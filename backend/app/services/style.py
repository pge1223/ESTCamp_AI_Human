"""문체 RAG — 작가별 문체 예시를 의미 검색해 소설 변환 few-shot으로 제공.

고정 문체 프롬프트(build_novel_system)에 더해, 현재 장면과 가장 비슷한 '그 작가의
실제 예시 문장'을 검색해 주입하면 문체 재현도가 올라간다. (자체 문체 모델 없이 문체를 '산다')

샘플은 app/data/style_samples.json 에 작가별로 모아두며, 팀이 자유롭게 추가한다.
임베딩/코사인은 memory 모듈 헬퍼를 재사용한다(RAG 인프라 공유).
"""
import json
import logging
from pathlib import Path

from app.services import memory  # _embed_cached, _cosine 재사용

logger = logging.getLogger(__name__)

_SAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "style_samples.json"


def _load_samples() -> dict[str, list[str]]:
    try:
        raw = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, list)}
    except Exception as e:  # noqa: BLE001
        logger.warning("문체 샘플 로드 실패: %s", e)
        return {}


_SAMPLES = _load_samples()


async def retrieve_examples(persona_id: str, query: str, k: int = 3) -> list[str]:
    """persona_id 작가의 문체 예시 중 query(장면)와 가장 가까운 top-K를 반환."""
    samples = _SAMPLES.get(persona_id) or []
    if not samples or not (query or "").strip():
        return samples[:k]  # 검색 불가 시 앞에서 k개라도 제공
    try:
        qv = (await memory._embed_cached([query]))[0]
        svs = await memory._embed_cached(samples)
    except Exception as e:  # noqa: BLE001 - 임베딩 실패 시 앞에서 k개 폴백
        logger.warning("문체 예시 임베딩 실패(앞에서 %d개 사용): %s", k, e)
        return samples[:k]
    scored = sorted(
        ((s, memory._cosine(qv, v)) for s, v in zip(samples, svs) if v),
        key=lambda x: x[1],
        reverse=True,
    )
    return [s for s, _ in scored[:k]]
