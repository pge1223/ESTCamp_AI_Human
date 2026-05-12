"""
보이스피싱 탐지 성능 비교
① 키워드 규칙 기반
② KoELECTRA 베이스 (파인튜닝 전 — 랜덤 분류 헤드)
③ KoELECTRA 파인튜닝 (현재 모델)

실행: uv run python voicephishing_detection_model/compare.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import f1_score, precision_score, recall_score
from transformers import AutoTokenizer, ElectraForSequenceClassification

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.filter import PHISHING_KEYWORDS

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE            = Path(__file__).parent.parent
from config import DATA_VERSION, DATA_DIR
MODEL_FINETUNED = BASE / f"models/koelectra-finetuned-{DATA_VERSION}/best"
BASE_MODEL_NAME = "monologg/koelectra-base-v3-discriminator"
DATA_PATH       = DATA_DIR / "test_ml.json"
MAX_LENGTH      = 128
THRESHOLD       = 0.5
LABEL_COLS      = ["기관사칭", "금전요구", "개인정보"]


def load_test_data() -> tuple[np.ndarray, list[str]]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    labels = np.array([d["label"] for d in data], dtype=int)   # (N, 3)
    texts  = [d["text"] for d in data]
    return labels, texts


# ── ① 키워드 규칙 기반 ────────────────────────────────────────────────
def predict_keyword(texts: list[str]) -> np.ndarray:
    results = []
    for text in texts:
        normalized = text.lower().replace(" ", "")
        row = [
            int(any(kw.lower().replace(" ", "") in normalized for kw in PHISHING_KEYWORDS[col]))
            for col in LABEL_COLS
        ]
        results.append(row)
    return np.array(results, dtype=int)   # (N, 3)


# ── ② ③ KoELECTRA 추론 ───────────────────────────────────────────────
@torch.inference_mode()
def predict_electra(model, tokenizer, texts: list[str], device: str) -> np.ndarray:
    results = []
    for text in texts:
        enc = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        ).to(device)
        probs = torch.sigmoid(model(**enc).logits[0]).cpu().numpy()
        results.append((probs >= THRESHOLD).astype(int))
    return np.array(results, dtype=int)   # (N, 3)


# ── 지표 출력 ─────────────────────────────────────────────────────────
def print_report(name: str, y_true: np.ndarray, y_pred: np.ndarray, texts: list[str]) -> dict:
    # 이진 집계 (하나라도 탐지 → 피싱)
    bin_true = (y_true.sum(axis=1) > 0).astype(int)
    bin_pred = (y_pred.sum(axis=1) > 0).astype(int)

    tp = int(((bin_true == 1) & (bin_pred == 1)).sum())
    fp = int(((bin_true == 0) & (bin_pred == 1)).sum())
    fn = int(((bin_true == 1) & (bin_pred == 0)).sum())
    tn = int(((bin_true == 0) & (bin_pred == 0)).sum())
    n  = len(bin_true)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1_bin    = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy  = (tp + tn) / n

    print(f"\n{'─'*65}")
    print(f"  {name}")
    print(f"{'─'*65}")
    print(f"  [전체 피싱/정상]")
    print(f"    Accuracy : {accuracy:.0%}  ({tp+tn}/{n}개 정답)")
    print(f"    Precision: {precision:.0%}")
    print(f"    Recall   : {recall:.0%}   (피싱 {tp}/{tp+fn}개 탐지)")
    print(f"    F1-Score : {f1_bin:.0%}")

    print(f"  [카테고리별 멀티라벨]")
    per_f1 = []
    for i, col in enumerate(LABEL_COLS):
        p = precision_score(y_true[:, i], y_pred[:, i], zero_division=0)
        r = recall_score(y_true[:, i], y_pred[:, i], zero_division=0)
        f = f1_score(y_true[:, i], y_pred[:, i], zero_division=0)
        per_f1.append(f)
        pos_true = int(y_true[:, i].sum())
        pos_pred = int(y_pred[:, i].sum())
        print(f"    {col:6s}  P={p:.2f}  R={r:.2f}  F1={f:.2f}"
              f"  (실제 {pos_true}개 / 예측 {pos_pred}개)")
    macro_f1 = float(np.mean(per_f1))
    print(f"    {'매크로':6s}  F1(macro)={macro_f1:.2f}")

    # 오분류 (이진 기준)
    errors = [(bin_true[i], bin_pred[i], texts[i])
              for i in range(n) if bin_true[i] != bin_pred[i]]
    if errors:
        print(f"  오분류 {len(errors)}건 (이진 기준):")
        for t, p, s in errors[:5]:
            tag = "미탐 FN" if t == 1 else "오탐 FP"
            print(f"    [{tag}] {s[:50]}...")
    else:
        print("  오분류 없음 ✓")

    return dict(accuracy=accuracy, precision=precision, recall=recall,
                f1=f1_bin, macro_f1=macro_f1, per_f1=per_f1)


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    labels, texts = load_test_data()

    n_phishing = int((labels.sum(axis=1) > 0).sum())
    print(f"{'='*65}")
    print(f"  보이스피싱 탐지 성능 비교  ({DATA_PATH.name}, {len(texts)}개)")
    print(f"  피싱 {n_phishing}개 / 정상 {len(texts)-n_phishing}개")
    print(f"  라벨 분포: 기관사칭 {int(labels[:,0].sum())} / 금전요구 {int(labels[:,1].sum())} / 개인정보 {int(labels[:,2].sum())}")
    print(f"{'='*65}")

    # ① 키워드
    m1 = print_report("① 키워드 규칙 기반", labels, predict_keyword(texts), texts)

    # ② 베이스 (파인튜닝 전)
    print(f"\n베이스 모델 로딩: {BASE_MODEL_NAME}")
    tok_base = AutoTokenizer.from_pretrained(BASE_MODEL_NAME)
    mdl_base = ElectraForSequenceClassification.from_pretrained(
        BASE_MODEL_NAME,
        num_labels=3,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    ).to(device).eval()
    m2 = print_report("② KoELECTRA 베이스 (파인튜닝 전)", labels,
                      predict_electra(mdl_base, tok_base, texts, device), texts)

    # ③ 파인튜닝
    if not MODEL_FINETUNED.exists():
        print(f"\n파인튜닝 모델 없음: {MODEL_FINETUNED}")
        return
    print(f"\n파인튜닝 모델 로딩: {MODEL_FINETUNED}")
    tok_ft = AutoTokenizer.from_pretrained(str(MODEL_FINETUNED))
    mdl_ft = ElectraForSequenceClassification.from_pretrained(str(MODEL_FINETUNED)).to(device).eval()
    m3 = print_report("③ KoELECTRA 파인튜닝 (현재 모델)", labels,
                      predict_electra(mdl_ft, tok_ft, texts, device), texts)

    # 요약 비교표
    print(f"\n{'='*65}")
    print(f"  {'':34s} Acc    Prec   Recall  F1(bin)  F1(macro)")
    print(f"{'─'*65}")
    for name, m in [("① 키워드 규칙 기반", m1),
                    ("② KoELECTRA 베이스", m2),
                    ("③ KoELECTRA 파인튜닝", m3)]:
        print(f"  {name:34s} {m['accuracy']:.0%}    {m['precision']:.0%}    "
              f"{m['recall']:.0%}    {m['f1']:.0%}    {m['macro_f1']:.0%}")
    print(f"{'─'*65}")
    print(f"  {'카테고리별 F1 (파인튜닝)':34s} ", end="")
    for col, f in zip(LABEL_COLS, m3["per_f1"]):
        print(f"{col}={f:.0%}  ", end="")
    print(f"\n{'='*65}")


if __name__ == "__main__":
    main()
