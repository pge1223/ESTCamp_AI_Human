# NodeVelture — Backend

사용자가 AI와 함께 세계관·등장인물을 설계하고, 그 세계관 속 **주인공이 되어** 조연(AI)과 대화하며 이야기를 만든다. 대화가 끝나면 **작가 문체의 소설 초안**으로 자동 변환된다.

차별점은 범용 LLM이 못/안 하는 **RAG 3종** — ① 장기기억 ② 설정 검수 ③ 문체 — 을 붙여 *길어져도 일관성이 무너지지 않게* 하는 것.

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 프레임워크 | FastAPI (async / **SSE 토큰 스트리밍**) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| DB | PostgreSQL (운영: **Neon**, 로컬: Docker Postgres) |
| 캐시/상태 | Redis (운영: **Upstash**) |
| AI 엔진 | **Vertex AI Gemini (Flash-lite, ADC 키리스)** · 폴백 체인 **Gemini → Groq → OpenAI** |
| 임베딩 | Gemini 임베딩 (RAG 의미검색, 인앱 코사인 top-K) |
| 배포 | **GCP Cloud Run** (`--source` Dockerfile 빌드) |

> 엔진은 환경변수로 스위칭한다 — `LLM_PROVIDER`(gemini|groq|openai) · `USE_VERTEX`(ADC) · `LLM_PROVIDER_CHAIN`(폴백 순서). 한 엔진이 막혀도 다음 후보로 자동 승계.

---

## 전체 흐름

```
┌─────────────┐   REST / SSE(스트리밍)   ┌──────────────────────────┐
│  Frontend   │ ───────────────────────▶ │  FastAPI (Cloud Run)     │
└─────────────┘                          └────────────┬─────────────┘
                          ┌───────────────────────────┼───────────────────────┐
                          ▼                            ▼                       ▼
                 ┌────────────────┐         ┌────────────────┐      ┌────────────────────┐
                 │ Postgres(Neon) │         │  Redis(Upstash)│      │ Vertex AI Gemini   │
                 │ 대화·소설·로그  │         │ 히스토리·캐시   │      │ (폴백 Groq/OpenAI)  │
                 └────────────────┘         └────────────────┘      └────────────────────┘
```

### AI 파이프라인 (한 턴)

```
사용자 입력(주인공)
  └▶ get_context (Redis: history·summary·state·memos·phase)
     + world_context (DB에서 항상 재구성 → 세계관 수정 즉시 반영)
     + 기억 RAG (memory.retrieve_relevant — 오래된 설정 의미검색)
        ▼ LLM (json 구조화 · 토큰 스트리밍)
     {narration, dialogue, speaker, state}
        ├▶ 설정 검수 RAG (consistency.check) → 모순 시 화면 '설정↔충돌' alert
        └▶ Redis/DB 저장 · ApiLog(토큰·비용) 기록  ※저장·요약은 응답 뒤로 deferral
「채팅 종료」 → 대화 로그 ─[문체 RAG few-shot]→ 작가 문체 단편소설
```

---

## 주요 API (prefix: `/api/v1`)

전체 명세는 서버 실행 후 **Swagger UI** `http://localhost:8000/docs` 참고.

| 영역 | 엔드포인트(대표) |
|------|------------------|
| 세계관 | `POST/PUT/GET /worlds` · `…/worlds/{id}/characters` |
| 세션 | `POST/GET /sessions` · `…/sessions/{id}/dialogues` |
| **채팅(창작)** | `POST /chats/{id}/messages` · **`GET /chats/{id}/stream`** (SSE) |
| 작가 보조 | `…/chats/{id}/suggestions` · `/voice-suggest` · `/reaction` · `/author/message` · `/author/rewrite` |
| 취향/개인화 | `…/chats/{id}/taste-recommend` · `/mypage/*` |
| 검수/교정 | `…/chats/{id}/proofread` · `/error-warmup` · `/glossary` |
| 소설 변환 | `POST /sessions/{id}/novel/convert` |
| 삽화 | `…/sessions/{id}/illustrations` · `/illustrations/generate-openai` |
| 운영 | `/api-logs` (호출·토큰·비용 로그) · `/authors` · `/world-examples` |

---

## 빠른 시작

```bash
# 1. 가상환경
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)

# 2. 패키지
pip install -r requirements.txt

# 3. 환경변수
cp .env.example .env           # DB·Redis·LLM 키 채우기 (아래 참고)

# 4. (로컬) DB·Redis 컨테이너
docker-compose up -d

# 5. 마이그레이션 적용 (이미 정의돼 있음 — autogenerate 불필요)
alembic upgrade head

# 6. 서버
uvicorn app.main:app --reload
```

접속: `http://localhost:8000/docs` (Swagger) · 헬스체크: `GET /health`

### 필수 환경변수(.env)

```
DATABASE_URL=postgresql://...        # Neon은 끝에 ?sslmode=require
REDIS_URL=redis://...                # Upstash
# AI 엔진 (택1 이상)
USE_VERTEX=true                      # GCP ADC(키리스) — 운영 권장
GEMINI_API_KEY=...                   # 또는 키 방식
GROQ_API_KEY=...  /  OPENAI_API_KEY=...   # 폴백·평가용
LLM_PROVIDER_CHAIN=gemini,groq,openai
# 멀티모달(선택)
FAL_KEY=...   ELEVENLABS_API_KEY_1=...
```

---

## 폴더 구조

```
backend/
├── app/
│   ├── main.py              # 앱 시작점 · 라우터 등록 · /health
│   ├── database.py          # async 엔진 / 세션
│   ├── core/                # config(환경변수) · personas(작가 4인) · 프롬프트 상수
│   ├── models/              # DB 모델 (world·character·session·dialogue·novel·user·api_log·taste…)
│   ├── schemas/             # Pydantic 입출력
│   ├── api/v1/endpoints/    # 라우터 (chats·worlds·sessions·novels·illustrations·proofread·mypage…)
│   ├── services/            # 핵심 로직 — llm·memory(기억)·consistency(검수)·style(문체)·personalize·evaluate·proofread
│   └── prompts/             # 장르/스토리 프롬프트 템플릿
├── scripts/                 # 정량평가 (아래)
├── migrations/              # Alembic
├── docs/                    # 상세 문서 · server-ops
├── docker-compose.yml · alembic.ini · Dockerfile · requirements.txt
```

---

## 정량평가 (재현)

`backend/` 에서 `python -m scripts.<이름>` (conda/venv + `.env` 필요). 채점·라벨은 **독립 모델(Groq/Llama)**.

| 스크립트 | 측정 | 비고 |
|----------|------|------|
| `rag_recall_eval` | 장기기억 검색 (방해 비밀 경쟁) | top-1 정밀도 |
| `consistency_eval` | 설정 모순 탐지 (독립 교차라벨) | 합의셋 정확도 |
| `personalize_e2e` | 저장 톤 → 추천 톤 인과 | DARK/WARM/NONE |
| `testset_eval` | 균형 40문항(일상·페르소나·엣지·안전) | 카테고리별 |
| `evidence_report` | 맨손 vs 우리 변환 | JSON 저장 |
| `ttfb_eval` · `completion_rate` · `cer_eval` | 시스템·음성 지표 | TTFB / 완료율 / CER |

> 종합 결과·해석: [`docs/발표_정량근거.md`](../docs/발표_정량근거.md)

---

## 배포 (Cloud Run)

`backend/` 에서:

```bash
gcloud run deploy nodevelture-api --source . \
  --region us-central1 --project nodevelture-499003 --allow-unauthenticated \
  --update-secrets "DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,FAL_KEY=FAL_KEY:latest"
```

- 시크릿 값엔 `KEY=` 접두사·줄바꿈 금지(컨테이너 기동 실패 원인).
- 배포는 마이그레이션을 자동 실행하지 않음 → 스키마 변경 시 `alembic upgrade head` 별도 실행.
- 좌표·게이트키퍼 상세: [`docs/server-ops.md`](docs/server-ops.md)

---

## 문서

| 문서 | 내용 |
|------|------|
| [아키텍처](docs/architecture.md) | 전체 구조·레이어·데이터 흐름 |
| [DB 모델](docs/models.md) | 테이블 명세·ERD |
| [API 명세](docs/api.md) | 엔드포인트 요청/응답 |
| [환경 설정](docs/setup.md) | 로컬·Docker·Alembic |
| [운영/배포](docs/server-ops.md) | Cloud Run 배포·시크릿·게이트키퍼 |
| [코딩 규칙](docs/coding-rules.md) | 컨벤션·패턴 |
