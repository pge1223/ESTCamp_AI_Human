"""
services/tts.py
----------------
F-AV-02 첫 문장 낭독 — ElevenLabs TTS 연동.

- 모델: eleven_multilingual_v2 (한국어 지원)
- narration 50자 내외로 추출해서 음성 생성
- 작가별 음성 ID 설정

작가별 음성:
    백야v1    → XTqHG68XyHm3iAxC18O2
    백야v2    → Velz1FYYWzS1Ro8Ln77l
    김도현    → icPpEDRQnftyC8bLxQht
    차로운    → x1VfcAsjwQX6oXjHOffX
    한여름    → DheTGeQX8ACNXdfZwHSe
"""

import re
import httpx
from app.core.config import settings
from app.core.personas import AUTHOR_ID_MAP as _AUTHOR_ID_MAP


# 작가별 음성 ID
_VOICE_MAP = {
    "baekya":     "XTqHG68XyHm3iAxC18O2",
    "charoun":    "x1VfcAsjwQX6oXjHOffX",
    "hanyeoreum": "DheTGeQX8ACNXdfZwHSe",
    "kimdohyeon": "icPpEDRQnftyC8bLxQht",
}

# 작가별 API 키 매핑 (계정 2개로 분리)
#   키1: 차로운·한여름  /  키2: 백야·김도현
_API_KEY_MAP = {
    "baekya":     "ELEVENLABS_API_KEY_2",
    "charoun":    "ELEVENLABS_API_KEY_1",
    "hanyeoreum": "ELEVENLABS_API_KEY_1",
    "kimdohyeon": "ELEVENLABS_API_KEY_2",
}

# author_id(int) → persona_id(str)
_AUTHOR_ID_MAP = {
    1: "baekya",
    2: "charoun",
    3: "hanyeoreum",
    4: "kimdohyeon",
}

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
MODEL_ID = "eleven_multilingual_v2"


def extract_first_sentence(narration: str, max_chars: int = 50) -> str:
    """narration에서 50자 내외로 자연스럽게 추출."""
    if not narration:
        return ""

    sentences = re.split(r'(?<=[.!?])\s*', narration.strip())
    sentences = [s for s in sentences if s]

    result = ""
    for s in sentences:
        if len(result) + len(s) <= max_chars:
            result += s + " "
        else:
            break

    return result.strip() or sentences[0]


async def synthesize(text: str, author_id: int) -> bytes:
    """
    텍스트를 음성으로 변환 (ElevenLabs).

    Args:
        text: 낭독할 텍스트 (narration 50자 내외)
        author_id: 1~4 (작가 ID)

    Returns:
        mp3 bytes
    """
    persona_id = _AUTHOR_ID_MAP.get(author_id, "")
    voice_id = _VOICE_MAP.get(persona_id)
    if not voice_id:
        return b""
    
    api_key_attr = _API_KEY_MAP.get(persona_id, "ELEVENLABS_API_KEY_1")
    api_key = getattr(settings, api_key_attr, "")
    if not api_key:
        return b""
    
    voice_id = _VOICE_MAP.get(persona_id)
    if not voice_id:
        return b""

    url = f"{ELEVENLABS_API_URL}/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.content
