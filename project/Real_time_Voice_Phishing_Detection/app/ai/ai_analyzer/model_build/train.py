import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, f1_score
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    ElectraForSequenceClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 설정 ──────────────────────────────────────────────────────────────
BASE       = Path(__file__).parent.parent
MODEL_NAME = "monologg/koelectra-base-v3-discriminator"
sys.path.insert(0, str(BASE))
from config import DATA_VERSION, DATA_DIR

OUTPUT_DIR = BASE / f"models/koelectra-finetuned{'-v2' if DATA_VERSION == 'v2' else ''}"
MAX_LENGTH = 128
THRESHOLD  = 0.5

LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]
NUM_LABELS = len(LABEL_COLS)


# ── 데이터셋 ──────────────────────────────────────────────────────────
class PhishingDataset(Dataset):
    def __init__(self, data: list[dict], tokenizer):
        self.data = data
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict:
        item = self.data[idx]
        enc = self.tokenizer(
            item["text"],
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        )
        return {
            **{k: torch.tensor(v) for k, v in enc.items()},
            "labels": torch.tensor(item["label"], dtype=torch.float),
        }


# ── 평가 지표 ─────────────────────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = 1 / (1 + np.exp(-logits))          # sigmoid
    preds = (probs >= THRESHOLD).astype(int)
    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    per_class = f1_score(labels, preds, average=None, zero_division=0)
    metrics = {"f1_macro": macro_f1}
    for col, f1 in zip(LABEL_COLS, per_class):
        metrics[f"f1_{col}"] = f1
    return metrics


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> None:
    def load(name: str) -> list[dict]:
        return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))

    train_data = load("train_ml.json")
    val_data   = load("val_ml.json")
    test_data  = load("test_ml.json")

    print(f"train {len(train_data)}개 / val {len(val_data)}개 / test {len(test_data)}개")

    # 라벨 분포 출력
    for col_idx, col in enumerate(LABEL_COLS):
        count = sum(1 for d in train_data if d["label"][col_idx] == 1)
        print(f"  train {col}: {count}개")

    print(f"\n모델 로딩: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = ElectraForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )

    train_ds = PhishingDataset(train_data, tokenizer)
    val_ds   = PhishingDataset(val_data,   tokenizer)
    test_ds  = PhishingDataset(test_data,  tokenizer)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=10,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=32,
        learning_rate=3e-5,
        weight_decay=0.01,
        warmup_steps=72,   # 전체 720스텝의 10% (1152샘플 / 배치16 * 에폭10 * 0.1)
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_macro",
        greater_is_better=True,
        logging_steps=20,
        fp16=False,
        dataloader_num_workers=0,
        report_to="none",
        save_total_limit=2,
    )

    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=3)],
    )

    print("\n학습 시작 (멀티라벨, BCEWithLogitsLoss)\n")
    trainer.train()

    print("\n─── 테스트 세트 최종 평가 ───")
    pred_out = trainer.predict(test_ds)
    logits = pred_out.predictions
    labels = pred_out.label_ids
    probs  = 1 / (1 + np.exp(-logits))
    preds  = (probs >= THRESHOLD).astype(int)

    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    print(f"F1 (macro): {macro_f1:.4f}  {'✓ 목표 달성' if macro_f1 >= 0.87 else '✗ 목표 미달 (0.87 필요)'}\n")
    print(classification_report(labels, preds, target_names=LABEL_COLS, zero_division=0))

    save_path = OUTPUT_DIR / "best"
    model.save_pretrained(str(save_path))
    tokenizer.save_pretrained(str(save_path))
    print(f"모델 저장 완료: {save_path}")


if __name__ == "__main__":
    main()
