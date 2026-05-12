"""
KoELECTRA 멀티라벨 파인튜닝 — Colab 전용

Drive 폴더 구조:
  MyDrive/VoicePhishingData/
    data/
      phishing_augmented_data.json
      raw/
        normal_tts.json
        normal_callcenter.json
        callcenter_finance.json
    models/
      koelectra-finetuned-v4/   ← 체크포인트 저장
        best/                   ← 최종 모델

실행 (Colab 셀):
  # 셀 1 — 패키지 설치
  !pip install transformers torch scikit-learn

  # 셀 2 — Drive 마운트
  from google.colab import drive
  drive.mount('/content/drive')

  # 셀 3 — 학습 실행
  !python /content/drive/MyDrive/VoicePhishingData/train_colab.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import ConcatDataset, Dataset
from transformers import (
    AutoTokenizer,
    ElectraForSequenceClassification,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

# ── 경로 설정 ──────────────────────────────────────────────────────────
DRIVE_BASE  = Path("/content/drive/MyDrive/VoicePhishingData")
DATA_DIR    = DRIVE_BASE / "data"
OUTPUT_DIR  = DRIVE_BASE / "models/koelectra-finetuned-v5"

# ── 모델 설정 ──────────────────────────────────────────────────────────
MODEL_NAME = "monologg/koelectra-base-v3-discriminator"
MAX_LENGTH = 128
THRESHOLD  = 0.5
LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]
NUM_LABELS = len(LABEL_COLS)
POS_WEIGHT_CAP = 15.0

# ── 학습 파일 목록 ─────────────────────────────────────────────────────
SOURCE_FILES: list[Path] = [
    DATA_DIR / "v5/phishing_augmented_data.json",        # 피싱 1,510개
    DATA_DIR / "raw/normal_tts.json",                 # 정상 TTS 13,922개
    DATA_DIR / "raw/normal_callcenter.json",          # 정상 K쇼핑 2,500개
    DATA_DIR / "raw/callcenter_finance.json",         # 정상 금융보험 4,000개
]

TRAIN_FILES: list[Path] = []
VAL_FILES:   list[Path] = []
TEST_FILES:  list[Path] = []


# ── train/val/test 분할 ────────────────────────────────────────────────
def split_and_save(src: Path, train_ratio: float = 0.7, val_ratio: float = 0.1, seed: int = 42) -> tuple[Path, Path, Path]:
    stem       = src.stem
    train_path = src.parent / f"train_{stem}.json"
    val_path   = src.parent / f"val_{stem}.json"
    test_path  = src.parent / f"test_{stem}.json"

    if train_path.exists() and val_path.exists() and test_path.exists():
        print(f"  [skip] {stem} — 분할 파일 이미 존재")
        return train_path, val_path, test_path

    data       = json.loads(src.read_text(encoding="utf-8"))
    test_ratio = round(1.0 - train_ratio - val_ratio, 10)

    train_data, tmp = train_test_split(data, test_size=(1.0 - train_ratio), random_state=seed)
    val_data, test_data = train_test_split(
        tmp,
        test_size=test_ratio / (val_ratio + test_ratio),
        random_state=seed,
    )

    for path, subset in [(train_path, train_data), (val_path, val_data), (test_path, test_data)]:
        path.write_text(json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8")
        ph = sum(1 for d in subset if sum(d["label"]) > 0)
        print(f"  저장: {path.name:40s} {len(subset):5d}개  (피싱 {ph} / 정상 {len(subset)-ph})")

    return train_path, val_path, test_path


def prepare_splits() -> None:
    print("\n=== 데이터 분할 (7:1:2) ===")
    for src in SOURCE_FILES:
        if not src.exists():
            print(f"  [warn] {src.name} 없음, 건너뜀")
            continue
        t, v, te = split_and_save(src)
        TRAIN_FILES.append(t)
        VAL_FILES.append(v)
        TEST_FILES.append(te)


# ── 데이터셋 ──────────────────────────────────────────────────────────
def load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_dataset(files: list[Path], tokenizer) -> Dataset:
    datasets = [PhishingDataset(load_json(f), tokenizer) for f in files if f.exists()]
    return datasets[0] if len(datasets) == 1 else ConcatDataset(datasets)


def print_stats(label: str, files: list[Path]) -> list[dict]:
    all_data: list[dict] = []
    for f in files:
        if f.exists():
            data = load_json(f)
            all_data.extend(data)
            ph = sum(1 for d in data if sum(d["label"]) > 0)
            print(f"  {f.name:40s}: {len(data):5d}개  (피싱 {ph} / 정상 {len(data)-ph})")
    ph_total = sum(1 for d in all_data if sum(d["label"]) > 0)
    print(f"  {'[합계]':40s}: {len(all_data):5d}개  (피싱 {ph_total} / 정상 {len(all_data)-ph_total})")
    for col_idx, col in enumerate(LABEL_COLS):
        count = sum(1 for d in all_data if d["label"][col_idx] == 1)
        print(f"    {col}: {count}개")
    return all_data


class PhishingDataset(Dataset):
    def __init__(self, data: list[dict], tokenizer):
        self.data      = data
        self.tokenizer = tokenizer

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict:
        item = self.data[idx]
        enc  = self.tokenizer(
            item["text"],
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        )
        return {
            **{k: torch.tensor(v) for k, v in enc.items()},
            "labels": torch.tensor(item["label"], dtype=torch.float),
        }


# ── 클래스 불균형 보정 Trainer ────────────────────────────────────────
class WeightedTrainer(Trainer):
    def __init__(self, *args, pos_weight: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, **_):
        labels  = inputs.pop("labels")
        outputs = model(**inputs)
        loss_fn = torch.nn.BCEWithLogitsLoss(
            pos_weight=self.pos_weight.to(outputs.logits.device)
            if self.pos_weight is not None else None
        )
        loss = loss_fn(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


# ── 평가 지표 ─────────────────────────────────────────────────────────
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs     = 1 / (1 + np.exp(-logits))
    preds     = (probs >= THRESHOLD).astype(int)
    macro_f1  = f1_score(labels, preds, average="macro", zero_division=0)
    per_class = f1_score(labels, preds, average=None, zero_division=0)
    metrics   = {"f1_macro": macro_f1}
    for col, f1 in zip(LABEL_COLS, per_class):
        metrics[f"f1_{col}"] = f1
    return metrics


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> None:
    prepare_splits()

    print("\n=== train ===")
    train_data = print_stats("train", TRAIN_FILES)
    print("=== val ===")
    print_stats("val", VAL_FILES)
    print("=== test ===")
    print_stats("test", TEST_FILES)

    labels_arr = np.array([d["label"] for d in train_data], dtype=np.float32)
    n_pos      = labels_arr.sum(axis=0).clip(min=1)
    n_neg      = len(labels_arr) - n_pos
    pos_weight = torch.tensor(np.clip(n_neg / n_pos, 1.0, POS_WEIGHT_CAP), dtype=torch.float)
    print(f"\npos_weight (cap={POS_WEIGHT_CAP}): "
          + " / ".join(f"{c}={w:.1f}" for c, w in zip(LABEL_COLS, pos_weight.tolist())))

    print(f"\n모델 로딩: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model     = ElectraForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=NUM_LABELS,
        problem_type="multi_label_classification",
    )

    train_ds = build_dataset(TRAIN_FILES, tokenizer)
    val_ds   = build_dataset(VAL_FILES,   tokenizer)

    n_train         = len(train_ds)
    steps_per_epoch = n_train // 16
    warmup          = max(1, int(steps_per_epoch * 10 * 0.1))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    args = TrainingArguments(
        output_dir               = str(OUTPUT_DIR),
        num_train_epochs         = 10,
        per_device_train_batch_size = 32,   # Colab GPU 여유 있음
        per_device_eval_batch_size  = 64,
        learning_rate            = 3e-5,
        weight_decay             = 0.01,
        warmup_steps             = warmup,
        eval_strategy            = "epoch",
        save_strategy            = "epoch",
        load_best_model_at_end   = True,
        metric_for_best_model    = "f1_macro",
        greater_is_better        = True,
        logging_steps            = 20,
        fp16                     = True,    # Colab GPU (T4/A100) 지원
        dataloader_num_workers   = 2,
        report_to                = "none",
        save_total_limit         = 2,
    )

    trainer = WeightedTrainer(
        model          = model,
        args           = args,
        train_dataset  = train_ds,
        eval_dataset   = val_ds,
        compute_metrics= compute_metrics,
        callbacks      = [EarlyStoppingCallback(early_stopping_patience=3)],
        pos_weight     = pos_weight,
    )

    print("\n학습 시작 (멀티라벨, BCEWithLogitsLoss + pos_weight)\n")
    trainer.train()

    print("\n─── 테스트 세트 최종 평가 ───")
    test_data   = [item for f in TEST_FILES if f.exists() for item in load_json(f)]
    test_single = PhishingDataset(test_data, tokenizer)
    pred_out    = trainer.predict(test_single)
    probs       = 1 / (1 + np.exp(-pred_out.predictions))
    preds       = (probs >= THRESHOLD).astype(int)
    labels      = pred_out.label_ids

    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    print(f"F1 (macro): {macro_f1:.4f}  {'✓ 목표 달성' if macro_f1 >= 0.87 else '✗ 목표 미달 (0.87 필요)'}\n")
    print(classification_report(labels, preds, target_names=LABEL_COLS, zero_division=0))

    save_path = OUTPUT_DIR / "best"
    model.save_pretrained(str(save_path))
    tokenizer.save_pretrained(str(save_path))
    print(f"\n모델 저장 완료: {save_path}")


if __name__ == "__main__":
    main()
