import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import imageio_ffmpeg

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ffmpeg_dir = str(Path(imageio_ffmpeg.get_ffmpeg_exe()).parent)
os.environ["PATH"] = _ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

from stt import WhisperSTT

BASE = Path(__file__).parent.parent
DATA_DIR = BASE / "data"
OUTPUT_PATH = BASE / "output/stt_output.json"


def run(model_size: str = "small") -> list[dict]:
    audio_files = sorted(DATA_DIR.glob("*.mp4"))
    if not audio_files:
        print("data 폴더에 MP4 파일이 없습니다.")
        return []

    print(f"파일 {len(audio_files)}개 발견")
    stt = WhisperSTT(model_size=model_size)

    results = []
    for i, path in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] {path.name}")
        segments = stt.transcribe(str(path))
        for seg in segments:
            print(f"  {seg}")
        results.append({
            "filename": path.name,
            "segments": [asdict(seg) for seg in segments],
        })

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n저장 완료: {OUTPUT_PATH}  ({len(results)}개 파일)")
    return results


if __name__ == "__main__":
    run()
