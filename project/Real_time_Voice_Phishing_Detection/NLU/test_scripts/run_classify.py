import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.classifier import KoELECTRAClassifier
from pipeline.filter import WindowResult

BASE = Path(__file__).parent.parent
INPUT_PATH = BASE / "output/filter_output.json"
OUTPUT_PATH = BASE / "output/classify_output.json"


def run() -> list[dict]:
    if not INPUT_PATH.exists():
        print(f"입력 파일 없음: {INPUT_PATH}")
        print("먼저 run_filter.py를 실행하세요.")
        return []

    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    classifier = KoELECTRAClassifier()

    results = []
    for item in data:
        suspicious = [WindowResult(**w) for w in item["windows"] if w["is_suspicious"]]

        if not suspicious:
            print(f"{item['filename']}: 이상 없음")
            results.append({"filename": item["filename"], "results": []})
            continue

        file_results = []
        for window in suspicious:
            result = classifier.classify(window.text)
            flag = "⚠" if result.is_phishing() else "✓"
            print(
                f"  {flag} {item['filename']} "
                f"[{window.start_idx}~{window.end_idx}] "
                f"{result.label} ({result.confidence:.1%})"
            )
            file_results.append({
                "start_idx": window.start_idx,
                "end_idx": window.end_idx,
                "text": window.text,
                "matched_categories": window.matched_categories,
                "label": result.label,
                "confidence": result.confidence,
                "scores": result.scores,
                "is_phishing": result.is_phishing(),
            })

        results.append({"filename": item["filename"], "results": file_results})

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n저장 완료: {OUTPUT_PATH}")
    return results


if __name__ == "__main__":
    run()
