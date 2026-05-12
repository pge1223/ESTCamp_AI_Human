"""
금융보험 콜센터 데이터에서 정상 발화 추출 (Training / Validation 분리)

출력:
  data/raw/callcenter_finance_train.json  ← 1.Training 4개 zip
  data/raw/callcenter_finance_val.json    ← 2.Validation 4개 zip

실행: python model_build/extract_callcenter_finance.py
"""
import json
import random
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(__file__).parent.parent
RAW_DIR  = BASE / "data/raw/callcenter_data/01.데이터"
OUT_DIR  = BASE / "data/raw"

SPLITS = {
    "train": ("1.Training",  "Training", 3000),
    "val":   ("2.Validation","Validation", 1000),
}

TEXT_FIELDS = ["고객질문(요청)", "상담사질문(요청)", "고객답변", "상담사답변"]
MIN_LEN     = 8
MAX_LEN     = 150
RANDOM_SEED = 42


def is_valid(text: str) -> bool:
    if not text or len(text) < MIN_LEN or len(text) > MAX_LEN:
        return False
    return text.count("ㅇ") / len(text) < 0.4


def extract_from_zip(zpath: Path) -> list[str]:
    texts: list[str] = []
    with zipfile.ZipFile(zpath) as z:
        for fname in z.namelist():
            raw = z.read(fname)
            try:
                records = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                records = json.loads(raw.decode("cp949"))
            for row in records:
                for field in TEXT_FIELDS:
                    text = str(row.get(field, "")).strip()
                    if is_valid(text):
                        texts.append(text)
    return texts


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(RANDOM_SEED)

    for split_key, (folder, suffix, sample_n) in SPLITS.items():
        finance_dir = RAW_DIR / folder / "라벨링데이터_220121_add" / "금융보험"
        zips = sorted(finance_dir.glob(f"*_{suffix}.zip"))
        print(f"\n[{split_key}] {folder} — zip {len(zips)}개")

        candidates: list[str] = []
        seen: set[str] = set()

        for zpath in zips:
            print(f"  처리 중: {zpath.name}")
            for text in extract_from_zip(zpath):
                if text not in seen:
                    seen.add(text)
                    candidates.append(text)

        print(f"  유효 문장: {len(candidates):,}개 → {sample_n}개 샘플링")
        sampled = random.sample(candidates, min(sample_n, len(candidates)))
        results = [{"text": t, "label": [0, 0, 0]} for t in sampled]

        out_path = OUT_DIR / f"callcenter_finance_{split_key}.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {out_path.name}  ({len(results)}개)")


if __name__ == "__main__":
    main()
