<!-- markdownlint-disable MD022 MD031 MD032 MD040 MD060 -->
# NodeVelture

> **AI 빙의작가** — 작가 캐릭터와 놀듯 대화하면, 진짜 *내 소설*이 되는 협업 창작 서비스
> AI휴먼 캠프 4기 · 1팀(woawoal)

---

## 한 줄 소개

성격·문체가 뚜렷한 **AI 작가 4인** 중 하나를 골라, 내가 주인공이 되어 대화하듯 이야기를 만들면 → 그 대화가 **작가의 문체로 쓰인 단편 소설**로 완성됩니다.

> **ChatGPT가 "밖에서 지시하는 도구"라면, NodeVelture는 "이야기 안에서 함께 쓰는 동료 작가"입니다.**
> - character.ai = 캐릭터 놀이는 있지만 *결과물(소설)*이 없다
> - Sudowrite = 창작 도구지만 *캐릭터와 노는 재미*가 없다
> - **NodeVelture = 둘을 잇는 다리** — "놀듯 대화 → 진짜 내 소설"

서비스의 **척추**는 *진지한 창작 도구*("혼자 쓰는 것보다 좋은 소설이 나온다"), **껍데기**는 *엔터테인먼트*(작가 페르소나·테마·아바타)로 사용자를 끌어들입니다.

---

## 서비스 흐름

```
[1단계] 작가 선택 + 세계관 작성        작가 4인 중 선택 → 장르·배경·등장인물 입력
   │                                  (작가별 테마 적용 / 세계관 태그 자동분류)
   ▼
[2단계] 대화형 창작                     사용자 = 1인칭 주인공 (@등장인물로 다른 인물도 연기)
   │                                  → AI가 작가 문체로 서술/대사 응답
   │                                  → RAG 일관성 · 어시스턴트 유도 · 작가 리액션 · 오탈자 교정
   ▼
[3단계] 소설 변환 → 읽기 → 삽화          채팅 종료 → 작가 문체 단편 소설로 변환
                                      → 일관성 검수 → 읽기(챕터·진행률·txt) → 장면 삽화 생성
```

---

## 작가 4인 (페르소나)

| 작가 | 장르 | 문체·성격 |
|------|------|-----------|
| **백야** | 호러 / 미스터리 | 짧고 단절적인 문장, 여백과 침묵의 미학. 감정을 직접 말하지 않는다 |
| **차로운** | 본격 추리 | 관찰자 시점, 행동·사실 먼저, 치밀한 복선. 논리적이고 까칠함 |
| **한여름** | 로맨스 | 신체 반응·감각 묘사(심장·호흡·시선), 감정선과 여운 |
| **김도현** | 일상 / 에세이 | 낮은 시선, 작은 디테일, 담담함. 결론을 내지 않는 사색 |

각 작가는 말투·가치관·문체·금기가 정의된 리치 프롬프트(`personas.py`)와 문체 샘플로 구동됩니다.

---

## 핵심 차별점 (3축)

### 1. RAG 3종 — "길어져도 안 까먹는다"

| 모듈 | 역할 |
|------|------|
| **기억** (`memory.py`) | 누적 요약 + **의미검색(top-K)** 으로 과거 설정·사건을 검색해 주입 → 긴 대화에서도 세계관 일관성 유지 |
| **검수** (`consistency.py`) | 새 응답을 확립된 설정·기억과 대조해 **모순 탐지**(LLM JSON) |
| **문체** (`style.py`) | 작가별 문체 샘플 중 장면과 가장 가까운 예시를 **few-shot 검색**해 소설 변환에 주입 |

> 임베딩(Gemini `text-multilingual-embedding-002`, 768차원) + 인앱 코사인 유사도. 대규모 시 pgvector로 확장 가능.

### 2. AI 어시스턴트 — "혼자 쓰는 것보다 낫다"

- **💡 문장 추천**(`/suggestions`·`/voice-suggest`) — 막막할 때 **내 말투(voice 프로파일) 기반**으로 다음 대사를 추천 → 클릭하면 입력창에 채워짐 (백지 공포 해결)
- **다음 전개 제안**(`/suggest`) · **막힘 도움**(`/stuck`) — 막혔을 때 행동/대사 후보 제시
- **작가 리액션**(`/reaction`) — 사용자 대사에 작가가 즉각 짧게 반응('흥미로운데?')
- **조연 다중 반응**(`/npc-react`) — 여러 조연이 각자 페르소나로 동시 반응

### 3. 정량 근거 — "맨손 작성 vs 우리 서비스"

- LLM-as-Judge 4축(세계관·캐릭터 일관성, 문체 뚜렷함, 완성도) 채점(`evaluate.py`)
- 페르소나 구분도 측정(`scripts/persona_eval.py`) · 근거 리포트(`scripts/evidence_report.py`)

---

## 주요 기능

- 🎭 **작가별 테마** — 작가 선택 시 전 화면 색/분위기 전환(새로고침에도 유지)
- ⌨️ **타자기 효과** — 응답이 한 글자씩 흘러나와 "함께 쓰는" 느낌
- 💡 **문장 추천(말투 기반)** — 막막할 때 내 말투(voice 프로파일)로 다음 대사를 추천 → 클릭해 입력
- 🗣️ **TTS 낭독** — 응답 첫 문장을 작가 목소리로(`tts.py`, SSE `event:audio`)
- 💬 **작가 리액션 자막** — 사용자 대사에 작가가 즉각 반응(사진 위 영화 자막 스타일)
- 📝 **작가 메모** — 메모를 작성하면 이후 응답 프롬프트에 즉시 주입
- 🔍 **일관성 검수** — 설정 모순을 잡아 알려줌
- ✏️ **오탈자 교정 / 오답노트(예측형)** — 작가가 '여백 메모'처럼 맞춤법을 짚어줌. **창작 고유명사 보호**·실시간 토글·개인 오답노트 + **능동 경고**(글쓰기 진입 시 자주 틀리는 것 미리 짚음 — 반응형→예측형)
- 🎭 **@등장인물 멘션** — `@이름`으로 주인공 외 다른 인물로도 대사 입력 → 작가AI가 그 인물 시점·서사로 전개. **멀티워드 이름·주인공 @지정**도 지원
- 🎯 **화자 고정·장면 일관성** — 응답 화자가 안 흔들리고(검증+프롬프트 2겹), **떠나거나 부재한 인물이 대사하지 않음**(혼자 장면 = 나레이션만)
- 🖼️ **장면 삽화 생성** — 소설 장면을 삽화로(**Vertex Gemini 2.5 Flash Image**, 비전) → 내 삽화에 저장
- 📚 **마이페이지(내 서재)** — 대시보드·취향 프로필·설정집·문장 보관함·오답노트·AI 작가 기록
- ✒️ **집필형 에디터** — 채팅↔원고 전환, 자동저장·실시간 교정·작가 피드백
- 📊 **토큰 사용량 분석**(`/api-logs`) — 세션·모델별 토큰/비용 집계
- 🔐 **로그인** — Neon Auth(이메일 OTP)
- 📖 **소설 읽기** — 챕터 목차·글자 크기·진행률·**txt 내보내기**

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | React 19 + Vite, react-router, react-markdown, Neon Auth(`@neondatabase/neon-js`) |
| **Backend** | FastAPI (Python 3.11), SQLAlchemy(async) + asyncpg, Alembic, Pydantic |
| **DB** | PostgreSQL — **Neon**(클라우드 공용) |
| **Cache / 세션** | Redis — **Upstash** |
| **LLM 엔진** | **Vertex AI Gemini 2.5 Flash-lite**(ADC) — Groq / OpenAI 폴백(`LLM_PROVIDER_CHAIN`) |
| **임베딩 / RAG** | Gemini `text-multilingual-embedding-002` + 인앱 코사인 |
| **삽화(비전)** | **Vertex Gemini 2.5 Flash Image** — 소설 장면 → 이미지(ADC·GCP 크레딧), 세션별 DB 저장 |
| **음성(TTS)** | ElevenLabs — 작가별 음성으로 첫 문장 낭독 |
| **배포** | 백엔드 GCP **Cloud Run**(Dockerfile + Secret Manager, Vertex는 ADC 자동) · 프론트 **Vercel**(정적 SPA·CDN) |

### 아키텍처

```
                         ┌──────────────────────────────┐
  React + Vite  ──────▶  │   FastAPI (app.main)         │
  (작가/세계관/채팅/읽기)  │   · /chats /sessions /novels │
        ▲                │   · RAG(기억·검수·문체)        │
        │  SSE/REST      │   · 어시스턴트·리액션·TTS       │
        │                └──────┬───────────┬───────────┘
   Neon Auth                    │           │
   (로그인)             ┌────────▼──┐   ┌────▼─────────┐   ┌──────────────┐
                        │ PostgreSQL│   │  Redis        │   │ Vertex AI     │
                        │  (Neon)   │   │ (Upstash)     │   │ Gemini 2.5    │
                        │ 영속 데이터 │   │ 대화 컨텍스트   │   │ 생성·임베딩    │
                        └───────────┘   └───────────────┘   └──────────────┘
```

LLM 호출(`services/llm.py`)은 **프로바이더 체인 → 모델 → 키 순회 + 429/auth/transient 분기·쿨다운·폴백**을 일원화하고, 채팅 응답은 JSON 모드(서술/대사 구조화)로 받습니다.

---

## 로컬 실행

### 사전 준비
- Python 3.11 (conda 권장)
- Node.js 18+
- Neon(PostgreSQL) · Upstash(Redis) 계정 — 또는 로컬 docker
- LLM: GCP 프로젝트 + Vertex(ADC) **또는** Gemini/Groq API 키

### 백엔드
```bash
conda create -n nodevelture python=3.11 -y
conda activate nodevelture
cd backend
pip install -r requirements.txt

# .env 작성 (아래 예시 참고)
alembic upgrade head            # 테이블 마이그레이션
python -m uvicorn app.main:app --reload   # http://localhost:8000
```

`backend/.env` 예시:
```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<pw>@<neon-host>/<db>?ssl=require
REDIS_URL=rediss://<upstash-url>

# LLM — Vertex 사용 시 (키 불필요, ADC)
USE_VERTEX=true
GOOGLE_CLOUD_PROJECT=<gcp-project-id>
GOOGLE_CLOUD_LOCATION=us-central1
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-2.5-flash
LLM_PROVIDER=gemini
LLM_PROVIDER_CHAIN=gemini,groq      # 폴백 체인
# GROQ_API_KEY / OPENAI_API_KEY ... (폴백용)
```
> Vertex(ADC) 인증·트러블슈팅은 [`backend/docs/server-ops.md`](backend/docs/server-ops.md) 참고.

### 프론트엔드
```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

`frontend/.env` 예시:
```dotenv
VITE_API_BASE_URL=http://localhost:8000/api    # 배포 시엔 Cloud Run 주소(…/api)
VITE_NEON_AUTH_URL=https://<neon-auth-endpoint>/neondb/auth
```

---

## 프로젝트 구조

```
NodeVelture/
├── backend/                 # FastAPI 서버
│   ├── app/
│   │   ├── api/v1/endpoints/ # chats · sessions · novels · worlds · characters · authors · users · api_logs · proofread · mypage · taste · illustrations · author_chat
│   │   ├── core/            # config · personas · reactions
│   │   ├── models/          # SQLAlchemy 모델 (user·session·world·character·dialogue·novel·api_log·illustration·saved_sentence·user_taste)
│   │   ├── services/        # llm · memory(RAG) · consistency · style · evaluate · tts · proofread · illustration(Vertex 비전) · llm_router
│   │   └── prompts/         # 시스템 프롬프트
│   ├── scripts/             # rag/consistency/style_demo · persona_eval · evidence_report · completion_rate · ttfb_eval · cer_eval · e2e_smoke
│   ├── alembic/             # DB 마이그레이션
│   └── docs/                # setup · server-ops · architecture · api · models
├── frontend/                # React + Vite (src/pages · src/lib · src/hooks)
├── data/                    # world_tags.json 등 데이터
├── docs/                    # 기능정의서 · 업무분담 · 사용자_시나리오 · scrum · personas
└── model/                   # (실험) 파인튜닝 스텁
```

---

## 팀 — 1팀(woawoal)

| 역할 | 담당 |
|------|------|
| 백엔드 · LLM 파이프라인 · RAG | 지윤정, 윤가연 |
| 프론트엔드 | 박가은, 유건혁 |
| AI — 프롬프트 설계 | 김동완 |

> **기능 단위 책임제** — 한 기능(F-ID)을 한 사람이 백엔드·DB·프론트·프롬프트까지 end-to-end로 담당.

---

## 문서

- [기능정의서](docs/기능정의서.md) — 전체 기능(F-ID)·정의·상태
- [업무분담](docs/업무분담.md) — 담당자별 진행 현황
- [사용자 시나리오](docs/사용자_시나리오.md)
- [서버 운영·트러블슈팅](backend/docs/server-ops.md) · [셋업](backend/docs/setup.md)
- [스크럼 기록](docs/scrum/scrum.md)
