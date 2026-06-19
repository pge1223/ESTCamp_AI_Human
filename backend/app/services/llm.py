"""LLM 호출 정교 파이프라인.

요구사항 충족:
  1) 모델 스위칭        — provider별 [PRIMARY, FALLBACK]
  2) 프로바이더 체인     — LLM_PROVIDER_CHAIN="groq,gemini" 순서로 자동 승계
  3) n개 계정 키 순환    — GEMINI_API_KEYS / GROQ_API_KEYS (콤마구분) + 단일키 병합
  4) 429 전용 분기       — quota=쿨다운+다음, auth=키폐기, transient=백오프재시도, model/bad=다음
  5) 최종 폴백 예외처리   — 모든 후보 소진 시 마지막 예외 raise (호출부에서 폴백 처리)

후보(candidate) = (provider, model, api_key). 체인순→모델순→키순으로 시도.
호출부(llm_router, chats)는 generate()/stream()만 쓰면 됨 (시그니처 유지).

contents 형식: [{"role": "user"|"model", "parts": [{"text": "..."}]}]
"""
import asyncio
import logging
import time
from typing import AsyncGenerator

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── 설정 파싱 ────────────────────────────────────────────────────
def _csv(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _dedup(seq) -> list[str]:
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _gemini_keys() -> list:
    if settings.USE_VERTEX:
        return [None]  # Vertex는 ADC 인증 → API 키 없음(후보 1개)
    return _dedup(_csv(settings.GEMINI_API_KEYS) + [settings.GEMINI_API_KEY, settings.GEMINI_API_KEY_2])


def _groq_keys() -> list[str]:
    return _dedup(_csv(settings.GROQ_API_KEYS) + [settings.GROQ_API_KEY])


def _openai_keys() -> list[str]:
    return _dedup(_csv(settings.OPENAI_API_KEYS) + [settings.OPENAI_API_KEY])


def _provider_chain() -> list[str]:
    return _csv(settings.LLM_PROVIDER_CHAIN) or _csv(settings.LLM_PROVIDER) or ["gemini"]


COOLDOWN_SEC = settings.LLM_KEY_COOLDOWN_SEC
MAX_TRANSIENT_RETRY = settings.LLM_MAX_TRANSIENT_RETRY

# 런타임 상태 (프로세스 메모리)
_cooldown: dict[tuple, float] = {}   # (provider, model, key) → 해제 시각(monotonic)
_bad_keys: set[str] = set()          # 인증 실패한 키 (영구 스킵)
_oai_clients: dict[tuple, object] = {}   # (provider, key) → OpenAI호환 클라이언트

logger.info("LLM 파이프라인: chain=%s | gemini키=%d | groq키=%d",
            _provider_chain(), len(_gemini_keys()), len(_groq_keys()))


# ── 후보 생성 ────────────────────────────────────────────────────
def _candidates(chain: list[str] | None = None) -> list[tuple]:
    """[(provider, model, key)] — 체인순 → 모델(primary,fallback) → 키.

    chain을 주면 그 프로바이더만으로 후보를 만든다(평가용 provider 강제에 사용).
    """
    out = []
    for prov in (chain or _provider_chain()):
        if prov == "gemini":
            models = [m for m in (settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL) if m]
            keys = _gemini_keys() or [settings.GEMINI_API_KEY]
        elif prov == "groq":
            models = [m for m in (settings.GROQ_MODEL, settings.GROQ_FALLBACK_MODEL) if m]
            keys = _groq_keys() or [settings.GROQ_API_KEY]
        elif prov == "openai":
            models = [m for m in (settings.OPENAI_MODEL, settings.OPENAI_FALLBACK_MODEL) if m]
            keys = _openai_keys() or [settings.OPENAI_API_KEY]
        else:
            continue
        for m in models:
            for k in keys:
                out.append((prov, m, k))
    return out


def _active_candidates(provider: str | None = None) -> list[tuple]:
    """쿨다운/불량키 제외. 전부 막혔으면 그냥 전체 반환(쿼터 회복 가능성).

    provider를 주면 그 프로바이더(예: "openai")만으로 후보를 만든다 — 평가에서
    베이스라인/채점관을 특정 모델로 강제할 때 사용.
    """
    now = time.monotonic()
    chain = [provider] if provider else None
    cands = _candidates(chain)
    active = [c for c in cands if c[2] not in _bad_keys and _cooldown.get(c, 0) <= now]
    return active or cands


# ── 에러 분류 ────────────────────────────────────────────────────
def _classify(exc: Exception) -> str:
    s = str(exc).lower()
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code == 429 or any(t in s for t in ("429", "resource_exhausted", "quota", "rate limit",
                                            "exceeded", "depleted", "too many requests")):
        return "quota"
    if code in (401, 403) or any(t in s for t in ("invalid api key", "unauthorized", "permission denied")):
        return "auth"
    if code == 404 or "not found" in s or "does not exist" in s or "decommission" in s:
        return "model"
    if code in (500, 502, 503, 504) or any(t in s for t in ("timeout", "timed out", "connection",
                                                            "temporarily", "unavailable", "internal")):
        return "transient"
    return "bad"


# ── 입력 변환 ────────────────────────────────────────────────────
def _to_openai_messages(system_prompt: str, contents: list[dict]) -> list[dict]:
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    for c in contents:
        role = "assistant" if c.get("role") == "model" else (c.get("role") or "user")
        text = "".join(p.get("text", "") for p in c.get("parts", []))
        msgs.append({"role": role, "content": text})
    return msgs


def _oai_client(prov: str, key: str):
    """OpenAI 호환 클라이언트(groq/openai). 둘 다 chat.completions API 동일."""
    ck = (prov, key)
    if ck not in _oai_clients:
        if prov == "openai":
            from openai import OpenAI
            _oai_clients[ck] = OpenAI(api_key=key)
        else:  # groq
            from groq import Groq
            _oai_clients[ck] = Groq(api_key=key)
    return _oai_clients[ck]


_vertex_ready = False


def _ensure_vertex():
    global _vertex_ready
    if not _vertex_ready:
        import vertexai
        vertexai.init(project=settings.GOOGLE_CLOUD_PROJECT, location=settings.GOOGLE_CLOUD_LOCATION)
        _vertex_ready = True
        logger.info("Vertex AI init: project=%s location=%s",
                    settings.GOOGLE_CLOUD_PROJECT, settings.GOOGLE_CLOUD_LOCATION)


def _gemini_model(model: str, key: str, system_prompt: str):
    if settings.USE_VERTEX:
        _ensure_vertex()
        from vertexai.generative_models import GenerativeModel as _VxModel
        return _VxModel(model, system_instruction=system_prompt or None)
    import google.generativeai as genai
    genai.configure(api_key=key)  # 전역 설정 (동시요청 시 드물게 키 경합 가능 — 데모 범위 허용)
    return genai.GenerativeModel(model, system_instruction=system_prompt or None)


def _gemini_gen_config(json_mode: bool):
    """Gemini generation_config. Vertex면 thinking 끔(응답 속도↑), json_mode면 JSON 강제."""
    cfg = {}
    if settings.USE_VERTEX:
        cfg["thinking_config"] = {"thinking_budget": 0}  # 창작엔 '사고' 불필요 → 지연 크게 감소
    if json_mode:
        cfg["response_mime_type"] = "application/json"
    return cfg or None


# ── 단발 호출(동기) ──────────────────────────────────────────────
def _gen_once(prov: str, model: str, key: str, system_prompt: str, contents: list[dict],
              json_mode: bool = False) -> tuple[str, dict]:
    if prov in ("groq", "openai"):
        kwargs = {"model": model, "messages": _to_openai_messages(system_prompt, contents)}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}  # 유효한 JSON 강제
        resp = _oai_client(prov, key).chat.completions.create(**kwargs)
        u = getattr(resp, "usage", None)
        usage = {"model": model,
                 "prompt_tokens": getattr(u, "prompt_tokens", 0) or 0,
                 "completion_tokens": getattr(u, "completion_tokens", 0) or 0}
        return (resp.choices[0].message.content or ""), usage
    # gemini
    # request_options(timeout)는 google-generativeai 전용 인자 — Vertex SDK의 generate_content는 안 받음
    _gen_kwargs = {"generation_config": _gemini_gen_config(json_mode)}
    if not settings.USE_VERTEX:
        _gen_kwargs["request_options"] = {"timeout": 40}
    resp = _gemini_model(model, key, system_prompt).generate_content(contents, **_gen_kwargs)
    meta = getattr(resp, "usage_metadata", None)
    usage = {"model": model,
             "prompt_tokens": getattr(meta, "prompt_token_count", 0) or 0,
             "completion_tokens": getattr(meta, "candidates_token_count", 0) or 0}
    return resp.text, usage


# ── 스트림 호출(동기 제너레이터) ─────────────────────────────────
def _stream_once(prov: str, model: str, key: str, system_prompt: str, contents: list[dict], usage_box: list,
                 json_mode: bool = False):
    """텍스트 청크를 yield. 완료 후 usage_box에 사용량 기록. 429 등은 첫 next()에서 raise."""
    if prov in ("groq", "openai"):
        _kw = {"model": model, "messages": _to_openai_messages(system_prompt, contents), "stream": True}
        if json_mode:
            _kw["response_format"] = {"type": "json_object"}
        s = _oai_client(prov, key).chat.completions.create(**_kw)
        pt = ct = 0
        for chunk in s:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            xg = getattr(chunk, "x_groq", None)
            if xg and getattr(xg, "usage", None):
                pt = xg.usage.prompt_tokens or 0
                ct = xg.usage.completion_tokens or 0
        usage_box.append({"model": model, "prompt_tokens": pt, "completion_tokens": ct})
        return
    # gemini
    resp = _gemini_model(model, key, system_prompt).generate_content(
        contents, stream=True, generation_config=_gemini_gen_config(json_mode))
    for chunk in resp:
        if chunk.text:
            yield chunk.text
    meta = getattr(resp, "usage_metadata", None)
    usage_box.append({"model": model,
                      "prompt_tokens": getattr(meta, "prompt_token_count", 0) or 0,
                      "completion_tokens": getattr(meta, "candidates_token_count", 0) or 0})


# ── 실패 처리 공통 ───────────────────────────────────────────────
def _handle_failure(cand: tuple, exc: Exception, attempt: int) -> str:
    """반환: 'retry'(같은 후보 재시도) | 'next'(다음 후보). 부수효과: 쿨다운/불량키 기록."""
    prov, model, key = cand
    kind = _classify(exc)
    tag = f"{prov}/{model}/…{key[-4:] if key else ''}"
    if kind == "quota":
        _cooldown[cand] = time.monotonic() + COOLDOWN_SEC
        logger.warning("[LLM quota] %s 소진 → 쿨다운 %ds, 다음 후보", tag, COOLDOWN_SEC)
        return "next"
    if kind == "auth":
        _bad_keys.add(key)
        logger.warning("[LLM auth] %s 인증실패 → 키 폐기, 다음 후보", tag)
        return "next"
    if kind == "transient" and attempt < MAX_TRANSIENT_RETRY:
        logger.warning("[LLM transient] %s 일시오류 → 백오프 재시도(%d): %s", tag, attempt + 1, exc)
        return "retry"
    logger.warning("[LLM %s] %s 실패 → 다음 후보: %s", kind, tag, exc)
    return "next"


# ── 공개 API ─────────────────────────────────────────────────────
async def generate(system_prompt: str, contents: list[dict], usage_out: list | None = None,
                   json_mode: bool = False, provider: str | None = None) -> str:
    """단발 생성. 후보 순회 + 429 분기 + 백오프. 전부 실패 시 마지막 예외 raise.

    json_mode=True 면 프로바이더에 JSON 출력을 강제(Groq/OpenAI response_format,
    Gemini response_mime_type) — narration/dialogue 구조화 응답에 사용.

    provider="openai"|"gemini"|"groq" 를 주면 그 프로바이더로만 호출한다(평가용:
    베이스라인을 진짜 GPT로, 채점관을 독립 모델로 강제). None이면 기존 체인 사용.
    """
    last_exc = None
    for cand in _active_candidates(provider):
        prov, model, key = cand
        attempt = 0
        while True:
            try:
                text, usage = await asyncio.wait_for(
                    asyncio.to_thread(_gen_once, prov, model, key, system_prompt, contents, json_mode),
                    timeout=45.0,
                )
                if usage_out is not None:
                    usage_out.append(usage)
                return text
            except asyncio.TimeoutError:
                tag = f"{prov}/{model}"
                logger.warning("[LLM timeout] %s 45s 초과 → 다음 후보", tag)
                last_exc = RuntimeError(f"{tag} 응답 시간 초과")
                break
            except Exception as e:
                last_exc = e
                action = _handle_failure(cand, e, attempt)
                if action == "retry":
                    attempt += 1
                    await asyncio.sleep(min(0.5 * (2 ** attempt), 8))
                    continue
                break
    raise last_exc or RuntimeError("LLM 생성 실패: 후보 없음")


async def stream(system_prompt: str, contents: list[dict], usage_out: list | None = None,
                 json_mode: bool = False) -> AsyncGenerator[str, None]:
    """스트리밍 생성. 첫 청크 전 실패면 다음 후보로 승계(이미 보냈으면 재시도 불가).

    json_mode=True 면 프로바이더에 JSON 출력을 강제(구조화 응답 스트리밍에 사용).
    """
    last_exc = None
    for cand in _active_candidates():
        prov, model, key = cand
        attempt = 0
        while True:
            yielded = False
            box: list = []
            try:
                for text in _stream_once(prov, model, key, system_prompt, contents, box, json_mode):
                    yielded = True
                    yield text
                if usage_out is not None and box:
                    usage_out.append(box[0])
                return
            except Exception as e:
                last_exc = e
                if yielded:
                    raise  # 이미 일부 스트리밍 → 재시도 불가
                action = _handle_failure(cand, e, attempt)
                if action == "retry":
                    attempt += 1
                    await asyncio.sleep(min(0.5 * (2 ** attempt), 8))
                    continue
                break
    raise last_exc or RuntimeError("LLM 스트리밍 실패: 후보 없음")


# ── 임베딩(RAG 검색용) ────────────────────────────────────────────
EMBED_MODEL = "models/gemini-embedding-001"


def _embed_sync(key, texts: list[str]) -> list[list[float]]:
    if settings.USE_VERTEX:
        _ensure_vertex()
        from vertexai.language_models import TextEmbeddingModel
        m = TextEmbeddingModel.from_pretrained("text-multilingual-embedding-002")
        embs = m.get_embeddings(list(texts))
        return [list(e.values) for e in embs]
    import google.generativeai as genai
    genai.configure(api_key=key)
    out = []
    for t in texts:
        r = genai.embed_content(model=EMBED_MODEL, content=t)
        out.append(list(r["embedding"]))
    return out


async def embed(texts: list[str]) -> list[list[float]]:
    """문장 리스트 → 임베딩 벡터 리스트 (Gemini text-embedding-004)."""
    if not texts:
        return []
    keys = _gemini_keys()
    if not keys:
        raise RuntimeError("임베딩용 Gemini 키가 없습니다 (GEMINI_API_KEY).")
    return await asyncio.to_thread(_embed_sync, keys[0], texts)
