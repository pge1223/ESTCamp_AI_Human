"""설정 일관성 검수 (F-QC-01).

확립된 설정(세계관·캐릭터·이전 사건·검색된 관련 기억)과 새 내용을 LLM으로 비교해
모순을 찾는다. RAG가 "기억해서 주입"이라면, 이건 "기억과 대조해서 검수"하는 단계다.

토큰을 추가로 쓰므로(검수 1회 = LLM 1콜) 채팅에서는 기본 off, 필요 시(최종 검수 등)만 호출한다.
검수 실패는 '통과(consistent=True)'로 흡수해 사용자 흐름을 막지 않는다.
"""
import re
import json
import logging

from app.services import llm
from app.prompts import CONSISTENCY_SYSTEM

logger = logging.getLogger(__name__)

_PASS = {"consistent": True, "violations": []}


async def check(facts: str, text: str) -> dict:
    """[확립된 설정]facts 와 [검수 대상]text 를 비교해 모순을 반환.

    반환: {"consistent": bool, "violations": [{"established","conflict","severity"}, ...]}
    """
    if not (facts or "").strip() or not (text or "").strip():
        return dict(_PASS)

    prompt = f"[확립된 설정]\n{facts}\n\n[검수 대상]\n{text}"
    try:
        raw = await llm.generate(
            CONSISTENCY_SYSTEM,
            [{"role": "user", "parts": [{"text": prompt}]}],
            json_mode=True,
        )
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
        data = json.loads(cleaned)
        violations = data.get("violations") or []
        # consistent 가 명시적으로 false 거나 위반이 있으면 불일치
        consistent = bool(data.get("consistent", True)) and not violations
        return {"consistent": consistent, "violations": violations}
    except Exception as e:  # noqa: BLE001 - 검수 실패는 통과 처리
        logger.warning("일관성 검수 실패(통과 처리): %s", e)
        return dict(_PASS)
