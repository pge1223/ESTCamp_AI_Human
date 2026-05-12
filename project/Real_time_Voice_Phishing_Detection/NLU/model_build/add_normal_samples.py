"""
콜센터 정상 샘플을 학습 데이터에 추가하고 재분할

문제: 모델이 콜센터 환불/입금 문장을 피싱으로 오탐
원인: 학습 데이터 정상 샘플(205개)이 피싱(947개) 대비 부족
해결: 콜센터 정상 문장 ~300개 추가 → 재분할 → 재학습

실행: python model_build/add_normal_samples.py
"""
import json
import random
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE     = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
from config import DATA_DIR
AS_PATH  = BASE / "test_scripts/data/raw/as/민원(콜센터) 질의응답_K쇼핑_업무처리_Training.json"

# 금융 키워드 포함 문장 우선 추출 (FP 원인 패턴)
FINANCIAL_KEYWORDS = ["계좌", "입금", "현금", "환불", "이체", "송금", "카드", "결제", "납부"]

ADD_FINANCIAL = 150   # 금융 키워드 포함 정상 문장
ADD_GENERAL   = 150   # 일반 정상 문장
VAL_TEST_RATIO = 0.1  # 각 10%
SEED = 99


def load_callcenter(path: Path) -> list[str]:
    with open(path, encoding="cp949") as f:
        data = json.load(f)
    fields = ["고객질문(요청)", "상담사질문(요청)"]
    texts = []
    for record in data:
        for field in fields:
            text = record.get(field, "").strip()
            if len(text) >= 10:
                texts.append(text)
    return texts


def main() -> None:
    rng = random.Random(SEED)

    # ── 기존 데이터 로드 ──────────────────────────────────────────────
    train = json.loads((DATA_DIR / "train_ml.json").read_text(encoding="utf-8"))
    val   = json.loads((DATA_DIR / "val_ml.json").read_text(encoding="utf-8"))
    test  = json.loads((DATA_DIR / "test_ml.json").read_text(encoding="utf-8"))

    existing_texts = {d["text"] for d in train + val + test}
    n_phishing = sum(1 for d in train + val + test if sum(d["label"]) > 0)
    n_normal   = sum(1 for d in train + val + test if sum(d["label"]) == 0)
    print(f"기존 데이터: {len(existing_texts)}개 (피싱 {n_phishing} / 정상 {n_normal})")

    # ── 콜센터 데이터 로드 및 중복 제거 ──────────────────────────────
    all_callcenter = load_callcenter(AS_PATH)
    unique = [t for t in all_callcenter if t not in existing_texts]
    print(f"콜센터 후보: {len(unique)}개 (중복 제거 후)")

    # ── 금융 키워드 포함 / 미포함 분류 ───────────────────────────────
    financial, general = [], []
    for text in unique:
        if any(kw in text for kw in FINANCIAL_KEYWORDS):
            financial.append(text)
        else:
            general.append(text)

    print(f"  금융 키워드 포함: {len(financial)}개")
    print(f"  일반: {len(general)}개")

    # ── 샘플링 ───────────────────────────────────────────────────────
    sampled_fin = rng.sample(financial, min(ADD_FINANCIAL, len(financial)))
    sampled_gen = rng.sample(general,   min(ADD_GENERAL,   len(general)))
    new_samples = [
        {"text": t, "label": [0, 0, 0], "source": "callcenter_normal"}
        for t in sampled_fin + sampled_gen
    ]
    print(f"\n추가할 정상 샘플: {len(new_samples)}개")
    print(f"  금융 키워드 포함: {len(sampled_fin)}개")
    print(f"  일반: {len(sampled_gen)}개")

    # ── 전체 재분할 ───────────────────────────────────────────────────
    all_data = train + val + test + new_samples
    rng.shuffle(all_data)

    n_total    = len(all_data)
    n_val_test = int(n_total * VAL_TEST_RATIO)
    new_val    = all_data[:n_val_test]
    new_test   = all_data[n_val_test:n_val_test * 2]
    new_train  = all_data[n_val_test * 2:]

    print(f"\n재분할 결과:")
    for name, split in [("train", new_train), ("val", new_val), ("test", new_test)]:
        ph = sum(1 for d in split if sum(d["label"]) > 0)
        no = len(split) - ph
        print(f"  {name:5s}: {len(split):4d}개  (피싱 {ph} / 정상 {no})")

    # ── 백업 후 저장 ──────────────────────────────────────────────────
    for fname in ["train_ml.json", "val_ml.json", "test_ml.json"]:
        src = DATA_DIR / fname
        src.rename(DATA_DIR / fname.replace(".json", "_backup.json"))

    (DATA_DIR / "train_ml.json").write_text(
        json.dumps(new_train, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "val_ml.json").write_text(
        json.dumps(new_val, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA_DIR / "test_ml.json").write_text(
        json.dumps(new_test, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n저장 완료. 기존 파일은 *_backup.json으로 보존됨.")
    print("다음 단계: python model_build/train.py")


if __name__ == "__main__":
    main()
