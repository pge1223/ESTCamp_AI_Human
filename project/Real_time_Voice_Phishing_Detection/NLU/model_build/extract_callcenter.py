"""
K쇼핑 민원 콜센터 데이터에서 정상 발화 문장 추출

출력: data/v2/normal_callcenter.json
형식: [{"text": "...", "label": [0, 0, 0]}, ...]

실행: python model_build/extract_callcenter.py
"""
import json
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(BASE))
SRC      = BASE / "test_scripts/data/raw/as/민원(콜센터) 질의응답_K쇼핑_업무처리_Training.json"
OUT_PATH = BASE / "data/raw/normal_callcenter.json"

SAMPLE_N  = 2500
TEXT_FIELDS = ["고객질문(요청)", "상담사질문(요청)", "고객답변", "상담사답변"]
MIN_LEN   = 8
MAX_LEN   = 150
RANDOM_SEED = 42


def is_valid(text: str) -> bool:
    if not text or len(text) < MIN_LEN or len(text) > MAX_LEN:
        return False
    # ㅇ으로 익명화된 비율이 절반 이상이면 제외
    o_ratio = text.count("ㅇ") / len(text)
    return o_ratio < 0.4


def main() -> None:
    print(f"로딩: {SRC.name}")
    with open(SRC, encoding="cp949", errors="replace") as f:
        records = json.load(f)
    print(f"총 레코드: {len(records):,}개")

    candidates: list[str] = []
    seen: set[str] = set()

    for row in records:
        for field in TEXT_FIELDS:
            text = str(row.get(field, "")).strip()
            if is_valid(text) and text not in seen:
                seen.add(text)
                candidates.append(text)

    print(f"유효 문장: {len(candidates):,}개")

    random.seed(RANDOM_SEED)
    sampled = random.sample(candidates, min(SAMPLE_N, len(candidates)))

    results = [{"text": t, "label": [0, 0, 0]} for t in sampled]

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: {len(results):,}개 문장 → {OUT_PATH}")


if __name__ == "__main__":
    main()
