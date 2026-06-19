# NodeVelture 환경 세팅 & 실행 가이드

## 구조 개요

```
NodeVelture/
├── frontend/          # React + Vite (포트 5173)
│   └── api/tts.js     # Vercel 서버리스 함수 (TTS 프록시)
├── backend/           # FastAPI + Python (포트 8000)
└── docker-compose.yml # Redis (로컬)
```

**DB:** Neon (PostgreSQL 클라우드) — 로컬 전환 시 docker-compose.yml 주석 해제  
**Redis:** Docker로 로컬 실행  
**TTS:** Vercel 서버리스 (`/api/tts`) — ElevenLabs 키를 서버사이드에서 관리

---

## 1. 사전 준비

- Node.js 18+
- Python 3.11+
- Docker Desktop (Redis용)

---

## 2. Redis 실행

```bash
docker-compose up -d redis
```

확인:
```bash
docker-compose ps
```

---

## 3. 백엔드

### 3-1. 가상환경 & 패키지 설치

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3-2. 환경변수 설정

`backend/.env` 파일 생성:

```env
# DB (Neon 클라우드 — Neon 대시보드에서 복사)
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>/nodevelture

# Redis (로컬 Docker)
REDIS_URL=redis://localhost:6379

# LLM 엔진 선택 (gemini | groq | openai)
LLM_PROVIDER=gemini

# Gemini (Primary)
GEMINI_API_KEY=<your-key>
GEMINI_API_KEY_2=<your-key-2>           # 선택 (키 순환용)
GEMINI_API_KEYS=key1,key2,key3          # 선택 (복수 키)
GEMINI_MODEL=gemini-2.0-flash-lite
GEMINI_FALLBACK_MODEL=gemini-2.0-flash

# Groq (Gemini 429 폴백용 — 선택)
GROQ_API_KEY=<your-key>
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI (선택)
OPENAI_API_KEY=<your-key>
OPENAI_MODEL=gpt-4o-mini

# 프로바이더 체인 (순서대로 폴백, 선택)
# 예: gemini 먼저, 실패 시 groq
LLM_PROVIDER_CHAIN=gemini,groq

# 삽화 생성 — fal.ai (선택)
FAL_KEY=<your-key>

# ElevenLabs TTS (선택 — Vercel에도 동일하게 설정)
ELEVENLABS_API_KEY_1=<your-key>
ELEVENLABS_API_KEY_2=<your-key>

# Vertex AI (GCP 사용 시만 — 기본은 Gemini API 키 방식)
USE_VERTEX=false
GOOGLE_CLOUD_PROJECT=
GOOGLE_CLOUD_LOCATION=us-central1
```

### 3-3. DB 마이그레이션

```bash
cd backend
alembic upgrade head
```

### 3-4. 백엔드 실행

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 4. 프론트엔드

### 4-1. 패키지 설치

```bash
cd frontend
npm install
```

### 4-2. 환경변수 설정

`frontend/.env.local` 파일 생성:

```env
# 백엔드 API 주소
VITE_API_BASE_URL=http://localhost:8000/api/v1

# Neon Auth (회원가입/로그인 — Neon 대시보드에서 복사)
VITE_NEON_AUTH_URL=https://<project>.neon.tech
```

### 4-3. 프론트엔드 실행

```bash
npm run dev
```

브라우저: `http://localhost:5173`

---

## 5. TTS (로컬 개발 시)

`/api/tts`는 Vercel 서버리스 함수라 로컬에서는 404가 정상.  
음성 없이 나머지 기능은 모두 동작함.

**실제 TTS가 필요하면** Vercel CLI로 로컬 실행:

```bash
npm install -g vercel
cd frontend
vercel dev   # .env.local의 ELEVENLABS_API_KEY_* 를 읽어옴
```

Vercel 프로젝트 환경변수에도 동일하게 설정 필요 (서버사이드, `VITE_` 접두사 없이):
```
ELEVENLABS_API_KEY_1=...
ELEVENLABS_API_KEY_2=...
```

---

## 6. 전체 실행 순서 요약

```bash
# 터미널 1 — Redis
docker-compose up -d redis

# 터미널 2 — 백엔드
cd backend && venv\Scripts\activate && uvicorn app.main:app --reload --port 8000

# 터미널 3 — 프론트엔드
cd frontend && npm run dev
```

---

## 7. 자주 쓰는 명령

```bash
# DB 마이그레이션 새로 만들기
alembic revision --autogenerate -m "설명"
alembic upgrade head

# Redis 초기화
docker-compose down -v && docker-compose up -d redis

# 백엔드 로그 (레벨 조정)
LOG_LEVEL=debug uvicorn app.main:app --reload

# 프론트 빌드 (배포용)
cd frontend && npm run build
```

---

## 8. 핵심 포트 & 서비스 정리

| 서비스 | 주소 | 비고 |
|---|---|---|
| 프론트엔드 | http://localhost:5173 | Vite dev server |
| 백엔드 API | http://localhost:8000 | FastAPI |
| API 문서 | http://localhost:8000/docs | Swagger UI |
| Redis | localhost:6379 | Docker |
| PostgreSQL | Neon 클라우드 | DATABASE_URL에서 관리 |
| TTS | /api/tts | Vercel 서버리스 |
