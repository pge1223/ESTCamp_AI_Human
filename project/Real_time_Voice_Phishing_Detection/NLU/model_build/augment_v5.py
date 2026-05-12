"""
보이스피싱 데이터 증강 스크립트 (v5)
탐문형 피싱 패턴 집중 보강

흐름:
  0단계: data/v4/phishing_augmented_data.json 로드 (기존 1,510개)
  1단계: transcripts.json 탐문형 80개 필터링 → 시드로 사용
          (data/v3/_transcripts_classified.json 있으면 재사용, 없으면 GPT 분류)
  2단계: KBS_001 탐문형 대화 + transcripts 탐문형을 시드로
          탐문형 집중 증강 500개 (라벨별)
  3단계: 전체 합치고 7:1:2 분할 → data/v5/ 저장

Colab 실행:
  !pip install openai tqdm scikit-learn
  !python model_build/augment_v5.py

로컬 실행:
  uv run python model_build/augment_v5.py
"""

import json
import os
import sys
import time
import random
from collections import Counter
from pathlib import Path

from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:
    print("pip install openai")
    sys.exit(1)

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 경로 설정 ─────────────────────────────────────────────────────────
# Colab 사용 시 BASE 경로를 수정하세요
# 예: BASE = Path("/content/drive/MyDrive/ai_analyzer")
#BASE        = Path(__file__).parent.parent
BASE  = Path("/content/drive/MyDrive/VoicePhishingData")
DATA_RAW    = BASE / "data/raw"
DATA_V3     = BASE / "data/v3"
DATA_V4     = BASE / "data/v4"
DATA_OUT    = BASE / "data/v5"
DATA_OUT.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH      = DATA_OUT / "phishing_augmented_data.json"
CLASSIFY_CACHE   = DATA_V3  / "_transcripts_classified.json"   # v3 분류 결과 재사용

# ── 설정 ──────────────────────────────────────────────────────────────
MODEL      = "gpt-4o-mini"
LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]
BATCH_SIZE = 10
SLEEP_SEC  = 0.5
RETRY_LIMIT = 3

# 탐문형 키워드 (시드 필터링용)
TAMUN_KEYWORDS = [
    "있으신가요", "아니신가요", "말씀이시죠", "그렇군요", "그러시군요",
    "혹시", "없으신가요", "분실", "빌려", "적이 있", "아니신지",
    "확인해보", "진술", "맞으시죠", "기억나시",
]

# 탐문형 집중 쿼터 (v4 기존 데이터에 추가로 생성할 개수)
QUOTA_V5: dict[tuple, int] = {
    (1, 0, 0): 150,   # 탐문형 기관사칭만  (신원확인 질문, 사건연루 탐문)
    (1, 0, 1): 150,   # 탐문형 기관사칭+개인정보 (명의도용/신분증 분실 확인)
    (1, 1, 1): 200,   # 탐문형 복합 (금융자산 현황 탐문 → 금전요구 연결)
}
# 총 500개 신규 생성


# ── API ───────────────────────────────────────────────────────────────
def get_client() -> OpenAI:
    key = os.getenv("OPENAI_API_KEY") or input("OpenAI API Key: ").strip()
    return OpenAI(api_key=key)


def chat(client: OpenAI, prompt: str, temperature: float = 0.9) -> dict | None:
    for attempt in range(RETRY_LIMIT):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}/{RETRY_LIMIT}] {e} — {wait}s 대기")
            time.sleep(wait)
    return None


# ── 0단계: v4 기존 데이터 로드 ────────────────────────────────────────
def load_v4_base() -> list[dict]:
    """v4 phishing_augmented_data.json 로드. 없으면 train/val/test 합산."""
    full = DATA_V4 / "phishing_augmented_data.json"
    if full.exists():
        data = json.loads(full.read_text(encoding="utf-8"))
        print(f"[0단계] v4 전체 피싱 데이터 로드: {len(data)}개")
        return data

    # 없으면 train + val + test 합산
    all_data: list[dict] = []
    for split in ["train", "val", "test"]:
        f = DATA_V4 / f"{split}_phishing_augmented_data.json"
        if f.exists():
            all_data.extend(json.loads(f.read_text(encoding="utf-8")))
    print(f"[0단계] v4 split 합산 로드: {len(all_data)}개")
    return all_data


# ── 1단계: transcripts 탐문형 시드 준비 ──────────────────────────────
def load_transcripts_tamun(client: OpenAI) -> list[dict]:
    """
    transcripts.json 탐문형 패턴 필터링.
    v3 분류 캐시 있으면 재사용, 없으면 GPT 멀티라벨 분류 후 캐시 저장.
    """
    # v3 캐시 재사용
    if CLASSIFY_CACHE.exists():
        classified = json.loads(CLASSIFY_CACHE.read_text(encoding="utf-8"))
        print(f"[1단계] v3 분류 캐시 재사용: {len(classified)}개")
    else:
        print("[1단계] transcripts.json GPT 멀티라벨 분류 시작")
        transcripts = json.loads((DATA_RAW / "transcripts.json").read_text(encoding="utf-8"))
        classified = []
        for item in tqdm(transcripts):
            text = item.get("text", "").strip()
            if len(text) < 30:
                continue
            prompt = f"""보이스피싱 통화 텍스트를 분석해 카테고리를 판단하세요.

카테고리:
- 기관사칭: 검찰·경찰·금감원·은행 등 공공기관 사칭
- 금전요구: 계좌이체·현금·공탁금 등 금전 요구
- 개인정보: 주민번호·카드번호·OTP·신분증 등 개인정보 요구

텍스트:
{text[:1500]}

JSON으로만 응답:
{{"기관사칭": 0또는1, "금전요구": 0또는1, "개인정보": 0또는1}}"""
            result = chat(client, prompt, temperature=0)
            label = [1, 0, 0] if result is None else [
                int(bool(result.get("기관사칭", 0))),
                int(bool(result.get("금전요구", 0))),
                int(bool(result.get("개인정보", 0))),
            ]
            classified.append({"text": text, "label": label, "source": "transcripts_raw"})
            time.sleep(SLEEP_SEC)

        CLASSIFY_CACHE.write_text(json.dumps(classified, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[1단계] 분류 완료 + 캐시 저장: {len(classified)}개")

    # 탐문형 키워드 필터링
    tamun = [
        d for d in classified
        if any(kw in d["text"] for kw in TAMUN_KEYWORDS)
    ]
    print(f"[1단계] 탐문형 패턴 필터링: {len(tamun)}개 / {len(classified)}개")
    return tamun


# ── KBS_001 탐문형 시드 추출 ──────────────────────────────────────────
def load_kbs_tamun_seed() -> str:
    """KBS_001 (검1선) 전체 대화를 탐문형 시드 텍스트로 반환."""
    kbs_data = json.loads(
        (DATA_RAW / "kbs_voicephishing_dataset.json").read_text(encoding="utf-8")
    )
    for scenario in kbs_data:
        if scenario["scenario_id"] == "KBS_001":
            turns = [
                d for d in scenario.get("dialogue", [])
                if isinstance(d, dict) and d.get("text")
            ]
            dialogue_text = "\n".join(
                f"[{d.get('role', d.get('speaker', ''))}]: {d.get('text', '')}"
                for d in turns
            )
            print(f"[KBS 시드] KBS_001 (검1선) 로드: {len(turns)}턴")
            return dialogue_text
    print("[KBS 시드] KBS_001 없음")
    return ""


# ── 2단계: 탐문형 집중 증강 ──────────────────────────────────────────
def augment_tamun_batch(
    client: OpenAI,
    label: list[int],
    seed_text: str,
    n: int,
    seed_type: str,
) -> list[str]:
    """탐문형 스타일 시드로 n개 증강."""
    label_desc = "+".join(col for col, v in zip(LABEL_COLS, label) if v)

    prompt = f"""다음은 실제 보이스피싱 {seed_type}입니다.
카테고리: {label_desc}  |  라벨: {label}

[참고 텍스트]
{seed_text[:1800]}

위를 참고해 【탐문형 피싱 발화】 {n}개를 생성하세요.

탐문형이란:
- 피해자에게 직접 금전을 요구하거나 명령하는 대신
- 사실 확인 질문, 상황 탐문, 공감 유도 등으로 신뢰를 쌓는 단계
- 예: "본인이 개설한 적이 없다는 말씀이시죠?",
       "혹시 신분증 분실한 적은 있으신가요?",
       "지금 사용 중이신 금융권이 어떻게 되십니까?"

규칙:
- 각 텍스트는 충분히 다른 상황/표현 사용
- 실제 통화처럼 자연스러운 구어체
- 길이: 80~400자
- 탐문·확인·공감 어조 포함 (질문형 종결어미 권장)
- 라벨 {label} 의미 정확히 유지
- STT 특성 반영 가능

JSON: {{"samples": [{{"text": "..."}}]}} 형식으로 {n}개 응답"""

    result = chat(client, prompt)
    if result is None:
        return []
    samples = result.get("samples", [])
    return [s["text"] for s in samples if isinstance(s, dict) and s.get("text")]


def augment_by_quota_v5(
    client: OpenAI,
    kbs_seed: str,
    tamun_transcripts: list[dict],
    existing: list[dict],
) -> list[dict]:
    """탐문형 쿼터에 맞게 증강."""
    results = list(existing)
    current = Counter(tuple(d["label"]) for d in results)

    print("\n[2단계] 탐문형 집중 증강 시작")
    for label_key, quota in QUOTA_V5.items():
        label      = list(label_key)
        label_desc = "+".join(LABEL_COLS[i] for i, v in enumerate(label_key) if v)
        need       = quota

        print(f"\n  [{label_desc}] {need}개 생성 예정")

        # 시드풀: KBS_001 + 해당 라벨 탐문형 transcripts
        tamun_seeds = [
            d["text"] for d in tamun_transcripts
            if tuple(d["label"]) == label_key
        ]
        seed_pool = []
        if kbs_seed:
            seed_pool.append(("KBS_001 검1선 탐문 시나리오", kbs_seed))
        for t in tamun_seeds:
            seed_pool.append(("실제 보이스피싱 통화 STT (탐문형)", t))

        if not seed_pool:
            # 시드 없어도 KBS 기반으로 생성
            seed_pool = [("KBS_001 검1선 탐문 시나리오", kbs_seed or "탐문형 보이스피싱")]

        generated = 0
        seed_idx  = 0
        pbar      = tqdm(total=need, desc=f"  {label_desc}")

        while generated < need:
            seed_type, seed_text = seed_pool[seed_idx % len(seed_pool)]
            batch_n = min(BATCH_SIZE, need - generated)

            texts = augment_tamun_batch(client, label, seed_text, batch_n, seed_type)
            for text in texts:
                results.append({
                    "text":   text,
                    "label":  label,
                    "source": "tamun_aug_v5",
                })
            generated += len(texts)
            seed_idx  += 1
            pbar.update(len(texts))
            time.sleep(SLEEP_SEC)

            # 50개마다 중간 저장
            if len(results) % 50 == 0:
                OUTPUT_PATH.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
                )

        pbar.close()

    return results


# ── 3단계: 분할 저장 ──────────────────────────────────────────────────
def split_and_save(data: list[dict]) -> None:
    """7:1:2 분할 후 data/v5/ 저장."""
    from sklearn.model_selection import train_test_split

    random.seed(42)
    random.shuffle(data)

    train, temp = train_test_split(data, test_size=0.3, random_state=42)
    val, test   = train_test_split(temp, test_size=0.667, random_state=42)
    # 0.3 × 0.667 ≈ 0.2 → 7:1:2

    for fname, split_data in [
        ("train_phishing_augmented_data.json", train),
        ("val_phishing_augmented_data.json",   val),
        ("test_phishing_augmented_data.json",  test),
    ]:
        path = DATA_OUT / fname
        path.write_text(json.dumps(split_data, ensure_ascii=False, indent=2), encoding="utf-8")
        phishing = sum(1 for d in split_data if any(d["label"]))
        print(f"  {fname}: {len(split_data)}개 (피싱 {phishing})")


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> None:
    client = get_client()

    # 기존 진행 결과 로드 (중단 후 재실행 지원)
    existing_results: list[dict] = []
    if OUTPUT_PATH.exists():
        existing_results = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        print(f"기존 진행 결과 로드: {len(existing_results)}개")

    # 0단계: v4 피싱 데이터
    v4_base = load_v4_base()

    # 이미 v4 데이터가 포함된 경우 중복 방지
    if not existing_results:
        existing_results = v4_base

    # 1단계: transcripts 탐문형 시드
    tamun_transcripts = load_transcripts_tamun(client)

    # KBS_001 탐문형 시드
    kbs_seed = load_kbs_tamun_seed()

    # 2단계: 탐문형 증강
    results = augment_by_quota_v5(client, kbs_seed, tamun_transcripts, existing_results)

    # 최종 저장
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 결과 요약
    new_count = len(results) - len(v4_base)
    print(f"\n{'='*55}")
    print(f"  v4 기존: {len(v4_base)}개")
    print(f"  v5 신규: {new_count}개  (탐문형 집중)")
    print(f"  v5 합계: {len(results)}개")
    print(f"  저장:    {OUTPUT_PATH}")
    print(f"{'='*55}")

    dist = Counter(tuple(d["label"]) for d in results)
    print("\n전체 라벨 분포:")
    for label_key, cnt in sorted(dist.items()):
        desc = "+".join(LABEL_COLS[i] for i, v in enumerate(label_key) if v) or "정상"
        print(f"  {desc:30s}: {cnt:4d}개")

    src_dist = Counter(d.get("source", "unknown") for d in results)
    print("\n소스 분포:")
    for src, cnt in sorted(src_dist.items(), key=lambda x: -x[1]):
        print(f"  {src:25s}: {cnt}개")

    # 3단계: 분할 저장
    print("\n[3단계] 7:1:2 분할 저장")
    split_and_save(results)

    print("\n완료! data/v5/ 피싱 데이터 준비됐습니다.")
    print("다음: train_colab.py에서 DATA_VERSION = 'v5' 로 설정 후 학습")


if __name__ == "__main__":
    main()
