"""삽화 이미지 생성 서비스.

2가지 모드:
  1. 직접 입력: 사용자 장면 설명 → LLM 정제·필터 → Vertex AI Imagen 3
  2. AI 추천:  소설 내용 → LLM 장면 후보 4종 → 사용자 선택 → Vertex AI Imagen 3

Imagen 3 호출은 동기 SDK를 asyncio.to_thread로 감싼다.
LLM 호출 실패 시 대화 흐름을 막지 않도록 예외를 흡수한다.
"""
import asyncio
import base64
import json
import logging

from app.services import llm

logger = logging.getLogger(__name__)

# ── 스타일·분위기·비율 매핑 ─────────────────────────────────────────────
STYLE_MAP = {
    "webtoon":    "Korean webtoon illustration style, web novel cover art, vibrant anime art, detailed character design",
    "watercolor": "soft watercolor illustration, dreamy and gentle, pastel tones, delicate brushstrokes",
    "ink":        "black and white ink illustration, manga style, clean expressive lines, high contrast",
    "realistic":  "semi-realistic digital illustration, cinematic lighting, detailed environment",
    "pastel":     "soft pastel aesthetic illustration, kawaii style, gentle warm tones",
}

MOOD_MAP = {
    "warm":     "warm golden lighting, cozy and inviting atmosphere",
    "dark":     "dark dramatic atmosphere, moody deep shadows, suspenseful",
    "dreamy":   "ethereal dreamy atmosphere, soft diffused light, misty",
    "tense":    "tense dramatic lighting, high contrast, suspenseful mood",
    "romantic": "romantic soft lighting, tender intimate moment, warm pink tones",
}


TYPE_LABEL = {
    "dramatic":     "핵심 장면",
    "emotional":    "감정 장면",
    "foreshadowing": "복선 장면",
    "fanservice":   "팬서비스 장면",
}

# ── 프롬프트 ────────────────────────────────────────────────────────────
_SCENE_RECOMMEND_SYSTEM = """\
당신은 웹소설 삽화 연출 전문가입니다.
소설 내용을 읽고 삽화로 만들기 좋은 장면 4개를 아래 유형으로 각 1개씩 추천하세요.

유형:
- dramatic     : 이야기의 핵심 사건·전환점
- emotional    : 인물의 감정이 가장 강하게 드러나는 장면
- foreshadowing: 복선·이스터에그가 담긴 장면
- fanservice   : 독자가 좋아할 관계성·설렘·긴장감이 있는 장면

JSON 형식으로만 응답하세요:
{
  "scenes": [
    {"type":"dramatic","label":"핵심 장면","description":"2~3문장 설명","visual":"시각적 묘사 힌트"},
    {"type":"emotional","label":"감정 장면","description":"...","visual":"..."},
    {"type":"foreshadowing","label":"복선 장면","description":"...","visual":"..."},
    {"type":"fanservice","label":"팬서비스 장면","description":"...","visual":"..."}
  ]
}"""

_FILTER_REFINE_SYSTEM = """\
당신은 한국 웹소설 앱의 삽화 프롬프트 검수 전문가입니다.
사용자가 입력한 장면 설명을 검토한 뒤 Imagen 3용 영어 프롬프트로 정제하세요.

검토 기준:
1. 웹소설 삽화로 적합한가?
2. 선정적·폭력적·혐오 표현이 있는가?
3. 소설 내용·분위기와 너무 동떨어졌는가?
4. 장난성/저품질 요청인가?

JSON 형식으로만 응답하세요:
{
  "status": "appropriate" | "refine_needed" | "inappropriate",
  "refined_prompt": "Imagen 3용 영어 프롬프트 (appropriate·refine_needed)",
  "suggestion": "한국어 수정 제안 (refine_needed인 경우, 없으면 null)",
  "block_reason": "거절 이유 (inappropriate인 경우, 없으면 null)"
}

- appropriate   : 그대로 생성 가능
- refine_needed : 내용을 순화·조정 후 생성 (대체 제안 포함)
- inappropriate : 생성 불가 (선정적·폭력·혐오 등)"""


# ── 핵심 함수 ────────────────────────────────────────────────────────────
async def recommend_scenes(novel_content: str, world_context: str) -> dict:
    """소설 내용에서 삽화 후보 장면 4개 추출."""
    excerpt = novel_content[:3000]
    user_msg = f"[세계관]\n{world_context}\n\n[소설 내용]\n{excerpt}"
    try:
        raw = await llm.generate(
            _SCENE_RECOMMEND_SYSTEM,
            [{"role": "user", "parts": [{"text": user_msg}]}],
            json_mode=True,
        )
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception as e:
        logger.warning("장면 추천 실패: %s", e)
        return {"scenes": []}


async def filter_and_refine(
    scene_desc: str,
    genre: str,
    style: str,
    mood: str,
) -> dict:
    """사용자 입력 필터 + DALL-E 프롬프트 정제."""
    style_hint = STYLE_MAP.get(style, STYLE_MAP["webtoon"])
    mood_hint  = MOOD_MAP.get(mood, "")
    user_msg = (
        f"장르: {genre}\n"
        f"사용자 입력 장면: {scene_desc}\n"
        f"원하는 스타일: {style_hint}\n"
        f"원하는 분위기: {mood_hint}"
    )
    try:
        raw = await llm.generate(
            _FILTER_REFINE_SYSTEM,
            [{"role": "user", "parts": [{"text": user_msg}]}],
            json_mode=True,
        )
        data = json.loads(raw) if isinstance(raw, str) else raw
        if data.get("status") in ("appropriate", "refine_needed") and data.get("refined_prompt"):
            extra = ", ".join(filter(None, [style_hint, mood_hint]))
            data["refined_prompt"] = f"{data['refined_prompt']}, {extra}".strip(", ")
        return data
    except Exception as e:
        logger.warning("프롬프트 정제 실패(폴백): %s", e)
        return {
            "status": "appropriate",
            "refined_prompt": f"{scene_desc}, {STYLE_MAP['webtoon']}",
            "suggestion": None,
            "block_reason": None,
        }


# ── 이미지 생성: Vertex Gemini 2.5 Flash Image ──────────────────────────
# fal.ai(유료·데이터센터 IP 차단) 대신 GCP Vertex 사용 → ADC 인증이라 Cloud Run에서
# IP 차단 없이 동작 + 기존 GCP 크레딧으로 결제. 응답 이미지 바이트 → base64 data URL로
# 반환(별도 스토리지 불필요, 프론트 <img src>가 그대로 표시).
_IMAGE_MODEL = "gemini-2.5-flash-image"

_RATIO_HINT = {
    "1:1":  "square 1:1 aspect ratio composition",
    "16:9": "wide 16:9 cinematic landscape composition",
    "9:16": "tall 9:16 vertical portrait composition",
}


def _generate_image_sync(prompt: str, ratio: str) -> str:
    """Vertex Gemini 2.5 Flash Image로 이미지 생성 → base64 data URL(동기)."""
    from vertexai.generative_models import GenerativeModel
    llm._ensure_vertex()   # llm.py와 동일한 vertexai.init(ADC) 재사용
    hint = _RATIO_HINT.get(ratio, _RATIO_HINT["1:1"])
    full_prompt = f"{prompt}\n\n{hint}. High-quality illustration. No text, letters, or watermark."
    model = GenerativeModel(_IMAGE_MODEL)
    resp = model.generate_content(
        full_prompt,
        generation_config={"response_modalities": ["TEXT", "IMAGE"]},
    )
    for cand in (getattr(resp, "candidates", None) or []):
        content = getattr(cand, "content", None)
        for part in (getattr(content, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                mime = getattr(inline, "mime_type", None) or "image/png"
                b64 = base64.b64encode(inline.data).decode()
                return f"data:{mime};base64,{b64}"
    raise RuntimeError("이미지 응답에 이미지 파트가 없습니다(안전필터 차단 또는 모델 미지원).")


async def generate_image(prompt: str, ratio: str = "1:1") -> str:
    """프롬프트 → 이미지(base64 data URL). 동기 Vertex 호출을 thread로 감싼다(루프 비차단)."""
    return await asyncio.to_thread(_generate_image_sync, prompt, ratio)
