"""
혼동행렬 및 지표 검증 스크립트
슬라이드 수치가 올바른지 확인용

비교 기준:
  Base  : monologg/koelectra-base-v3-discriminator + 랜덤 분류 헤드 (파인튜닝 없음)
  FT    : koelectra-finetuned-v5 (보이스피싱 데이터 파인튜닝)

테스트셋: v5 피싱 + v4 정상 (3:1 비율)
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

BASE = Path(__file__).parent.parent
PHISHING_FILE  = BASE / "data/v5/test_phishing_augmented_data.json"
NORMAL_FILES   = [
    BASE / "data/v4/test_normal_tts.json",
    BASE / "data/v4/test_normal_callcenter.json",
    BASE / "data/raw/test_callcenter_finance.json",
]
NORMAL_RATIO   = 3
BASE_MODEL     = "monologg/koelectra-base-v3-discriminator"
FT_MODEL       = str(BASE / "models/koelectra-finetuned-v5/best")
MAX_LENGTH     = 128
THRESHOLD      = 0.5
LABEL_COLS     = ["기관사칭", "금전요구", "개인정보"]
SEED           = 42


# ── 테스트셋 구성 ────────────────────────────────────────────────────────
def build_test_set():
    phishing = json.loads(PHISHING_FILE.read_text(encoding="utf-8"))
    normal_pool = []
    for f in NORMAL_FILES:
        if f.exists():
            normal_pool += json.loads(f.read_text(encoding="utf-8"))

    n_normal = len(phishing) * NORMAL_RATIO
    rng = random.Random(SEED)
    normal = rng.sample(normal_pool, min(n_normal, len(normal_pool)))

    data = phishing + normal
    rng.shuffle(data)
    return data


# ── 추론 ─────────────────────────────────────────────────────────────────
@torch.inference_mode()
def run_model(model, tokenizer, texts, device):
    preds = []
    for text in texts:
        enc = tokenizer(text, return_tensors="pt", truncation=True,
                        max_length=MAX_LENGTH, padding="max_length").to(device)
        probs = torch.sigmoid(model(**enc).logits[0]).cpu().numpy()
        preds.append((probs >= THRESHOLD).astype(int).tolist())
    return np.array(preds, dtype=int)


# ── 혼동행렬 출력 ────────────────────────────────────────────────────────
def print_confusion(name, y_true, y_pred):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")

    # 카테고리별 혼동행렬
    print(f"\n  {'카테고리':<8}  TP    FP    TN    FN  |  Prec   Rec    F1")
    print(f"  {'─'*57}")
    for i, col in enumerate(LABEL_COLS):
        yt = y_true[:, i]
        yp = y_pred[:, i]
        tp = int(((yt == 1) & (yp == 1)).sum())
        fp = int(((yt == 0) & (yp == 1)).sum())
        tn = int(((yt == 0) & (yp == 0)).sum())
        fn = int(((yt == 1) & (yp == 0)).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec  = tp / (tp + fn) if (tp + fn) else 0.0
        f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"  {col:<8}  {tp:4d}  {fp:4d}  {tn:4d}  {fn:4d}  |  {prec:.3f}  {rec:.3f}  {f1:.3f}")

    macro_prec = float(precision_score(y_true, y_pred, average="macro", zero_division=0))
    macro_rec  = float(recall_score(y_true, y_pred, average="macro", zero_division=0))
    macro_f1   = float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    per_f1     = [float(f1_score(y_true[:,i], y_pred[:,i], zero_division=0)) for i in range(3)]
    print(f"  {'─'*57}")
    print(f"  {'Macro':8}                          |  {macro_prec:.3f}  {macro_rec:.3f}  {macro_f1:.3f}")

    # 이진 혼동행렬 (피싱 여부)
    bt = (y_true.sum(axis=1) > 0).astype(int)
    bp = (y_pred.sum(axis=1) > 0).astype(int)
    tp  = int(((bt == 1) & (bp == 1)).sum())
    fp  = int(((bt == 0) & (bp == 1)).sum())
    tn  = int(((bt == 0) & (bp == 0)).sum())
    fn  = int(((bt == 1) & (bp == 0)).sum())
    n_normal = int((bt == 0).sum())

    print(f"\n  [이진 — 피싱 여부]")
    print(f"             예측 정상  예측 피싱")
    print(f"  실제 정상   {tn:5d}     {fp:5d}   ← 오탐 {fp/n_normal:.1%}" if n_normal else "")
    print(f"  실제 피싱   {fn:5d}     {tp:5d}")
    fp_rate = fp / n_normal if n_normal else 0.0
    print(f"\n  정상 오탐률: {fp}/{n_normal} = {fp_rate:.1%}")

    return dict(macro_prec=macro_prec, macro_rec=macro_rec, macro_f1=macro_f1, per_f1=per_f1)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    data = build_test_set()
    texts  = [d["text"] for d in data]
    labels = np.array([d["label"] for d in data], dtype=int)

    n_phishing = int((labels.sum(axis=1) > 0).sum())
    n_normal   = len(data) - n_phishing
    print(f"테스트셋: 총 {len(data)}개  (피싱 {n_phishing}개 / 정상 {n_normal}개, {n_normal//n_phishing}:1)")
    print(f"비교 기준: Base = 랜덤 헤드, FT = v5 파인튜닝")

    # ── Base 모델 (랜덤 헤드 재현성을 위해 시드 고정) ──
    torch.manual_seed(42)
    print(f"\nBase 모델 로딩: {BASE_MODEL}")
    tok_b = AutoTokenizer.from_pretrained(BASE_MODEL)
    mdl_b = ElectraForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=3,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    ).to(device).eval()
    pred_b = run_model(mdl_b, tok_b, texts, device)
    res_b  = print_confusion("Base 모델 (랜덤 분류 헤드, 파인튜닝 없음)", labels, pred_b)

    # ── Fine-tuned 모델 ──
    print(f"\nFine-tuned 모델 로딩: {FT_MODEL}")
    tok_f = AutoTokenizer.from_pretrained(FT_MODEL)
    mdl_f = ElectraForSequenceClassification.from_pretrained(FT_MODEL).to(device).eval()
    pred_f = run_model(mdl_f, tok_f, texts, device)
    res_f  = print_confusion("Fine-tuned 모델 (v5)", labels, pred_f)

    # ── 슬라이드 수치 검증 ──
    print(f"\n{'='*60}")
    print(f"  슬라이드 수치 검증")
    print(f"{'='*60}")
    slide = {
        "base":  dict(prec=0.123, rec=0.339, f1=0.156,
                      per=[0.275, 0.193, 0.000]),
        "ft":    dict(prec=0.936, rec=0.951, f1=0.944,
                      per=[1.000, 0.905, 0.926]),
    }
    for tag, res, sl in [("Base", res_b, slide["base"]), ("FT", res_f, slide["ft"])]:
        ok_p  = abs(res["macro_prec"] - sl["prec"]) < 0.01
        ok_r  = abs(res["macro_rec"]  - sl["rec"])  < 0.01
        ok_f1 = abs(res["macro_f1"]   - sl["f1"])   < 0.01
        print(f"\n  [{tag}]")
        print(f"    Precision : 슬라이드 {sl['prec']:.3f} / 실측 {res['macro_prec']:.3f}  {'✓' if ok_p else '✗ 불일치'}")
        print(f"    Recall    : 슬라이드 {sl['rec']:.3f} / 실측 {res['macro_rec']:.3f}  {'✓' if ok_r else '✗ 불일치'}")
        print(f"    F1(macro) : 슬라이드 {sl['f1']:.3f} / 실측 {res['macro_f1']:.3f}  {'✓' if ok_f1 else '✗ 불일치'}")
        for i, col in enumerate(LABEL_COLS):
            ok_c = abs(res["per_f1"][i] - sl["per"][i]) < 0.01
            print(f"    F1({col}): 슬라이드 {sl['per'][i]:.3f} / 실측 {res['per_f1'][i]:.3f}  {'✓' if ok_c else '✗ 불일치'}")


if __name__ == "__main__":
    main()
