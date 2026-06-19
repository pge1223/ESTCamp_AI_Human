<!-- markdownlint-disable MD022 MD032 MD031 MD040 -->
# 아키텍처

> 최종 갱신: 2026-06-14 — **클라우드 풀스택**(Neon · Upstash · Vertex AI), **백엔드 Cloud Run / 프론트 Vercel** 배포.

## 레이어 구조

```
┌────────────────────────────────────────────────────────────┐
│  API Layer        app/api/v1/endpoints/  ← HTTP·SSE 처리     │
│                   app/api/v1/router.py   ← /api/v1 통합      │
├────────────────────────────────────────────────────────────┤
│  Schema Layer     app/schemas/  ← Pydantic 입출력 검증/직렬화 │
├────────────────────────────────────────────────────────────┤
│  Service Layer    app/services/ · app/core/                 │
│   llm·llm_router  (프로바이더 체인·키 순환·폴백)              │
│   chat_context    (Redis 히스토리/상태/요약)                 │
│   memory·consistency·style   (RAG 3종)                      │
│   proofread       (맞춤법 교정·용어집)                       │
│   tts·evaluate·world_tag_classifier                         │
│   core/personas·reactions·prompts (프롬프트)                 │
├────────────────────────────────────────────────────────────┤
│  Model Layer      app/models/  ← SQLAlchemy 2.0 ORM         │
├────────────────────────────────────────────────────────────┤
│  Infrastructure   Neon(PostgreSQL) │ Upstash(Redis) │ Vertex AI│
└────────────────────────────────────────────────────────────┘
```

배포: 백엔드 **GCP Cloud Run**(Dockerfile + Secret Manager, Vertex는 런타임 SA/ADC) · 프론트 **Vercel**(정적 SPA, `apiBase`가 백엔드 직접 호출).

---

## 폴더별 역할

### `app/main.py`
- FastAPI 앱 + CORS(`ALLOWED_ORIGINS`) + v1 라우터 마운트 + 로깅 + `GET /health`

### `app/database.py`
- `create_async_engine`(asyncpg) — `_prepare_db_url`이 `postgresql://…?sslmode=require` → **asyncpg + SSL 자동 변환**(Neon)
- `pool_pre_ping`/`pool_recycle`로 끊긴 커넥션 복원, `get_db` 의존성, `Base`

### `app/core/config.py`
- `pydantic-settings` — `.env` → `settings` 싱글턴
- 주요: `DATABASE_URL`(Neon) · `REDIS_URL`(Upstash) · **`USE_VERTEX`·`GOOGLE_CLOUD_PROJECT`·`GOOGLE_CLOUD_LOCATION`·`GEMINI_MODEL`·`GEMINI_FALLBACK_MODEL`** · `LLM_PROVIDER`·`LLM_PROVIDER_CHAIN` · `GROQ_API_KEY`/`OPENAI_API_KEY`(폴백) · `ELEVENLABS_API_KEY_1/2`(TTS) · `ALLOWED_ORIGINS`

### `app/models/`
- SQLAlchemy 2.0(`Mapped[]`+`mapped_column`). `__init__.py`에서 전체 임포트 → Alembic 자동 감지
- user(+`voice_profile`/`error_profile`) · session(+`story_summary`) · world(+`tags`/`glossary`) · character · dialogue(+`speaker`) · novel · illustration · api_log · saved_sentence · user_chat_taste · user_taste_profile · 상세: [models.md](models.md)

### `app/services/`
- **`llm.py`** — LLM 호출 일원화: 프로바이더 체인(`USE_VERTEX`면 Vertex 우선 → Groq/OpenAI 폴백) · n키 순환 · 429/auth/transient 분기·쿨다운·지수 백오프 · `generate(json_mode=True)`(서술/대사 구조화 강제) · **`stream()`(SSE 토큰 스트리밍 — 첫 청크 전 실패 시 다음 후보 승계)** · `embed`(임베딩) · `provider=` 오버라이드(평가용 GPT 강제)
- **`chat_context.py`** — Redis 최근 대화/상태/요약 + DB fallback (※ chats.py에도 동명 로컬 헬퍼 존재)
- **`memory.py`** (RAG ①기억) — 증분 누적요약 + Gemini 임베딩 코사인 top-K 의미검색
- **`consistency.py`** (RAG ②검수, F-QC-01) — 새 응답 ↔ 설정/기억 모순 탐지(LLM JSON)
- **`style.py`** (RAG ③문체, F-NV-08) — 작가 문체 샘플 few-shot 검색 주입
- **`personalize.py`** (개인화 RAG) — `saved_sentences` 의미검색 → 취향저격 추천 톤 근거 주입(저장 톤→추천 톤 인과)
- **`proofread.py`** (F-QC-02) — 네이버 맞춤법기 + 단어단위 diff, 고유명사 보호·자모/늘임 무시, error_profile
- **`tts.py`** (F-AV-02) — ElevenLabs 작가별 음성, 첫 문장 낭독
- `evaluate.py`(LLM-judge 4축) · `world_tag_classifier.py`(F-WD-06) · `llm_router.py`·`llm.py`(엔진·폴백 체인)·`cache.py`

### `app/core/` · `app/prompts/`
- `personas.py`(작가 4인 리치 프롬프트·문체) · `reactions.py`(작가×감정 리액션 풀) · `prompts/`(출력/입력 규칙·멀티NPC·suggest/stuck 시스템)

### `migrations/`
- Alembic. `env.py`가 `.env`의 `DATABASE_URL` 단일 소스. head = `o5p6q7r8s9t0`(worlds.relations). 배포는 자동 마이그레이션 안 함 → `alembic upgrade head` 별도

---

## 요청 처리 흐름

### 일반 CRUD (예: 세계관 생성)
```
POST /api/v1/worlds?user_id=…
  → router → worlds.create_world()
  → schemas.WorldCreate (검증, 실패 시 422)
  → get_db() AsyncSession → World 인스턴스 → add/flush/refresh
  → schemas.WorldResponse → 201 JSON
```

### 채팅 스트리밍 (구조화 SSE) ★
```
GET /api/v1/chats/{id}/stream?content=&character_id=&mode=&speaker=&check_consistency=
  → chats.stream_response()
     ├─ get_context()         최근 대화/상태/요약(Redis, 없으면 DB 복원)
     ├─ _build_world_context  ★항상 DB에서 재구성(프론트 전송값 무시 → 세계관 수정 즉시 반영)
     ├─ memory.retrieve_relevant   RAG 의미검색(오래된 사건)
     ├─ build_messages(persona, world, context, speaker)  ← 다중 인물 화자 배분 규칙 포함
     ▼
     llm.generate/stream(system, contents, json_mode=True)   프로바이더 체인·폴백
     ├─ event: delta  (narration 토큰 즉시 흘림 → 체감 TTFB↓)
     ├─ event: reply  (narration·dialogue·memories·consistency)  ← check_consistency면 검수 RAG 결과 동봉
     ├─ event: audio  (tts 첫 문장, base64)  ※ 키/IP 차단 시 생략
     └─ event: done
   ※ DB 저장·요약은 reply 뒤로 deferral(TTFB 단축)
```
> 채팅·소설은 **JSON 모드**로 구조화 응답을 받아 프론트가 나레이션/대사를 분리·타자기 렌더.
> 검수: `consistency` 필드(`{consistent, violations:[{established,conflict,severity}]}`)를 프론트가 **🔍 '설정↔충돌' alert**로 화면 노출(라이브 토글).

---

## LLM 엔진 연동 구조

```
llm.generate(system, contents, json_mode)
   │  프로바이더 체인 = LLM_PROVIDER_CHAIN (예: gemini,groq,openai)
   ▼
 ┌─ USE_VERTEX=true → Vertex AI Gemini 2.5 Flash-lite (ADC, thinking off)
 │      └─ 실패(429/auth/transient) → 키 순환·쿨다운·다음 프로바이더
 ├─ Groq (Llama 3.3)        ← 폴백
 └─ OpenAI (GPT)            ← 폴백
```
- **Vertex 전환 효과**: 응답 8s→~2s, Groq의 한자/일본어 언어누수 해소
- 임베딩: Gemini `text-multilingual-embedding-002`(768d) + 인앱 코사인(별도 벡터DB 없이 단편 규모 충분, 대규모 시 pgvector)

프롬프트 구성:
```
system = 출력/입력 규칙 + 작가 페르소나(personas.py) + 문체 RAG few-shot
context = [등장인물] + [사건 요약] + [작가 메모] + [관련 기억(RAG)] + [현재 상태] + 최근 N턴
user    = (speaker 지정 시) 화자 지시 + 사용자 입력
```

---

## 배포 / 운영

- **백엔드**: Cloud Run(`nodevelture-api`, us-central1). `--source`로 Dockerfile 빌드, 시크릿은 Secret Manager, Vertex는 런타임 SA(ADC). 배포 시 **`alembic upgrade head` 동반 필수**(모델·DB 정합)
- **프론트**: Vercel(정적 SPA). `apiBase`가 배포 환경에서 `VITE_API_BASE_URL`로 백엔드 직접 호출
- 상세·트러블슈팅: [server-ops.md](server-ops.md)
