import json
import sys
from dataclasses import asdict
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.filter import SlidingWindowFilter
from stt import Segment

BASE = Path(__file__).parent.parent
INPUT_PATH = BASE / "output/stt_output.json"
OUTPUT_PATH = BASE / "output/filter_output.json"


def run(window_size: int = 5, stride: int = 2) -> list[dict]:
    if not INPUT_PATH.exists():
        print(f"입력 파일 없음: {INPUT_PATH}")
        print("먼저 run_stt.py를 실행하세요.")
        return []

    data = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    window_filter = SlidingWindowFilter(window_size=window_size, stride=stride)

    results = []
    for item in data:
        segments = [Segment(**s) for s in item["segments"]]
        windows = window_filter.apply(segments)
        suspicious_count = sum(1 for w in windows if w.is_suspicious)

        print(f"{item['filename']}: {len(windows)}개 윈도우 → {suspicious_count}개 의심")

        results.append({
            "filename": item["filename"],
            "segments": item["segments"],
            "windows": [asdict(w) for w in windows],
            "suspicious_count": suspicious_count,
        })

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n저장 완료: {OUTPUT_PATH}")
    return results


if __name__ == "__main__":
    run()
