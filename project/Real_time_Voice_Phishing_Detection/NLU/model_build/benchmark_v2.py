"""
benchmark_v2.py — v5 모델 기준 성능 측정 + 예시 추출
결과: NLU/model_build/benchmark_result.json
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import precision_score, recall_score, f1_score
from transformers import AutoTokenizer, ElectraForSequenceClassification

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE          = Path(__file__).parent.parent
PHISHING_FILE = BASE / "data/v5/test_phishing_augmented_data.json"
NORMAL_FILES  = [
    BASE / "data/v4/test_normal_tts.json",
    BASE / "data/v4/test_normal_callcenter.json",
    BASE / "data/raw/test_callcenter_finance.json",
]
NORMAL_RATIO  = 3
BASE_MODEL    = "monologg/koelectra-base-v3-discriminator"
FT_MODEL      = str(BASE / "models/koelectra-finetuned-v5/best")
MAX_LENGTH    = 128
THRESHOLD     = 0.5
LABEL_COLS    = ["기관사칭", "금전요구", "개인정보"]
SEED          = 42
N_EXAMPLES    = 12


def build_test_set():
    phishing = json.loads(PHISHING_FILE.read_text(encoding="utf-8"))
    normal_pool = []
    for f in NORMAL_FILES:
        if f.exists():
            normal_pool += json.loads(f.read_text(encoding="utf-8"))
    rng = random.Random(SEED)
    normal = rng.sample(normal_pool, min(len(phishing) * NORMAL_RATIO, len(normal_pool)))
    data = phishing + normal
    rng.shuffle(data)
    return data


@torch.inference_mode()
def run_model(model, tokenizer, texts, device):
    probs_all = []
    for text in texts:
        enc = tokenizer(text, return_tensors="pt", truncation=True,
                        max_length=MAX_LENGTH, padding="max_length").to(device)
        p = torch.sigmoid(model(**enc).logits[0]).cpu().numpy().tolist()
        probs_all.append(p)
    return np.array(probs_all)   # (N, 3) float


def compute_metrics(y_true, y_pred):
    prec = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    rec  = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    f1   = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    per  = [float(f1_score(y_true[:, i], y_pred[:, i], zero_division=0)) for i in range(3)]
    # binary FP rate
    bt = (y_true.sum(axis=1) > 0).astype(int)
    bp = (y_pred.sum(axis=1) > 0).astype(int)
    n_normal = int((bt == 0).sum())
    fp = int(((bt == 0) & (bp == 1)).sum())
    fp_rate = fp / n_normal if n_normal else 0.0
    return dict(precision=prec, recall=rec, f1=f1, per_f1=per,
                fp=fp, n_normal=n_normal, fp_rate=fp_rate)


def _interest_score(base_probs, ft_probs, true_label):
    """
    두 모델이 가장 크게 엇갈리는 샘플이 흥미롭다.
    FT가 맞고 Base가 틀린 정도 + FT 확신도를 점수화.
    """
    ft_pred  = (ft_probs  >= THRESHOLD).astype(int)
    base_pred = (base_probs >= THRESHOLD).astype(int)
    ft_correct   = int(np.array_equal(ft_pred, true_label))
    base_correct = int(np.array_equal(base_pred, true_label))
    ft_conf = float(np.max(np.abs(ft_probs - 0.5)))   # FT 확신도
    return (ft_correct - base_correct) * 2 + ft_conf


def select_examples(data, base_probs, ft_probs, y_true, n=N_EXAMPLES):
    scored = []
    for i, item in enumerate(data):
        score = _interest_score(base_probs[i], ft_probs[i], y_true[i])
        ft_pred   = (ft_probs[i]   >= THRESHOLD).astype(int).tolist()
        base_pred = (base_probs[i] >= THRESHOLD).astype(int).tolist()
        true_cats  = [LABEL_COLS[j] for j in range(3) if y_true[i][j] == 1] or ["정상"]
        base_cats  = [LABEL_COLS[j] for j in range(3) if base_pred[j] == 1] or ["정상"]
        ft_cats    = [LABEL_COLS[j] for j in range(3) if ft_pred[j]   == 1] or ["정상"]
        scored.append(dict(
            score=score,
            text=item["text"],
            true=true_cats,
            base=base_cats,
            ft=ft_cats,
            base_probs=[round(float(p), 3) for p in base_probs[i]],
            ft_probs=[round(float(p), 3) for p in ft_probs[i]],
            is_normal=(sum(y_true[i]) == 0),
        ))
    scored.sort(key=lambda x: -x["score"])
    return scored[:n]


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data   = build_test_set()
    texts  = [d["text"] for d in data]
    y_true = np.array([d["label"] for d in data], dtype=int)

    n_phishing = int((y_true.sum(axis=1) > 0).sum())
    print(f"테스트셋: {len(data)}개  (피싱 {n_phishing} / 정상 {len(data)-n_phishing})")

    # ── Base 모델 ──
    torch.manual_seed(SEED)
    print(f"\nBase 모델 로딩...")
    tok_b = AutoTokenizer.from_pretrained(BASE_MODEL)
    mdl_b = ElectraForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=3,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    ).to(device).eval()
    base_probs = run_model(mdl_b, tok_b, texts, device)
    base_preds = (base_probs >= THRESHOLD).astype(int)
    base_m = compute_metrics(y_true, base_preds)
    print(f"Base  Prec={base_m['precision']:.3f}  Rec={base_m['recall']:.3f}  F1={base_m['f1']:.3f}")
    del mdl_b

    # ── Fine-tuned 모델 ──
    print(f"\nFine-tuned 모델 로딩...")
    tok_f = AutoTokenizer.from_pretrained(FT_MODEL)
    mdl_f = ElectraForSequenceClassification.from_pretrained(FT_MODEL).to(device).eval()
    ft_probs  = run_model(mdl_f, tok_f, texts, device)
    ft_preds  = (ft_probs  >= THRESHOLD).astype(int)
    ft_m = compute_metrics(y_true, ft_preds)
    print(f"FT    Prec={ft_m['precision']:.3f}  Rec={ft_m['recall']:.3f}  F1={ft_m['f1']:.3f}")

    # ── 예시 선택 ──
    examples = select_examples(data, base_probs, ft_probs, y_true)

    result = dict(
        test_size=len(data),
        n_phishing=n_phishing,
        n_normal=len(data) - n_phishing,
        base=base_m,
        ft=ft_m,
        examples=examples,
    )

    out = Path(__file__).parent / "benchmark_result.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n결과 저장: {out}")
    print(f"\n예시 {len(examples)}개:")
    for i, ex in enumerate(examples, 1):
        print(f"  [{i:02d}] 실제={ex['true']}  Base={ex['base']}  FT={ex['ft']}")
        print(f"       {ex['text'][:70]}")


if __name__ == "__main__":
    main()
