import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import classification_report, f1_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, ElectraForSequenceClassification

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── 설정 ──────────────────────────────────────────────────────────────
BASE      = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
from config import DATA_VERSION, DATA_DIR
MODEL_DIR = BASE / f"models/koelectra-finetuned{'-v2' if DATA_VERSION == 'v2' else ''}/best"
MAX_LENGTH = 128
THRESHOLD  = 0.5

LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]


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


# ── 추론 ──────────────────────────────────────────────────────────────
@torch.inference_mode()
def predict(model, dataloader) -> tuple[np.ndarray, np.ndarray]:
    all_probs, all_labels = [], []
    for batch in dataloader:
        labels = batch.pop("labels")
        outputs = model(**{k: v for k, v in batch.items()})
        probs = torch.sigmoid(outputs.logits)
        all_probs.extend(probs.tolist())
        all_labels.extend(labels.tolist())
    return np.array(all_probs), np.array(all_labels)


# ── 오분류 샘플 출력 ──────────────────────────────────────────────────
def print_errors(data: list[dict], preds: np.ndarray, labels: np.ndarray, n: int = 5) -> None:
    errors = [
        i for i in range(len(preds))
        if not np.array_equal(preds[i], labels[i])
    ]
    if not errors:
        print("  오분류 없음")
        return
    for i in errors[:n]:
        true_str = [LABEL_COLS[j] for j in range(3) if labels[i][j] == 1] or ["정상"]
        pred_str = [LABEL_COLS[j] for j in range(3) if preds[i][j] == 1] or ["정상"]
        text_preview = data[i]["text"][:60].replace("\n", " ")
        print(f"  실제: {true_str} → 예측: {pred_str}  |  {text_preview}...")


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> None:
    if not MODEL_DIR.exists():
        print(f"모델 없음: {MODEL_DIR}\n먼저 train.py를 실행하세요.")
        return

    print(f"모델 로딩: {MODEL_DIR}")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = ElectraForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.eval()

    for split in ("val", "test"):
        path = DATA_DIR / f"{split}_ml.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        dataset = PhishingDataset(data, tokenizer)
        dataloader = DataLoader(dataset, batch_size=32)

        probs, labels = predict(model, dataloader)
        preds = (probs >= THRESHOLD).astype(int)

        macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)

        print(f"\n{'='*55}")
        print(f"  [{split.upper()}]  샘플 {len(data)}개  |  F1 (macro): {macro_f1:.4f}"
              f"  {'✓' if macro_f1 >= 0.87 else '✗'}")
        print("=" * 55)

        print("\n── 분류 리포트 ──")
        print(classification_report(labels, preds, target_names=LABEL_COLS, zero_division=0))

        print("── 카테고리별 임계값 0.5 기준 ──")
        for idx, col in enumerate(LABEL_COLS):
            col_preds  = preds[:, idx]
            col_labels = labels[:, idx].astype(int)
            f1 = f1_score(col_labels, col_preds, zero_division=0)
            pos_pred = col_preds.sum()
            pos_true = col_labels.sum()
            print(f"  {col:6}: F1={f1:.3f}  예측 양성={pos_pred}  실제 양성={pos_true}")

        print("\n── 오분류 샘플 (최대 5개) ──")
        print_errors(data, preds, labels)


if __name__ == "__main__":
    main()
