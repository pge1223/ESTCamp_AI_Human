<!-- markdownlint-disable MD022 MD028 MD031 MD032 MD034 MD040 -->
# 환경 설정 가이드

## 사전 준비

| 항목 | 버전 | 확인 명령어 |
|------|------|------------|
| Miniconda / Anaconda | 최신 | `conda --version` |
| Python | 3.11 (conda 환경) | `python --version` |
| Docker Desktop | 최신 | `docker --version` |
| Git | - | `git --version` |
| ngrok | 최신 (팀 공유용) | `ngrok version` |

> 팀 표준은 **conda 가상환경**입니다. Python 3.13에서는 asyncpg / pydantic-core 빌드가 실패하므로 반드시 **3.11**로 맞춥니다.

---

## 한눈에 보는 실행 순서 (TL;DR)

```powershell
# 1. DB/Redis 컨테이너 켜기
docker compose -f backend/docker-compose.yml up -d

# 2. conda 환경 활성화
conda activate nodevelture

# 3. (최초 1회 / 모델 변경 시) DB 테이블 생성
cd backend
alembic upgrade head

# 4. 앱 켜기  (conda의 uvicorn을 쓰려면 'python -m' 필수)
python -m uvicorn app.main:app --reload

# 5. 동작 확인  →  http://localhost:8000/health  →  {"status":"ok"}

# (선택) 팀원 공유 — 새 터미널에서
ngrok http --url=<고정도메인>.ngrok-free.app 8000
```

아래는 각 단계 상세 설명입니다.

---

## 로컬 개발 환경 세팅 (최초 1회)

### 1. 저장소 클론
```powershell
git clone {repo-url}
cd NodeVelture/backend
```

### 2. conda 가상환경 생성 및 활성화
```powershell
conda create -n nodevelture python=3.11
conda activate nodevelture
```

> 활성화되면 터미널 프롬프트 앞에 `(nodevelture)` 표시가 나타납니다.
> 다음부터는 `conda activate nodevelture` 한 줄이면 됩니다.

### 3. 패키지 설치
```powershell
pip install -r requirements.txt
```

### 4. 환경변수 설정
```powershell
copy .env.example .env
```

`.env` 파일을 열어 값을 채웁니다:
```env
DATABASE_URL=postgresql+asyncpg://nodevelture:nodevelture@localhost:5432/nodevelture

# Redis — 활성화된 한 줄만 사용 (전환 시 주석 토글 + 서버 재시작 필수)
# [로컬 도커]
REDIS_URL=redis://localhost:6379
# [Upstash 클라우드] — 도커 안 켜질 때 이 줄을 활성화하고 위 줄을 주석 처리
# REDIS_URL=rediss://default:...@xxxx.upstash.io:6379

CACHE_TTL=3600

# AI 엔진 — 키 방식(로컬) 또는 USE_VERTEX(운영, GCP ADC 키리스)
GEMINI_API_KEY=발급받은_키_입력
# USE_VERTEX=true                # 운영: Vertex AI(ADC). 로컬은 보통 GEMINI_API_KEY로 충분
LLM_PROVIDER_CHAIN=gemini,groq,openai   # 폴백 순서
GROQ_API_KEY=                    # 폴백·평가 채점관(독립 모델)
OPENAI_API_KEY=                  # 폴백·진짜 GPT 비교용(크레딧 필요)

# 멀티모달(선택)
FAL_KEY=                         # 삽화(fal.ai)
ELEVENLABS_API_KEY_1=            # TTS(작가 음성)

SECRET_KEY=로컬개발용_랜덤문자열
DEBUG=true
ALLOWED_ORIGINS=["*"]
```

> ⚠️ `.env` 값은 `--reload`로 자동 반영되지 않습니다. **수정하면 서버를 재시작**하세요.
> ⚠️ 도커 ↔ 클라우드 전환은 `REDIS_URL` 두 줄의 주석만 토글하면 됩니다.

---

## conda 환경 메모

- 앱(uvicorn)은 **conda 환경**에서 실행하고, DB·Redis는 **도커 컨테이너**에서 돕니다. 둘은 다른 층이라 **항상 같이** 켜져 있어야 합니다.
- conda 환경에서 `uvicorn ...`을 바로 치면 전역(py3.13) uvicorn이 잘못 잡힐 수 있으니, **`python -m uvicorn ...`** 형태로 실행해 환경을 일치시킵니다.
- 환경 비활성화: `conda deactivate`

---

## Docker 사용법

Docker는 PostgreSQL과 Redis를 내 PC에 직접 설치하지 않고 컨테이너로 실행하는 방법입니다.
**즉 도커 컨테이너가 곧 PostgreSQL/Redis 서버라서, 별도 설치가 필요 없습니다.**

> 명령어는 `backend` 폴더에서 실행하거나, 어디서든 `-f backend/docker-compose.yml`을 붙이세요.

### 컨테이너 시작
```powershell
docker compose up -d
```
> `-d` 옵션 : 백그라운드 실행 (터미널이 잠기지 않음)

### 컨테이너 상태 확인
```powershell
docker compose ps
```
```
NAME       STATUS    PORTS
db         running   0.0.0.0:5432->5432/tcp
redis      running   0.0.0.0:6379->6379/tcp
```

### 컨테이너 로그 보기
```powershell
docker compose logs db      # PostgreSQL 로그
docker compose logs redis   # Redis 로그
docker compose logs -f      # 전체 로그 실시간
```

### 컨테이너 중지 / 재시작
```powershell
docker compose stop         # 중지 (데이터 유지)
docker compose start        # 재시작
docker compose restart      # 재시작 (stop + start)
```

### 컨테이너 완전 삭제
```powershell
docker compose down         # 컨테이너만 삭제 (데이터 볼륨 유지)
docker compose down -v      # 컨테이너 + 데이터 볼륨 전부 삭제
```
> `-v` 옵션은 DB 데이터도 전부 삭제되므로 주의

> 💡 도커가 안 켜질 때: `.env`의 `REDIS_URL`을 Upstash 클라우드 줄로 토글하면 Redis는 도커 없이 동작합니다. (단, PostgreSQL은 도커 또는 클라우드 DB가 필요)

---

## Alembic 마이그레이션

모델(`app/models/`)을 변경할 때마다 마이그레이션을 생성하고 적용해야 DB에 반영됩니다.
도커 postgres는 처음 뜨면 **빈 DB**이므로, 최초 1회 `alembic upgrade head`로 테이블을 만들어야 대화 저장이 동작합니다.

### 처음 실행 (초기 테이블 생성)
```powershell
alembic upgrade head
```

### 모델 변경 후 마이그레이션 흐름
```powershell
# 1. app/models/ 에서 모델 수정

# 2. 변경사항 감지 → 마이그레이션 파일 자동 생성
alembic revision --autogenerate -m "변경 내용 설명"
# 예: alembic revision --autogenerate -m "add user profile image"

# 3. 생성된 파일 확인 (migrations/versions/ 폴더)
# 내용이 맞는지 반드시 눈으로 확인 후 적용!

# 4. DB에 적용
alembic upgrade head
```

### 자주 쓰는 Alembic 명령어
```powershell
alembic upgrade head        # 최신 버전으로 업그레이드
alembic downgrade -1        # 한 단계 롤백
alembic current             # 현재 DB 마이그레이션 버전 확인
alembic history             # 전체 마이그레이션 이력 조회
```

---

## 서버 실행

```powershell
# 개발 모드 (코드 변경 시 자동 재시작) — conda 환경에서 python -m 권장
python -m uvicorn app.main:app --reload

# 특정 포트 지정
python -m uvicorn app.main:app --reload --port 8001

# 외부 접속 허용 (LAN 등에서 직접 접근 시)
python -m uvicorn app.main:app --reload --host 0.0.0.0
```

| 주소 | 내용 |
|------|------|
| `http://localhost:8000` | API 서버 |
| `http://localhost:8000/docs` | Swagger UI (API 테스트) |
| `http://localhost:8000/redoc` | ReDoc 문서 |
| `http://localhost:8000/health` | 헬스체크 |

---

## ngrok으로 팀원 공유하기

로컬에서 띄운 서버(`localhost:8000`)를 외부 공개 URL로 노출해, 프론트엔드 팀원이 접속할 수 있게 합니다.
프론트는 `VITE_API_BASE_URL` 환경변수로 백엔드 주소를 잡으므로, **팀원은 이 값만 ngrok 주소로 바꾸면** 됩니다. (CORS는 `["*"]`라 별도 설정 불필요)

### 0. 최초 1회 — 설치 및 토큰 등록
```powershell
winget install ngrok.ngrok
ngrok config add-authtoken <ngrok_대시보드의_authtoken>
```

### 1. 고정 도메인 만들기 (강력 추천)
무료 플랜도 **고정 도메인 1개**를 제공합니다. 고정 도메인을 쓰면 서버를 껐다 켜도 주소가 그대로라, 팀원이 `.env`를 매번 고칠 필요가 없습니다.

1. https://dashboard.ngrok.com 접속 → 로그인
2. 좌측 메뉴 **Domains** → **+ New Domain** (또는 Create Domain)
3. 발급된 도메인 복사 (예: `nodevelture-jyj.ngrok-free.app`)

### 2. 고정 도메인으로 실행
```powershell
ngrok http --url=nodevelture-jyj.ngrok-free.app 8000
```
> 구버전 ngrok은 `--url` 대신 `--domain` 플래그를 씁니다: `ngrok http --domain=... 8000`

실행되면 아래처럼 뜹니다:
```
Forwarding   https://nodevelture-jyj.ngrok-free.app -> http://localhost:8000
```
이 **https 주소**가 팀 공유용 백엔드 주소입니다.

> 고정 도메인이 없으면 `ngrok http 8000`으로도 되지만, 껐다 켤 때마다 임의 주소가 새로 생겨 팀원이 매번 `.env`를 고쳐야 합니다.

### 3. 팀원(프론트) 설정
`frontend/.env` 파일에 (없으면 생성):
```env
VITE_API_BASE_URL=https://nodevelture-jyj.ngrok-free.app/
```
> ⚠️ **끝에 슬래시(`/`) 필수** — 코드가 `${VITE_API_BASE_URL}api/v1`로 이어붙이므로 슬래시가 없으면 경로가 깨집니다.

이후 vite 개발서버를 **재시작**해야 env가 반영됩니다:
```powershell
npm run dev
```

### 주의 — 채팅 스트리밍(SSE) + ngrok 경고 페이지
- 무료 ngrok은 브라우저 첫 접근 시 "방문 경고" 페이지를 띄웁니다.
- 일반 API 호출(fetch)은 요청 헤더 `ngrok-skip-browser-warning: true`로 우회 가능하지만,
- 채팅 스트림은 `EventSource`라 커스텀 헤더를 못 붙입니다. 스트리밍이 팀원 화면에서 안 뜨면 이 경고가 원인일 수 있습니다.
- 고정 도메인을 쓰면 경고 빈도가 줄고, 한 번 "Visit Site"를 누른 브라우저 세션에서는 이후 통과됩니다.

---

## 자주 겪는 문제

### `connection refused` (DB 연결 실패)
```powershell
# Docker 컨테이너가 실행 중인지 확인
docker compose ps

# 컨테이너가 없으면 시작
docker compose up -d
```

### `uvicorn`이 엉뚱한 파이썬(3.13)으로 실행됨
- `uvicorn ...` 대신 **`python -m uvicorn ...`**로 실행 (conda 환경 일치)
- `conda activate nodevelture`가 되어 있는지 확인 (프롬프트에 `(nodevelture)`)

### `ModuleNotFoundError`
```powershell
# conda 환경이 활성화되어 있는지 확인 (프롬프트에 (nodevelture) 표시)
conda activate nodevelture
pip install -r requirements.txt
```

### Alembic `Target database is not up to date`
```powershell
alembic upgrade head
```

### 포트 충돌 (`5432` 이미 사용 중)
- 로컬에 PostgreSQL이 이미 설치되어 있는 경우
- `docker-compose.yml`에서 포트를 변경하거나 로컬 PostgreSQL을 중지

### `.env`를 바꿨는데 반영이 안 됨
- `.env`는 `--reload` 감시 대상이 아닙니다. **서버를 직접 재시작**하세요.
