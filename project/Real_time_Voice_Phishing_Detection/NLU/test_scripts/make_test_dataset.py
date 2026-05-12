"""
실전 시뮬레이션 테스트 데이터셋 생성기

mixed_test_01/02  (기존): 일상대화 + K쇼핑 콜센터 + 피싱(train_ml)
mixed_test_03     (신규): 비K쇼핑 콜센터 zip + 피싱(test_ml) — 오염 없는 벤치마크
mixed_test_v4     (v4):  v4 test_* 파일 전부 — 피싱 303 + 정상 4087

실행: python test_scripts/make_test_dataset.py [--mode v4]
  --mode v4  : mixed_test_v4.json 생성 (기본값)
  --mode 03  : mixed_test_03.json만 생성
  --mode all : 01/02/03 전체 생성
"""
import argparse
import json
import random
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_HERE        = Path(__file__).parent
_AI_ANALYZER = _HERE.parent

import sys
sys.path.insert(0, str(_AI_ANALYZER))
from config import DATA_DIR

NORMAL_DIR   = _HERE / "data/raw/normal"
AS_DIR       = _HERE / "data/raw/as"
NEW_AS_DIR   = AS_DIR / "01.데이터"
OUTPUT_DIR   = _HERE / "data/mixed"

PHISHING_TRAIN = DATA_DIR / "train_ml.json"
PHISHING_TEST  = DATA_DIR / "test_ml.json"

AS_SAMPLE_SIZE       = 1000
AS_MIN_CHAR          = 10
PHISHING_RATIO_RANGE = (0.04, 0.09)
SEED_BASE            = 42

# K쇼핑은 v3 학습 데이터와 도메인 겹침 → 제외
EXCLUDE_DOMAINS = {"K쇼핑", "쇼핑"}


# ── 로더 ─────────────────────────────────────────────────────────────────────

def load_normal_sentences() -> list[dict]:
    """normal 폴더: script.normalized 리스트 구조."""
    seen: set[str] = set()
    result: list[dict] = []
    for json_file in sorted(NORMAL_DIR.glob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        for item in data:
            for sent in item.get("script", {}).get("normalized", []):
                sent = sent.strip()
                if sent and sent not in seen:
                    seen.add(sent)
                    result.append({"text": sent, "is_phishing": False,
                                   "label": [0, 0, 0], "source": "normal"})
    return result


def load_as_sentences(sample_size: int, seed: int) -> list[dict]:
    """as 폴더 flat JSON (기존 K쇼핑 업무처리): 01/02용."""
    text_fields = ["고객질문(요청)", "상담사질문(요청)"]
    seen: set[str] = set()
    pool: list[str] = []

    for json_file in sorted(AS_DIR.glob("*.json")):
        try:
            with open(json_file, encoding="cp949") as f:
                data = json.load(f)
        except UnicodeDecodeError:
            with open(json_file, encoding="utf-8", errors="replace") as f:
                data = json.load(f)

        for record in data:
            for field in text_fields:
                text = record.get(field, "").strip()
                if len(text) >= AS_MIN_CHAR and text not in seen:
                    seen.add(text)
                    pool.append(text)

    rng = random.Random(seed)
    sampled = rng.sample(pool, min(sample_size, len(pool)))
    return [{"text": t, "is_phishing": False, "label": [0, 0, 0], "source": "as"}
            for t in sampled]


def load_zip_as_sentences(sample_size: int, seed: int) -> list[dict]:
    """01.데이터 zip 파일에서 비K쇼핑 콜센터 문장 추출 (mixed_test_03용)."""
    text_fields = ["고객질문(요청)", "상담사질문(요청)", "고객답변", "상담사답변"]
    seen: set[str] = set()
    pool: list[str] = []

    for zip_path in sorted(NEW_AS_DIR.rglob("*.zip")):
        # 경로명에 쇼핑 포함이면 스킵 (K쇼핑 디렉토리)
        if any(d in zip_path.parts for d in ["쇼핑"]) or "쇼핑" in zip_path.name:
            continue
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for entry in zf.namelist():
                    if not entry.endswith(".json"):
                        continue
                    raw = zf.read(entry)
                    for enc in ("utf-8", "cp949", "euc-kr"):
                        try:
                            content = raw.decode(enc)
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        continue
                    try:
                        data = json.loads(content)
                    except json.JSONDecodeError:
                        continue
                    for record in data:
                        if record.get("도메인", "") in EXCLUDE_DOMAINS:
                            continue
                        for field in text_fields:
                            text = record.get(field, "").strip()
                            if len(text) >= AS_MIN_CHAR and text not in seen:
                                seen.add(text)
                                pool.append(text)
        except Exception:
            continue

    rng = random.Random(seed)
    sampled = rng.sample(pool, min(sample_size, len(pool)))
    return [{"text": t, "is_phishing": False, "label": [0, 0, 0], "source": "new_as"}
            for t in sampled]


def load_phishing_samples(path: Path) -> list[dict]:
    """지정 경로 JSON에서 피싱 샘플(label 합계 > 0)만 추출."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {"text": d["text"], "is_phishing": True,
         "label": d["label"], "source": "phishing"}
        for d in data if sum(d["label"]) > 0
    ]


def load_v4_test_data() -> tuple[list[dict], list[dict]]:
    """v4 test_* 파일에서 피싱/정상 분리 로딩."""
    phishing_file = DATA_DIR / "test_phishing_augmented_data.json"
    normal_files = [
        ("test_callcenter_finance.json",  "callcenter_finance"),
        ("test_normal_callcenter.json",   "normal_callcenter"),
        ("test_normal_tts.json",          "normal_tts"),
    ]

    phishing: list[dict] = []
    raw = json.loads(phishing_file.read_text(encoding="utf-8"))
    for d in raw:
        if sum(d["label"]) > 0:
            phishing.append({"text": d["text"], "is_phishing": True,
                             "label": d["label"],
                             "source": d.get("source", "phishing")})

    normal: list[dict] = []
    for fname, src in normal_files:
        raw = json.loads((DATA_DIR / fname).read_text(encoding="utf-8"))
        for d in raw:
            normal.append({"text": d["text"], "is_phishing": False,
                           "label": [0, 0, 0], "source": src})

    return phishing, normal


# ── 데이터셋 생성 ─────────────────────────────────────────────────────────────

def make_dataset(normal: list[dict], phishing: list[dict],
                 seed: int, ratio: float) -> list[dict]:
    rng = random.Random(seed)
    n_phishing = max(1, round(len(normal) * ratio / (1 - ratio)))
    sampled_phishing = rng.sample(phishing, min(n_phishing, len(phishing)))
    combined = normal + sampled_phishing
    rng.shuffle(combined)
    for idx, item in enumerate(combined):
        item["id"] = idx
    return combined


def _label_counts(dataset: list[dict]) -> dict[str, int]:
    keys = ["기관사칭", "금전요구", "개인정보"]
    counts = {k: 0 for k in keys}
    for d in dataset:
        if d["is_phishing"]:
            for i, k in enumerate(keys):
                counts[k] += d["label"][i]
    return counts


def _print_and_save(fname: str, dataset: list[dict]) -> None:
    out_path = OUTPUT_DIR / fname
    out_path.write_text(json.dumps(dataset, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    n_phishing = sum(1 for d in dataset if d["is_phishing"])
    n_normal   = len(dataset) - n_phishing
    ratio      = n_phishing / len(dataset)
    label_cnt  = _label_counts(dataset)
    print(f"  [{fname}]  총 {len(dataset)}개")
    print(f"    정상  : {n_normal}개")
    print(f"    피싱  : {n_phishing}개  (비율 {ratio:.1%})")
    print(f"    카테고리: 기관사칭 {label_cnt['기관사칭']} / "
          f"금전요구 {label_cnt['금전요구']} / 개인정보 {label_cnt['개인정보']}")
    print(f"    저장  : {out_path}")
    print()


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="v4",
                        choices=["v4", "03", "all"],
                        help="v4=mixed_test_v4만 생성(기본), 03=mixed_test_03만, all=01/02/03 전체")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print("  원본 데이터 로딩 중...")
    print("=" * 65)

    if args.mode == "all":
        # 기존 01/02 생성
        normal_sentences = load_normal_sentences()
        as_sentences     = load_as_sentences(AS_SAMPLE_SIZE, seed=SEED_BASE)
        all_normal       = normal_sentences + as_sentences
        phishing_train   = load_phishing_samples(PHISHING_TRAIN)

        print(f"  일상대화 (normal)  : {len(normal_sentences):>5}개")
        print(f"  콜센터   (as/flat) : {len(as_sentences):>5}개")
        print(f"  정상 합계          : {len(all_normal):>5}개")
        print(f"  피싱 (train_ml)    : {len(phishing_train):>5}개")
        print()

        rng_ratio = random.Random(SEED_BASE)
        for i in range(1, 3):
            ratio   = rng_ratio.uniform(*PHISHING_RATIO_RANGE)
            seed    = SEED_BASE + i
            dataset = make_dataset(all_normal, phishing_train, seed, ratio)
            _print_and_save(f"mixed_test_{i:02d}.json", dataset)

    if args.mode == "v4":
        print("=" * 65)
        print("  v4 test 데이터 로딩 중...")
        print("=" * 65)
        phishing_v4, normal_v4 = load_v4_test_data()
        print(f"  피싱 (test_phishing_augmented_data): {len(phishing_v4):>5}개")
        print(f"  정상 - callcenter_finance          : {sum(1 for d in normal_v4 if d['source']=='callcenter_finance'):>5}개")
        print(f"  정상 - normal_callcenter           : {sum(1 for d in normal_v4 if d['source']=='normal_callcenter'):>5}개")
        print(f"  정상 - normal_tts                  : {sum(1 for d in normal_v4 if d['source']=='normal_tts'):>5}개")
        print(f"  정상 합계                          : {len(normal_v4):>5}개")
        print()

        rng = random.Random(SEED_BASE)
        combined = phishing_v4 + normal_v4
        rng.shuffle(combined)
        for idx, item in enumerate(combined):
            item["id"] = idx
        _print_and_save("mixed_test_v4.json", combined)
        print("완료.")
        return

    # mixed_test_03: 비K쇼핑 zip + 피싱(test_ml)
    print("  zip 콜센터 로딩 중 (비K쇼핑)... ", end="", flush=True)
    zip_normal    = load_zip_as_sentences(AS_SAMPLE_SIZE, seed=SEED_BASE)
    phishing_test = load_phishing_samples(PHISHING_TEST)

    print(f"완료")
    print(f"  콜센터 zip (비K쇼핑): {len(zip_normal):>5}개")
    print(f"  피싱 (test_ml)      : {len(phishing_test):>5}개")
    print()

    rng_ratio = random.Random(SEED_BASE + 3)
    ratio     = rng_ratio.uniform(*PHISHING_RATIO_RANGE)
    dataset03 = make_dataset(zip_normal, phishing_test, seed=SEED_BASE + 3, ratio=ratio)
    _print_and_save("mixed_test_03.json", dataset03)

    print("완료.")


if __name__ == "__main__":
    main()