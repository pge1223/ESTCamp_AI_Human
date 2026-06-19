import asyncio
import json
import logging
from typing import AsyncGenerator

from app.core.config import settings
from app.core.personas import PERSONA_PROMPTS, get_author_prompt, build_novel_system
from app.models.character import Character
from app.services.cache import CacheService
from app.services import llm  # 엔진 추상화 (Gemini ↔ Groq + 폴백)

logger = logging.getLogger(__name__)

if settings.LLM_PROVIDER == "openai":
    PRIMARY_MODEL  = settings.OPENAI_MODEL
    FALLBACK_MODEL = settings.OPENAI_FALLBACK_MODEL
elif settings.LLM_PROVIDER == "groq":
    PRIMARY_MODEL  = settings.GROQ_MODEL
    FALLBACK_MODEL = settings.GROQ_FALLBACK_MODEL
else:  # gemini
    PRIMARY_MODEL  = settings.GEMINI_MODEL
    FALLBACK_MODEL = settings.GEMINI_FALLBACK_MODEL

# 1M 토큰당 가격 (USD)
_PRICE_PER_M = {
    "gemini-2.5-flash":      {"input": 0.15,  "output": 0.60},
    "gemini-2.0-flash":      {"input": 0.10,  "output": 0.40},
    "gemini-2.0-flash-lite": {"input": 0.075, "output": 0.30},
    "gpt-4o":                {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":           {"input": 0.15,  "output": 0.60},
    "llama-3.3-70b-versatile": {"input": 0.00, "output": 0.00},
    "llama-3.1-8b-instant":    {"input": 0.00, "output": 0.00},
}

_COACHING_SUFFIX = (
    "\n\n당신은 지금 코칭 모드입니다. "
    "사용자가 작성한 글을 읽고 당신의 장르 철학에 맞는 구체적인 피드백을 주세요. "
    "잘된 점보다 개선점을 먼저, 수정 방향은 명확하게. "
    "대신 써주지 말고 방향만 짚어주세요."
)

cache_svc = CacheService()


# ── 토큰 비용 계산 ──────────────────────────────────────────────

def calc_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    price = _PRICE_PER_M.get(model_id, {"input": 0.15, "output": 0.60})
    return round(
        (prompt_tokens * price["input"] + completion_tokens * price["output"]) / 1_000_000,
        8,
    )


# ── 내부 유틸 ──────────────────────────────────────────────────

def _to_gemini_contents(history: list[dict], user_message: str) -> list[dict]:
    """대화 히스토리를 Gemini contents 포맷으로 변환."""
    contents = []
    for msg in history:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})
    return contents


async def _generate(system_prompt: str, contents: list[dict]) -> str:
    """단발성 호출 — 엔진/폴백은 llm 모듈이 처리."""
    return await llm.generate(system_prompt, contents)


async def _stream_gemini(
    system_prompt: str,
    contents: list[dict],
    usage_out: list | None = None,
) -> AsyncGenerator[str, None]:
    """스트리밍 호출 — 엔진/폴백은 llm 모듈이 처리. usage_out에 토큰 기록."""
    async for text in llm.stream(system_prompt, contents, usage_out):
        yield text


class LLMRouter:

    # 캐릭터 모드 스트리밍 (v1 dialogues 엔드포인트용)

    async def stream_character_response(
        self,
        character: Character,
        dialogue_history: list[dict],
        user_message: str,
    ) -> AsyncGenerator[str, None]:
        """
        dialogues.py 에서 호출.
        스트리밍 완료 후 event: log SSE로 토큰 사용량 전달.
        """
        system_prompt = character.prompt or ""
        contents = _to_gemini_contents(dialogue_history[-10:], user_message)
        usage_out: list = []

        logger.info("[stream_character] 캐릭터=%s", character.name)

        try:
            async for text_chunk in _stream_gemini(system_prompt, contents, usage_out=usage_out):
                payload = json.dumps(
                    {"character": character.name, "text": text_chunk, "done": False},
                    ensure_ascii=False,
                )
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n"
            return

        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        if usage_out:
            u = usage_out[0]
            log_payload = json.dumps({
                "model": u["model"],
                "prompt_tokens": u["prompt_tokens"],
                "completion_tokens": u["completion_tokens"],
                "cost": calc_cost(u["model"], u["prompt_tokens"], u["completion_tokens"]),
            }, ensure_ascii=False)
            yield f"event: log\ndata: {log_payload}\n\n"

    # 작가/등장인물 모드 스트리밍 (chats.py 연동)

    async def stream(
        self,
        persona_id: str,
        text: str,
        history: list[dict] | None = None,
        world_context: str = "",
        mode: str = "author",
    ) -> AsyncGenerator[str, None]:
        """
        /api/chats/{id}/stream 에서 호출.
        캐시 히트 시 즉시 반환, 미스 시 LLM 스트리밍.
        """
        history = history or []
        cache_key = {"persona_id": persona_id, "text": text, "mode": mode}

        cached = await cache_svc.get("stream", cache_key)
        if cached:
            logger.debug("[CACHE HIT] stream persona=%s", persona_id)
            yield f"data: {json.dumps({'text': cached, 'done': False}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        system_prompt = get_author_prompt(
            persona_id=persona_id,
            world_context=world_context,
            mode=mode,
        )
        contents = _to_gemini_contents(history, text)
        full_chunks: list[str] = []
        usage_out: list = []

        try:
            async for text_chunk in _stream_gemini(system_prompt, contents, usage_out=usage_out):
                full_chunks.append(text_chunk)
                payload = json.dumps(
                    {"text": text_chunk, "done": False}, ensure_ascii=False
                )
                yield f"data: {payload}\n\n"
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"event: error\ndata: {err}\n\n"
            return

        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

        if full_chunks:
            await cache_svc.set("stream", cache_key, "".join(full_chunks))

        if usage_out:
            u = usage_out[0]
            log_payload = json.dumps({
                "model": u["model"],
                "prompt_tokens": u["prompt_tokens"],
                "completion_tokens": u["completion_tokens"],
                "cost": calc_cost(u["model"], u["prompt_tokens"], u["completion_tokens"]),
            }, ensure_ascii=False)
            yield f"event: log\ndata: {log_payload}\n\n"

    # 코칭 모드

    async def coach(self, persona_id: str, user_text: str) -> str:

        cache_key = {"persona_id": persona_id, "text": user_text, "mode": "coaching"}
        cached = await cache_svc.get("coach", cache_key)
        if cached:
            return cached

        base = PERSONA_PROMPTS.get(persona_id)
        if not base:
            raise ValueError(f"알 수 없는 페르소나: {persona_id}")

        contents = [{"role": "user", "parts": [{"text": user_text}]}]
        result = await _generate(base + _COACHING_SUFFIX, contents)
        await cache_svc.set("coach", cache_key, result)
        return result

    # 장르 비교 모드

    async def generate_all_personas(self, text: str) -> dict[str, str]:

        async def _one(pid: str) -> tuple[str, str]:
            cache_key = {"persona_id": pid, "text": text, "mode": "compare"}
            cached = await cache_svc.get("compare", cache_key)
            if cached:
                return pid, cached

            system_prompt = get_author_prompt(persona_id=pid, world_context="", mode="author")
            contents = [{"role": "user", "parts": [{"text": text}]}]
            result = await _generate(system_prompt, contents)
            await cache_svc.set("compare", cache_key, result)
            return pid, result

        pairs = await asyncio.gather(
            *[_one(pid) for pid in PERSONA_PROMPTS],
            return_exceptions=True,
        )

        results: dict[str, str] = {}
        for item in pairs:
            if isinstance(item, Exception):
                logger.error("[compare] 생성 실패: %s", item)
            else:
                pid, out = item
                results[pid] = out
        return results

    # 대화 히스토리 요약 (ContextManager용)

    async def summarize_history(self, history: list[dict]) -> str:
        """오래된 대화 히스토리를 3~4문장으로 요약해 컨텍스트 압축."""
        if not history:
            return ""
        block = "\n".join(
            f"{'사용자' if h['role'] == 'user' else 'AI'}: {h['content']}"
            for h in history
        )
        system = (
            "당신은 소설 대화 요약 전문가입니다. "
            "아래 대화의 핵심 사건, 인물 관계, 감정 흐름을 3~4문장으로 요약하세요. "
            "이후 이야기 전개에 필요한 맥락이 유지되도록 간결하게 작성하세요."
        )
        contents = [{"role": "user", "parts": [{"text": f"다음 대화를 요약해주세요:\n\n{block}"}]}]
        return await _generate(system, contents)

    # 대화 → 소설 변환

    async def generate_novel(
        self,
        dialogue_history: list[dict],
        world_description: str = "",
        persona_id: str = "",
        use_style: bool = True,
    ) -> str:
        """대화 히스토리를 소설 한 장면으로 변환. persona_id가 있으면 그 작가 문체로.

        use_style=False 면 문체 RAG(few-shot) 주입을 건너뛴다(시연/비교용 대조).
        """
        if not dialogue_history:
            return ""

        # persona_id 없으면 build_novel_system이 작가 중립 폴백으로 처리
        system_prompt = build_novel_system(persona_id, world_description)

        block = "\n\n".join(
            f"{'사용자' if m.get('role') == 'user' else '작가'}: {m['content']}"
            for m in dialogue_history
        )

        # 문체 RAG: 이 작가의 문체 예시 중 장면과 가장 가까운 것을 few-shot으로 주입
        if persona_id and use_style:
            try:
                from app.services import style
                examples = await style.retrieve_examples(persona_id, block, k=3)
                if examples:
                    ex = "\n".join(f"- {e}" for e in examples)
                    system_prompt += (
                        "\n\n[이 작가의 문체 예시]\n"
                        "아래는 어조·리듬·호흡·시선 처리를 보여주는 참고용 문장이다. "
                        "문장·표현·소재를 베끼지 말고, 목소리만 닮게 이 장면에 맞는 새 문장을 써라.\n"
                        f"{ex}"
                    )
            except Exception as e:
                logger.warning("문체 예시 검색 실패(건너뜀): %s", e)
        contents = [{
            "role": "user",
            "parts": [{"text": f"아래 대화를 소설 장면으로 변환해주세요:\n\n{block}"}],
        }]
        return await _generate(system_prompt, contents)
