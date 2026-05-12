"""
혼합 테스트 데이터셋으로 파이프라인 성능 평가

실행: python test_scripts/run_mixed_test.py
      python test_scripts/run_mixed_test.py --file mixed_test_02.json
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import analyzer as az
from config import DATA_VERSION

MIXED_DIR  = Path(__file__).parent / "data/mixed"
LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]


def normalize_dataset(dataset: list[dict]) -> list[dict]:
    """label 배열 포맷 → is_phishing 포맷으로 변환. 이미 is_phishing이면 그대로."""
    result = []
    for item in dataset:
        if "is_phishing" in item:
            result.append(item)
        else:
            result.append({
                "text": item["text"],
                "is_phishing": any(item.get("label", [])),
            })
    return result


def evaluate(dataset: list[dict]) -> dict:
    tp = fp = fn = tn = 0
    triggered_total = 0
    errors: list[dict] = []

    for item in dataset:
        az.reset()
        result = az.analyze(item["text"])

        pred_phishing = result["triggered"] and result["danger_level"] >= 0.5
        true_phishing = item["is_phishing"]

        if result["triggered"]:
            triggered_total += 1

        if true_phishing and pred_phishing:
            tp += 1
        elif not true_phishing and pred_phishing:
            fp += 1
            errors.append({"type": "FP", "text": item["text"],
                           "danger": result["danger_level"],
                           "cats": result["categories"]})
        elif true_phishing and not pred_phishing:
            fn += 1
            errors.append({"type": "FN", "text": item["text"],
                           "score": result["keyword_score"],
                           "triggered": result["triggered"],
                           "danger": result["danger_level"]})
        else:
            tn += 1

    n = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall    = tp / (tp + fn) if (tp + fn) else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy  = (tp + tn) / n if n else 0.0

    return dict(n=n, tp=tp, fp=fp, fn=fn, tn=tn,
                precision=precision, recall=recall, f1=f1, accuracy=accuracy,
                triggered=triggered_total, errors=errors)


def print_report(fname: str, dataset: list[dict], m: dict) -> None:
    n_phishing = sum(1 for d in dataset if d["is_phishing"])
    n_normal   = m["n"] - n_phishing

    print(f"\n{'='*65}")
    print(f"  {fname}  (총 {m['n']}개 | 피싱 {n_phishing} / 정상 {n_normal})   - {DATA_VERSION} 모델")
    print(f"{'='*65}")
    print(f"  KoELECTRA 트리거 : {m['triggered']}회")
    print()
    print(f"  {'':10s}  예측 피싱  예측 정상")
    print(f"  실제 피싱     {m['tp']:>5}      {m['fn']:>5}   ← 미탐(FN): {m['fn']}개")
    print(f"  실제 정상     {m['fp']:>5}      {m['tn']:>5}   ← 오탐(FP): {m['fp']}개")
    print()
    print(f"  Accuracy : {m['accuracy']:.1%}")
    print(f"  Precision: {m['precision']:.1%}")
    print(f"  Recall   : {m['recall']:.1%}   (피싱 {m['tp']}/{m['tp']+m['fn']}개 탐지)")
    print(f"  F1-Score : {m['f1']:.1%}")

    if m["errors"]:
        fn_list = [e for e in m["errors"] if e["type"] == "FN"]
        fp_list = [e for e in m["errors"] if e["type"] == "FP"]

        if fn_list:
            fn_filter = [e for e in fn_list if not e["triggered"]]
            fn_electra = [e for e in fn_list if e["triggered"]]
            print(f"\n  [미탐 FN {len(fn_list)}건]")
            if fn_filter:
                print(f"    ▸ 키워드 필터 미통과 ({len(fn_filter)}건)")
                for e in fn_filter[:5]:
                    print(f"      score={e['score']:2d}  {e['text']}")
            if fn_electra:
                print(f"    ▸ 필터 통과 후 KoELECTRA 미탐지 ({len(fn_electra)}건)")
                for e in fn_electra[:5]:
                    print(f"      score={e['score']:2d} danger={e['danger']:.1%}  {e['text']}")

        if fp_list:
            print(f"\n  [오탐 FP {len(fp_list)}건] — 정상인데 피싱으로 판정")
            for i, e in enumerate(fp_list, 1):
                print(f"    [{i}] danger={e['danger']:.1%} cats={e['cats']}")
                print(f"         {e['text']}")

    print(f"{'='*65}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=None,
                        help="mixed_test_01.json 등 파일명 (기본: 전체)")
    parser.add_argument("--path", default=None,
                        help="임의 경로의 테스트 파일 (label 배열 포맷도 지원)")
    args = parser.parse_args()

    if args.path:
        files = [Path(args.path)]
    elif args.file:
        files = [MIXED_DIR / args.file]
    else:
        files = sorted(MIXED_DIR.glob("mixed_test_*.json"))

    if not files:
        print("mixed 데이터 없음. 먼저 make_test_dataset.py 실행")
        sys.exit(1)

    for path in files:
        dataset = json.loads(path.read_text(encoding="utf-8"))
        dataset = normalize_dataset(dataset)
        print(f"\n{path.name} 평가 중... ({len(dataset)}개)", flush=True)
        m = evaluate(dataset)
        print_report(path.name, dataset, m)


if __name__ == "__main__":
    main()
