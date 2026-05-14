"""
전체 파이프라인 기준 Base vs FT 혼동행렬 비교
  키워드 필터 → KoELECTRA (Base / FT v5)
  테스트셋: mixed_test_v4.json
"""
import json
import sys
from pathlib import Path

import torch
import numpy as np
from transformers import AutoTokenizer, ElectraForSequenceClassification

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from analyzer import _keyword_score
ELECTRA_THRESHOLD = 15

BASE_DIR      = Path(__file__).parent.parent
TEST_FILE     = BASE_DIR / "test_scripts/data/mixed/mixed_test_v4.json"
BASE_MODEL    = "monologg/koelectra-base-v3-discriminator"
FT_MODEL      = str(BASE_DIR / "models/koelectra-finetuned-v5/best")
MAX_LENGTH    = 128
THRESHOLD     = 0.5
DANGER_THRESH = 0.5
SEED          = 42


def keyword_triggered(text: str) -> bool:
    return _keyword_score(text) >= ELECTRA_THRESHOLD


@torch.inference_mode()
def run_model(model, tokenizer, text: str, device: str) -> float:
    enc = tokenizer(text, return_tensors="pt", truncation=True,
                    max_length=MAX_LENGTH, padding="max_length").to(device)
    probs = torch.sigmoid(model(**enc).logits[0]).cpu().numpy()
    return float(probs.max())


def evaluate(dataset, model, tokenizer, device):
    tp = fp = fn = tn = 0
    triggered_total = 0

    for item in dataset:
        true_phishing = item["is_phishing"]

        if keyword_triggered(item["text"]):
            triggered_total += 1
            danger = run_model(model, tokenizer, item["text"], device)
            pred_phishing = danger >= DANGER_THRESH
        else:
            pred_phishing = False

        if true_phishing and pred_phishing:     tp += 1
        elif not true_phishing and pred_phishing: fp += 1
        elif true_phishing and not pred_phishing: fn += 1
        else:                                    tn += 1

    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec  = tp / (tp + fn) if (tp + fn) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc  = (tp + tn) / n if n else 0.0
    return dict(tp=tp, fp=fp, fn=fn, tn=tn,
                precision=prec, recall=rec, f1=f1, accuracy=acc,
                triggered=triggered_total)


def print_matrix(name, m, n_phishing, n_normal):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  KoELECTRA 트리거: {m['triggered']}회")
    print(f"\n             예측 피싱  예측 정상")
    print(f"  실제 피싱   {m['tp']:>6}    {m['fn']:>6}   ← 미탐 FN: {m['fn']}개")
    print(f"  실제 정상   {m['fp']:>6}    {m['tn']:>6}   ← 오탐 FP: {m['fp']}개")
    fp_rate = m['fp'] / n_normal if n_normal else 0.0
    print(f"\n  Accuracy : {m['accuracy']:.1%}")
    print(f"  Precision: {m['precision']:.3f}  ({m['precision']:.1%})")
    print(f"  Recall   : {m['recall']:.3f}  ({m['recall']:.1%})")
    print(f"  F1-Score : {m['f1']:.3f}  ({m['f1']:.1%})")
    print(f"  정상 오탐률: {m['fp']}/{n_normal} = {fp_rate:.1%}")


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dataset = json.loads(TEST_FILE.read_text(encoding="utf-8"))
    n_phishing = sum(1 for d in dataset if d["is_phishing"])
    n_normal   = len(dataset) - n_phishing
    print(f"테스트셋: {len(dataset)}개  (피싱 {n_phishing} / 정상 {n_normal})")

    # ── Base 모델 ──
    torch.manual_seed(SEED)
    print(f"\nBase 모델 로딩...")
    tok_b = AutoTokenizer.from_pretrained(BASE_MODEL)
    mdl_b = ElectraForSequenceClassification.from_pretrained(
        BASE_MODEL, num_labels=3,
        problem_type="multi_label_classification",
        ignore_mismatched_sizes=True,
    ).to(device).eval()
    m_base = evaluate(dataset, mdl_b, tok_b, device)
    del mdl_b

    # ── FT 모델 ──
    print(f"FT v5 모델 로딩...")
    tok_f = AutoTokenizer.from_pretrained(FT_MODEL)
    mdl_f = ElectraForSequenceClassification.from_pretrained(FT_MODEL).to(device).eval()
    m_ft = evaluate(dataset, mdl_f, tok_f, device)

    print_matrix("Base 모델 (랜덤 헤드, 파인튜닝 없음)", m_base, n_phishing, n_normal)
    print_matrix("Fine-tuned v5", m_ft, n_phishing, n_normal)

    print(f"\n{'='*60}")
    print(f"  비교 요약")
    print(f"{'='*60}")
    print(f"  {'':20s}  Base      FT v5")
    print(f"  {'Precision':20s}  {m_base['precision']:.3f}     {m_ft['precision']:.3f}")
    print(f"  {'Recall':20s}  {m_base['recall']:.3f}     {m_ft['recall']:.3f}")
    print(f"  {'F1':20s}  {m_base['f1']:.3f}     {m_ft['f1']:.3f}")
    print(f"  {'오탐(FP)':20s}  {m_base['fp']:>4}개      {m_ft['fp']:>4}개")
    print(f"  {'미탐(FN)':20s}  {m_base['fn']:>4}개      {m_ft['fn']:>4}개")


if __name__ == "__main__":
    main()
