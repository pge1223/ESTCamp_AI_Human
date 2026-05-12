"""
보이스피싱 데이터 증강 스크립트 (v3)

흐름:
  1단계: transcripts.json 104개 → GPT 멀티라벨 분류
  2단계: 분류된 transcripts + kbs 시나리오를 시드로 카테고리 조합별 쿼터 증강

출력: data/v3/phishing_augmented_data.json

실행 (Colab):
  !pip install openai tqdm
  !python model_build/augment_v3.py

실행 (로컬):
  uv run python model_build/augment_v3.py
"""

import json
import os
import sys
import time
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
# Colab 사용 시 아래 BASE 경로를 수정하세요
BASE        = Path(__file__).parent.parent
DATA_RAW    = BASE / "data/raw"
DATA_OUT    = BASE / "data/v3"
DATA_OUT.mkdir(parents=True, exist_ok=True)

OUTPUT_PATH   = DATA_OUT / "phishing_augmented_data.json"
CLASSIFY_PATH = DATA_OUT / "_transcripts_classified.json"   # 1단계 중간 저장

# ── 증강 설정 ─────────────────────────────────────────────────────────
MODEL      = "gpt-4o-mini"
LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]

# 카테고리 조합별 목표 개수 (합계 2,310개)
QUOTA: dict[tuple, int] = {
    (1, 0, 0): 200,   # 기관사칭만
    (0, 1, 0): 200,   # 금전요구만
    (0, 0, 1): 200,   # 개인정보만
    (1, 1, 0): 200,   # 기관사칭 + 금전요구
    (1, 0, 1): 200,   # 기관사칭 + 개인정보
    (0, 1, 1): 200,   # 금전요구 + 개인정보
    (1, 1, 1): 310,   # 전부 (실제 피싱 대부분이 복합)
}

BATCH_SIZE    = 10    # 1회 API 호출당 생성 개수
SLEEP_SEC     = 0.5  # 호출 간 대기
RETRY_LIMIT   = 3


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


# ── 1단계: 멀티라벨 분류 ──────────────────────────────────────────────
def classify_transcripts(client: OpenAI) -> list[dict]:
    """transcripts.json 104개를 멀티라벨로 분류. 기존 결과 있으면 재사용."""
    if CLASSIFY_PATH.exists():
        classified = json.loads(CLASSIFY_PATH.read_text(encoding="utf-8"))
        print(f"[1단계] 기존 분류 결과 로드: {len(classified)}개")
        return classified

    transcripts = json.loads((DATA_RAW / "transcripts.json").read_text(encoding="utf-8"))
    print(f"\n[1단계] transcripts {len(transcripts)}개 멀티라벨 분류 시작")

    classified = []
    for i, item in enumerate(tqdm(transcripts)):
        text = item.get("text", "").strip()
        if len(text) < 30:
            continue

        prompt = f"""보이스피싱 통화 텍스트를 분석해 카테고리를 판단하세요.

카테고리 정의:
- 기관사칭: 검찰·경찰·금감원·은행·공공기관 등을 사칭
- 금전요구: 계좌이체·현금·공탁금·송금 등 금전 요구
- 개인정보: 주민번호·카드번호·비밀번호·OTP 등 개인정보 요구

텍스트:
{text[:1500]}

JSON으로만 응답 (설명 없이):
{{"기관사칭": 0또는1, "금전요구": 0또는1, "개인정보": 0또는1}}"""

        result = chat(client, prompt, temperature=0)
        if result is None:
            label = [1, 0, 0]
        else:
            label = [
                int(bool(result.get("기관사칭", 0))),
                int(bool(result.get("금전요구", 0))),
                int(bool(result.get("개인정보", 0))),
            ]

        classified.append({"text": text, "label": label, "source": "transcripts_raw"})
        time.sleep(SLEEP_SEC)

        if (i + 1) % 20 == 0:
            CLASSIFY_PATH.write_text(
                json.dumps(classified, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    CLASSIFY_PATH.write_text(
        json.dumps(classified, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dist = Counter(tuple(d["label"]) for d in classified)
    print("[1단계] 분류 완료:")
    for label_key, cnt in sorted(dist.items()):
        desc = "+".join(LABEL_COLS[i] for i, v in enumerate(label_key) if v) or "정상"
        print(f"  {desc:30s}: {cnt}개")

    return classified


# ── kbs 시드 준비 ─────────────────────────────────────────────────────
def load_kbs_seeds() -> list[dict]:
    """kbs_voicephishing_dataset.json에서 실제 대화가 있는 시나리오만 추출."""
    kbs_data = json.loads(
        (DATA_RAW / "kbs_voicephishing_dataset.json").read_text(encoding="utf-8")
    )
    seeds = []
    for scenario in kbs_data:
        dialogue = scenario.get("dialogue", [])
        # flow 구조(step/key_phrases)나 빈 대화는 제외
        turns = [
            d for d in dialogue
            if isinstance(d, dict) and d.get("text")
        ]
        if not turns:
            continue

        dialogue_text = "\n".join(
            f"[{d.get('role', d.get('speaker', ''))}]: {d.get('text', '')}"
            for d in turns
        )
        seeds.append({
            "type":     scenario.get("scenario_type", ""),
            "label":    scenario.get("label", [1, 0, 0]),
            "dialogue": dialogue_text,
        })

    print(f"[kbs 시드] {len(seeds)}개 시나리오 로드")
    return seeds


# ── 2단계: 카테고리 조합별 쿼터 증강 ─────────────────────────────────
def build_seed_pool(
    classified: list[dict],
    kbs_seeds: list[dict],
) -> dict[tuple, list[str]]:
    """라벨 조합별로 시드 텍스트를 분류."""
    pool: dict[tuple, list[str]] = {k: [] for k in QUOTA}

    # transcripts
    for item in classified:
        key = tuple(item["label"])
        if key in pool:
            pool[key].append(item["text"])

    # kbs (대화 전체를 시드로)
    for seed in kbs_seeds:
        key = tuple(seed["label"])
        if key in pool:
            pool[key].append(seed["dialogue"])

    for key, texts in pool.items():
        desc = "+".join(LABEL_COLS[i] for i, v in enumerate(key) if v)
        print(f"  [{desc:30s}] 시드 {len(texts)}개")

    return pool


def augment_batch(
    client: OpenAI,
    label: list[int],
    seed_text: str,
    n: int,
    is_kbs: bool = False,
) -> list[str]:
    """시드 텍스트 하나로 n개 증강. 생성된 text 리스트 반환."""
    label_desc = "+".join(col for col, v in zip(LABEL_COLS, label) if v) or "정상"
    seed_type  = "보이스피싱 시나리오 대화" if is_kbs else "실제 보이스피싱 통화 STT"

    prompt = f"""다음은 {seed_type}입니다.
카테고리: {label_desc}  |  라벨: {label}

[참고 텍스트]
{seed_text[:1800]}

위를 참고해 카테고리({label_desc})에 해당하는 보이스피싱 발화 {n}개를 생성하세요.

규칙:
- 각 텍스트는 충분히 다르게 변형 (표현·상황·구체적 내용 다양화)
- 실제 통화처럼 자연스러운 구어체
- 길이: 80~500자
- STT 특성 반영 가능 (필러, 구어체 어미 등)
- 라벨 {label} 의미를 정확히 유지

JSON: {{"samples": [{{"text": "..."}}]}} 형식으로 {n}개 응답"""

    result = chat(client, prompt)
    if result is None:
        return []
    samples = result.get("samples", [])
    return [s["text"] for s in samples if isinstance(s, dict) and s.get("text")]


def augment_by_quota(
    client: OpenAI,
    pool: dict[tuple, list[str]],
    existing: list[dict],
) -> list[dict]:
    """쿼터에 맞게 증강. 기존 결과 있으면 이어서 진행."""
    results = list(existing)

    # 현재 카테고리별 개수 파악
    current = Counter(tuple(d["label"]) for d in results)

    print("\n[2단계] 카테고리별 증강 시작")
    for label_key, quota in QUOTA.items():
        label      = list(label_key)
        label_desc = "+".join(LABEL_COLS[i] for i, v in enumerate(label_key) if v)
        seeds      = pool.get(label_key, [])
        need       = quota - current.get(label_key, 0)

        if need <= 0:
            print(f"  [{label_desc:30s}] 이미 완료 ({current.get(label_key,0)}/{quota})")
            continue
        if not seeds:
            print(f"  [{label_desc:30s}] 시드 없음 — 건너뜀")
            continue

        print(f"  [{label_desc:30s}] {need}개 필요 (시드 {len(seeds)}개 사용)")

        generated = 0
        seed_idx  = 0
        pbar      = tqdm(total=need, desc=f"  {label_desc}")

        while generated < need:
            seed = seeds[seed_idx % len(seeds)]
            is_kbs = "\n[" in seed  # kbs 대화는 "[역할]: " 형식 포함
            batch_n = min(BATCH_SIZE, need - generated)

            texts = augment_batch(client, label, seed, batch_n, is_kbs=is_kbs)
            for text in texts:
                results.append({
                    "text":   text,
                    "label":  label,
                    "source": "kbs_aug" if is_kbs else "transcripts_aug",
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


# ── 메인 ──────────────────────────────────────────────────────────────
def main() -> None:
    client = get_client()

    # 기존 진행 결과 로드
    existing: list[dict] = []
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        print(f"기존 진행 결과 로드: {len(existing)}개")

    # 1단계
    classified = classify_transcripts(client)

    # kbs 시드
    kbs_seeds = load_kbs_seeds()

    # 시드풀 구성
    print("\n[시드풀 구성]")
    pool = build_seed_pool(classified, kbs_seeds)

    # 2단계
    results = augment_by_quota(client, pool, existing)

    # 최종 저장
    OUTPUT_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 결과 요약
    print(f"\n{'='*55}")
    print(f"  총 {len(results)}개 생성 완료")
    print(f"  저장: {OUTPUT_PATH}")
    print(f"{'='*55}")

    dist = Counter(tuple(d["label"]) for d in results)
    print("\n라벨 분포:")
    for label_key, cnt in sorted(dist.items()):
        desc  = "+".join(LABEL_COLS[i] for i, v in enumerate(label_key) if v) or "정상"
        quota = QUOTA.get(label_key, "-")
        print(f"  {desc:30s}: {cnt:4d}개  (목표 {quota})")

    src_dist = Counter(d["source"] for d in results)
    print("\n소스 분포:")
    for src, cnt in src_dist.items():
        print(f"  {src:25s}: {cnt}개")


if __name__ == "__main__":
    main()
