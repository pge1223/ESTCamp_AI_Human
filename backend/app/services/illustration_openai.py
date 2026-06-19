"""OpenAI gpt-image-1 삽화 생성 서비스 (독립 모듈).

기존 Gemini 기반 illustration.py 와 별개로 유지해
provider 전환 없이 두 경로를 동시에 사용할 수 있다.

[스타일 프리셋]
  STYLE_* 상수를 f-string으로 조합해 프롬프트를 만든다.
  나중에 맞춤설정 UI에서 사용자가 스타일을 고를 수 있도록
  STYLES dict에 이름을 등록해두면 된다.
"""
import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── 스타일 프리셋 ─────────────────────────────────────────────────────────
STYLE_WEBTOON = """
Korean webtoon illustration style,
anime art,
vibrant colors,
detailed character design,
web novel cover art quality,
clean lineart,
cel shading
"""

STYLE_WATERCOLOR = """
watercolor and gouache painting,
storybook illustration,

soft pastel colors,
delicate brush strokes,
paper texture,

golden sunlight,
soft atmospheric lighting,

dreamy atmosphere,
nostalgic feeling,
peaceful mood,

highly detailed landscape,
beautiful natural scenery,

hand-painted artwork,
children's book illustration
"""

STYLE_ROMANCE = """
dreamy atmosphere,
lush flower field,
floating flower petals,
warm lighting,
emotional mood
"""

STYLE_FANTASY = """
epic fantasy illustration,
magical atmosphere,
mystical glowing light,
otherworldly environment,
detailed fantasy world,
cinematic composition
"""

STYLE_GHIBLI = """
Studio Ghibli inspired,
gentle hand-drawn style,
lush natural background,
warm nostalgic atmosphere,
soft and expressive characters,
peaceful and whimsical mood
"""

# 지브리/애니풍 방지용 네거티브 블록
NEGATIVE_STYLE = """
anime style,
manga style,
cel shading,
cartoon,
3d render,
pixar,
studio ghibli character design,
webtoon style
"""

# 이름 → 프리셋 매핑 (맞춤설정 UI에서 참조)
STYLES: dict[str, str] = {
    "webtoon":    STYLE_WEBTOON,
    "watercolor": STYLE_WATERCOLOR,
    "romance":    STYLE_ROMANCE,
    "fantasy":    STYLE_FANTASY,
    "ghibli":     STYLE_GHIBLI,
}

# 자동생성 기본 스타일
_DEFAULT_STYLES = [STYLE_WATERCOLOR, STYLE_ROMANCE]


# ── 프롬프트 빌드 ─────────────────────────────────────────────────────────
def _build_prompt(scene: str, styles: list[str] | None = None) -> str:
    """장면 묘사 + 스타일 프리셋 목록 → 최종 프롬프트."""
    style_block = "\n".join(s.strip() for s in (styles or _DEFAULT_STYLES))
    return f"""{scene}

{style_block}

Focus on scenery and atmosphere.
Natural watercolor textures.
Painterly composition.

Avoid:
{NEGATIVE_STYLE.strip()}

masterpiece
""".strip()


def _build_scene(title: str, genre: str, description: str) -> str:
    parts: list[str] = []
    if title:
        parts.append(f"A couple walking through a vast flower meadow, small figures in the landscape, golden sunset, endless wildflowers, from the story '{title}'")
    if genre:
        parts.append(f"genre: {genre}")
    if description:
        parts.append(description[:400])
    return ", ".join(parts) if parts else "a couple walking through a vast flower meadow, small figures in the landscape, golden sunset, endless wildflowers"


# ── OpenAI 호출 ───────────────────────────────────────────────────────────
def _generate_sync(prompt: str) -> str:
    """동기 OpenAI 호출 → base64 data URL."""
    from openai import OpenAI

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
    )
    b64 = result.data[0].b64_json
    if not b64:
        raise RuntimeError("OpenAI 응답에 이미지 데이터가 없습니다.")
    return f"data:image/png;base64,{b64}"


async def generate_image(
    title: str = "",
    genre: str = "",
    description: str = "",
    style_names: list[str] | None = None,
    scene: str = "",
) -> str:
    """세계관 정보 + 스타일 프리셋 → OpenAI gpt-image-1 → base64 data URL.

    scene: 사용자가 직접 입력하거나 AI가 추천한 장면 설명.
           비어 있으면 title/genre/description으로 자동 생성.
    style_names: STYLES dict 키 목록. None이면 기본 스타일 사용.
    """
    styles = [STYLES[n] for n in (style_names or []) if n in STYLES] or _DEFAULT_STYLES
    final_scene = scene.strip() if scene.strip() else _build_scene(title, genre, description)
    prompt = _build_prompt(final_scene, styles)
    logger.info("OpenAI 삽화 생성 프롬프트:\n%s", prompt)
    return await asyncio.to_thread(_generate_sync, prompt)
