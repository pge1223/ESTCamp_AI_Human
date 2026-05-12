"""
133.감성 및 발화 스타일 동시 고려 음성합성 데이터에서
친절체 + 대화체 문장을 전부 추출해 정상 샘플 JSON 생성

출력: data/v2/normal_tts.json
형식: [{"text": "...", "label": [0, 0, 0]}, ...]

실행: python model_build/extract_normal_tts.py
"""
import glob
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(BASE))
RAW_DIR  = BASE / "data/raw/133.감성 및 발화 스타일 동시 고려 음성합성 데이터/01-1.정식개방데이터"
OUT_PATH = BASE / "data/raw/normal_tts.json"

STYLES = ["친절체", "대화체"]


def iter_sentences(zip_path: Path):
    with zipfile.ZipFile(zip_path) as z:
        for fname in z.namelist():
            raw = z.read(fname)
            try:
                records = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                records = json.loads(raw.decode("cp949"))

            for item in records:
                # sentences 필드가 있으면 개별 발화 단위 사용
                if item.get("sentences"):
                    for sent in item["sentences"]:
                        text = sent.get("origin_text", "").strip()
                        if text:
                            yield text
                else:
                    for text in item["script"]["normalized"]:
                        text = text.strip()
                        if text:
                            yield text


def main() -> None:
    results = []
    seen: set[str] = set()

    for split in ["Training", "Validation"]:
        prefix = "TL" if split == "Training" else "VL"
        for style in STYLES:
            pattern = str(RAW_DIR / split / "02.라벨링데이터" / f"{prefix}_{style}_*.zip")
            zips = sorted(glob.glob(pattern))
            print(f"{split}/{style}: {len(zips)}개 zip 처리 중...")
            for zpath in zips:
                for text in iter_sentences(Path(zpath)):
                    if text not in seen:
                        seen.add(text)
                        results.append({"text": text, "label": [0, 0, 0]})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: {len(results):,}개 문장 → {OUT_PATH}")


if __name__ == "__main__":
    main()