<!-- markdownlint-disable MD022 MD031 MD032 MD024 MD040 MD036 -->
# 서버 운영 / 트러블슈팅

서버 실행 중 발생한 에러와 해결 방법을 기록합니다.
**규칙: 새 이슈가 위로 오도록 최신순으로 쌓아 작성합니다.**
실행 방법은 [setup.md](setup.md), 전체 현황은 [../../docs/PROJECT_STATUS.md](../../docs/PROJECT_STATUS.md) 참고.

기록 형식:

```
## YYYY-MM-DD — 한 줄 증상

**증상** / **원인** / **해결** / **예방**
```

---

## 빠른 점검 체크리스트

서버가 이상하면 위에서부터 확인:

1. **DB/Redis 컨테이너 떠 있나?**
   ```powershell
   docker compose -f backend/docker-compose.yml ps
   ```
   `db`, `redis`가 `running`이 아니면 → `docker compose -f backend/docker-compose.yml up -d`
2. **conda 환경 맞나?** 프롬프트에 `(nodevelture)` 표시 / `python -m uvicorn ...`로 실행했나
3. **`.env` 바꾸고 서버 재시작했나?** (`--reload`는 `.env` 미감시)
4. **DB 테이블 있나?** `alembic upgrade head` 했는지 (빈 DB면 저장 실패)
5. **헬스체크**: `curl http://localhost:8000/health` → `{"status":"ok"}`

---

## ☁️ Cloud Run / 배포 체크리스트 (반복 함정 — 배포 전 필독)

> `.env`는 **이미지에 안 올라감**(`.dockerignore`+gitignore). Cloud Run은 **배포 시 넘긴 env/시크릿만** 봄. 로컬에서 되던 게 클라우드에서 안 되면 90%가 여기.

1. **🔑 새 외부 API 키는 Cloud Run에도 반드시 추가** — *이번 주에만 Vertex·ElevenLabs·FAL_KEY 3번 당함.* 코드에 `settings.XXX_KEY` 새로 쓰면, 로컬 `.env`뿐 아니라 **Cloud Run에도** 넣어야 함(안 넣으면 그 기능만 500/502, 키 없음 에러):
   ```bash
   # 재빌드 없이 config만 갱신(기존 env·시크릿 유지) — ~30초
   gcloud run services update nodevelture-api --region us-central1 --update-env-vars FAL_KEY=<값>
   # 민감키는 시크릿으로: --update-secrets FAL_KEY=FAL_KEY:latest (SA에 secretAccessor 부여 후)
   ```
2. **📁 배포는 `backend/`에서** — `gcloud run deploy nodevelture-api --source . --region us-central1`. 첫 줄에 **"Building using Dockerfile"** 떠야 정상. 루트에서 하면 **"Buildpacks"** 로 빌드 실패.
3. **🗄️ 모델에 컬럼 추가했으면 마이그레이션** — `alembic upgrade head`. 모델 코드만 배포하고 마이그레이션 누락하면 해당 테이블 조회가 전부 500(예: `worlds.glossary` 누락 → sessions·채팅 마비).
4. **🔁 코드 변경=재배포 / env만 변경=`services update`**(재빌드 X). env는 빌드 때 박히는 `VITE_*`(프론트)와 달리 백엔드 env는 런타임 주입.
5. **🔐 Vertex 인증** — 로컬 ADC ≠ Cloud Run. Cloud Run은 **런타임 SA**(`<프로젝트번호>-compute@developer.gserviceaccount.com`)로 호출 → `roles/aiplatform.user` 필요.
6. **▲ 프론트(Vercel)** — `VITE_API_BASE_URL`은 **Vercel 대시보드 env**에 넣고(로컬 `.env`는 gitignore라 안 읽힘) + **빌드 후 Production 승격**(새 빌드가 Preview로만 떠 있으면 메인 도메인은 옛 빌드). `VITE_*`는 빌드 때 박히므로 변경 시 **재배포 필수**.
7. **🔎 안 되면 추측 말고 로그** — `gcloud run services logs read nodevelture-api --region us-central1 --limit 50`. 실제 트레이스백이 원인을 정확히 짚어줌.

---

## 이슈 기록

## 2026-06-14 — 마이페이지('내 서재') 로딩 지연 진단 + dashboard 최적화

**증상**: 메인 → '내 서재' 진입 시 스피너가 오래(체감 7초+). 프론트는 이미 핵심만 await + 병렬 + 프로필 캐시였음.

**측정** (us-central1 라이브, 워밍 상태):

| 엔드포인트 | 지연 |
|---|---|
| `/users/{id}/...` (단순) | ~0.26s |
| `/mypage/profile` | ~2.2s |
| `/mypage/stats` | ~2.2s |
| `/users/{id}/voice-profile` (단순 PK 조회) | ~1.8s |
| **`/mypage/dashboard`** | **~6.9s** ← 주범 |

**원인 2가지**
1. **dashboard가 DB 쿼리 6~7개를 순차** 실행(세션→소설→세계관→주인공→최근대화→주간소설). LLM 없음.
2. **Neon 쿼리당 지연 floor ~2s** — 단순 PK 조회(voice-profile)도 1.8s. Cloud Run(us-central1)↔Neon **리전 거리/커넥션 establish 오버헤드**로 추정. **모든 엔드포인트에 영향**(채팅 포함).

**시도 & 결과**
- ❌ **독립 세션 5개로 병렬화**(`asyncio.gather` + 각자 `AsyncSessionLocal`): 6.9s → **8.7s로 역행**. asyncpg는 한 세션 동시 사용 불가라 새 커넥션 5개를 동시에 여는데, **Neon이 동시 커넥션 establish를 경합/직렬화**해서 오히려 느림. → 롤백.
- ✅ **단일 세션 유지 + 쿼리 병합**: Novel을 `session_id.in_(전체)` **1쿼리**로 가져와 latest/weekly 둘 다 커버(2→1). round-trip 6→5. **dashboard ~3.0s로 안정**.
- ✅ **프론트 stale-while-revalidate 캐시**: `profile`·`dashboard`·`stats`를 localStorage에 캐시 → **재방문 즉시** 표시 후 백그라운드 갱신. `voice-profile`(1.8s)은 첫 화면 불필요 → 백그라운드로 이동.

**교훈**
- **Neon에선 "쿼리 병렬화(다중 커넥션) > 순차"가 거짓.** 커넥션 establish가 비싸 동시 다중 커넥션이 더 느릴 수 있음. **라운드트립 수를 줄이는 것(쿼리 병합)** 이 안전한 최적화.
- 근본 해결(미적용, 발표 후 과제): **Neon pooled 엔드포인트(`-pooler`)** 사용 / **리전 정렬**(Cloud Run·Neon 같은 리전) / `pool_pre_ping` 재검토 / min-instances 1로 cold-start 제거. 이게 floor ~2s를 줄이는 진짜 레버.
- 데모 직전엔 **백엔드 워밍업**(아무 페이지 미리 호출)으로 cold-start 회피하면 충분.

## 2026-06-14 — 삽화 생성 502 (fal.ai 403 Forbidden)

**증상**: `POST /sessions/{id}/illustrations/generate` → 502. 로그에 `POST https://fal.run/fal-ai/flux/dev "HTTP/1.1 403 Forbidden"`.

**원인**: `FAL_KEY` 시크릿은 **정상 연결**돼 있음(리비전에 존재). fal.ai가 키를 받고도 **403** = 인증은 됐으나 권한 거부 → **크레딧 소진/결제 미설정/키 무효**(계정 측 문제). 배포·env 문제 아님.

**조치**: fal.ai 대시보드에서 크레딧·결제·키 유효성 확인(키 담당자). 코드/배포로는 못 고침.

**부수 발견(중요)**: 표준 배포 명령의 `--set-secrets`에 **`FAL_KEY`가 빠져 있었음** → `--set-secrets`는 전체 교체라 다음 배포가 FAL_KEY를 **삭제**할 뻔. 표준 명령에 `FAL_KEY=FAL_KEY:latest` 영구 추가함(위 ③ 참고).

## 2026-06-10 — 백엔드를 Cloud Run으로 배포 (ngrok 대체, 항상 켜진 HTTPS)

**배경**: 그동안 로컬 `uvicorn` + ngrok로 팀에 공유 → 내 PC 꺼지면 끊김·주소 매번 변경. DB(Neon)·Redis(Upstash)·LLM(Vertex)이 이미 클라우드라 **앱(FastAPI)만 올리면** 24시간 고정 HTTPS 주소가 생긴다.

### ⓪ 왜 Cloud Run인가 (Render·Railway 아님)
- 우리 조직 계정은 **SA 키 생성이 차단**(`iam.disableServiceAccountKeyCreation`)이라 로컬에선 ADC로 우회했음.
- **Cloud Run은 컨테이너가 attached 서비스 계정 신분으로 실행** → Vertex 인증이 **키 파일 없이 자동 ADC(메타데이터 서버)**. 로컬에서 겪은 인증 문제가 클라우드에선 사라진다.
- 같은 GCP 프로젝트라 크레딧/지연도 유리. (Render·Railway·Fly는 Vertex에 **SA 키가 필요 → 막힘**. 거기 가려면 LLM을 AI Studio 키/Groq로 바꿔야 함.)

### ① 배포 파일 (`backend/`)
- `Dockerfile`: `python:3.11-slim` + `pip install -r requirements.txt` + `uvicorn app.main:app --host 0.0.0.0 --port ${PORT}`.
  - **Cloud Run은 `$PORT`(기본 8080)를 주입** → 고정 포트로 띄우면 안 됨. 반드시 `${PORT}` 바인딩.
- `.dockerignore`: `.env`·`__pycache__`·`.venv` 등 제외 → **비밀·캐시가 이미지에 안 들어감**.

### ② 비밀값은 Secret Manager (env-var 평문 금지)
- DB/Redis URL은 콘솔(Secret Manager)에서 `DATABASE_URL`·`REDIS_URL` 시크릿으로 생성(**끝에 줄바꿈 없이** 붙여넣기).
- API 켜고 런타임 계정에 읽기 권한 부여:
  ```
  gcloud services enable secretmanager.googleapis.com run.googleapis.com cloudbuild.googleapis.com
  gcloud secrets add-iam-policy-binding DATABASE_URL --member="serviceAccount:<프로젝트번호>-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
  gcloud secrets add-iam-policy-binding REDIS_URL   --member="serviceAccount:<프로젝트번호>-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
  ```
  - `<프로젝트번호>` = `gcloud projects describe nodevelture-499003 --format="value(projectNumber)"` 로 나온 **12자리 숫자**(꺾쇠째 넣으면 `INVALID_ARGUMENT` 에러).

### ③ 배포 (backend 폴더에서, 한 줄)
```
gcloud run deploy nodevelture-api --source . --region us-central1 --allow-unauthenticated --min-instances=1 --set-env-vars "USE_VERTEX=true,GOOGLE_CLOUD_PROJECT=nodevelture-499003,GOOGLE_CLOUD_LOCATION=us-central1,LLM_PROVIDER=gemini,GEMINI_MODEL=gemini-2.5-flash-lite,GEMINI_FALLBACK_MODEL=gemini-2.5-flash" --set-secrets "DATABASE_URL=DATABASE_URL:latest,REDIS_URL=REDIS_URL:latest,FAL_KEY=FAL_KEY:latest,OPENAI_API_KEY=OPENAI_API_KEY:latest"
```
- 출력된 `https://nodevelture-api-xxxx.run.app` 가 ngrok 대체. `/health` → `{"status":"ok"}` 확인.
- **비밀 아닌 설정만 `--set-env-vars`**, DB/Redis URL·FAL_KEY·OPENAI_API_KEY는 `--set-secrets`로.
- ⚠️ **`--set-secrets`/`--set-env-vars`는 전체 교체**다. 시크릿 하나라도 빠뜨리면 그게 **삭제**된다(삽화 `FAL_KEY` 누락 → fal.ai 502가 단골 사고. 2026-06-16엔 표준 명령에 `OPENAI_API_KEY`가 빠져 있어 폴백 키가 지워질 뻔했음). **현재 서비스의 시크릿 전체**(`DATABASE_URL`·`REDIS_URL`·`FAL_KEY`·`OPENAI_API_KEY`)를 항상 같이 적을 것. 새 키 추가 시 이 줄도 갱신.
- 💡 **시크릿/ env를 건드리고 싶지 않으면**(코드만 재배포) `--set-*`를 **생략**하면 기존 설정이 전부 보존된다: `gcloud run deploy nodevelture-api --source . --region us-central1 --min-instances=1`. 시크릿 누락 사고를 원천 차단하는 가장 안전한 재배포.
- 🔥 **`--min-instances=1`** — scale-to-zero 콜드스타트(첫 요청 ~5초, 개선 전 TTFB p50 8.7s의 주범) 제거. 인스턴스 1개 상시 워밍(소량 과금). 2026-06-16부터 적용 → **개선 후 p50 5.9s**(+ 토큰 스트리밍 배포로 첫 토큰 체감 ~1-2s).

### ④ 함정
- **프로젝트 번호**: 꺾쇠 `<...>` 그대로 넣지 말고 실제 숫자로 치환.
- **Cloud SDK 창은 cmd** → 줄바꿈은 `^`(PowerShell 백틱 아님). 헷갈리면 **한 줄**로 실행.
- **`GOOGLE_APPLICATION_CREDENTIALS`·키 파일을 Cloud Run에 넣지 말 것** — 자동 ADC를 덮어써 Vertex가 깨진다.
- **콜드스타트**: scale-to-zero라 첫 요청 ~5초. 시연 직전 `--min-instances=1` 추가하면 항상 깨어 있음(소량 과금).
- **Vertex 403** 뜨면 그때만: `gcloud projects add-iam-policy-binding nodevelture-499003 --member="serviceAccount:<프로젝트번호>-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"`.

**예방/참고**
- 마이그레이션은 Neon이 이미 `upgrade head`(공용)라 배포 시 추가 작업 없음. 스키마 변경 시 로컬에서 Neon 대상으로 `alembic upgrade head` 한 번.
- 배포 후 **프론트 API base URL을 `run.app` 주소로** 교체해야 연결됨.
- 재배포는 같은 `gcloud run deploy ... --source .` 한 줄이면 새 리비전으로 무중단 교체.

---

## 2026-06-10 — LLM 엔진을 Vertex AI(GCP)로 전환 + 응답속도·언어누수 해결

**배경**: Groq Llama가 한국어에 한자·일본어를 산발적으로 섞음(언어 누수). AI Studio Gemini 키도 문제 → **GCP 크레딧으로 Vertex AI(Gemini 2.5) 전환**.

### ① Gemini API 키 형식 오류
- **증상**: 채팅 응답 없음 / `[LLM auth] gemini`. RAG 임베딩도 조용히 실패.
- **원인**: `.env`의 `GEMINI_API_KEY`가 `AQ.Ab8...`(OAuth 토큰 형식). 표준 AI Studio 키는 **`AIzaSy...`**.
- **해결**: AI Studio(`aistudio.google.com/app/apikey`)에서 `AIzaSy...` 재발급, **또는 Vertex 전환(아래)**.

### ② Vertex 우회 — 조직 정책(SA 키 차단) → ADC 인증
- **증상**: 서비스 계정 JSON 키 생성이 `iam.disableServiceAccountKeyCreation` 정책으로 차단(조직 계정) + "여러 프로젝트 ToS 위반 가능성" 경고.
- **해결**: SA 키 없이 **ADC(사용자 인증)** 로 우회 —
  ```powershell
  gcloud auth login
  gcloud config set project <PROJECT_ID>
  gcloud auth application-default login
  gcloud auth application-default set-quota-project <PROJECT_ID>
  ```
  - `.env`: `USE_VERTEX=true` / `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION=us-central1` (키 불필요)
  - `pip install google-cloud-aiplatform`
  - **billing(결제 계정) 연결 필수** — 무료크레딧을 써도 결제 활성화 안 하면 `requires billing to be enabled` 404.
- **예방**: 조직 계정은 정책·ToS 플래그가 많아 정지 위험 → 여의치 않으면 **개인 Gmail** 또는 **AI Studio 무료 키**.

### ③ Vertex 모델 가용성 — 신규 프로젝트는 2.5만
- **증상**: `gemini-2.0-flash`·`1.5`·`3.x` 전부 `404 Publisher Model not found`.
- **원인**: 신규 프로젝트엔 최신 세대만 열림. **Gemini 3.x는 아직 없음(2.5가 최신)**.
- **해결**: us-central1에서 **`gemini-2.5-flash-lite`(최速) / `gemini-2.5-flash` / `gemini-2.5-pro`** 만 동작. 모델명을 `.env`에 명시.

### ④ 응답 속도 — thinking + flash가 느림(~8s) → ~2s
- **증상**: 응답 8~11초.
- **원인**: Gemini 2.5는 기본으로 **'사고(thinking)'** 를 함 + flash는 lite보다 느림.
- **해결**: `generation_config`에 **`thinking_config.thinking_budget=0`**(창작엔 불필요) + 모델 **`gemini-2.5-flash-lite`** → **~2초**(4~5배↑). 코드: `llm._gemini_gen_config`.
- **참고**: 리전 `asia-northeast3`(서울)는 오히려 더 느렸음 + flash-lite 미제공 → **us-central1 유지**. 서버 첫 호출은 콜드스타트로 ~5초.

### ⑤ Redis 도커 안 켜질 때
- **해결**: `.env`의 `REDIS_URL`을 **Upstash 줄로 토글**(주석 교체) → Docker 없이 동작. **서버 재시작 필수**.

---

## 2026-06-08 — DB 커넥션이 작업 도중 끊김 (ConnectionResetError / ConnectionDoesNotExistError)

**증상**
- `sessions.py`의 `complete_session`에서 `db.execute(...)` 호출 시 ASGI 예외 발생
- 핵심 메시지:
  ```
  ConnectionResetError: [WinError 10054] 현재 연결은 원격 호스트에 의해 강제로 끊겼습니다
  asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation
  ```

**원인**
- PostgreSQL이 커넥션을 도중에 리셋함. 두 요인이 겹침:
  1. 도커 postgres 컨테이너가 (재)시작 중이거나 WSL 엔진이 흔들려 연결이 끊김
  2. SQLAlchemy 엔진에 `pool_pre_ping`이 없어, 죽은 커넥션을 풀에서 그대로 꺼내 재사용

**해결**
- `app/database.py` 엔진에 복원력 옵션 추가:
  ```python
  engine = create_async_engine(
      settings.DATABASE_URL,
      echo=settings.DEBUG,
      pool_pre_ping=True,    # 사용 전 커넥션 생존 확인 → 죽은 커넥션 자동 교체
      pool_recycle=1800,     # 30분 지난 커넥션 재생성
  )
  ```
- 컨테이너가 내려가 있으면 함께 재기동: `docker compose -f backend/docker-compose.yml up -d`

**예방**
- 도커가 불안정하면 Redis처럼 `.env`의 `DATABASE_URL`을 클라우드 PG(Neon/Supabase)로 토글하는 것도 대안
- DB 예외가 ASGI 레벨로 그대로 노출되는 문제는 **전역 에러 핸들링 미들웨어**(2주차 예정)로 일관 응답화 필요

**⚠️ 추가 확인 (재발) — 실제 주원인은 "컨테이너 종료"**
- 같은 에러가 `pool_pre_ping` 적용 후에도 재발. 트레이스백이 `_create_connection`(새 커넥션 생성) 단계에서 터지면 풀 문제가 아니라 **postgres 컨테이너 자체가 꺼진 것**.
- 진단: `docker compose ps`가 비어 있음 + 로그 마지막에 `received fast shutdown request`.
- 해결: `docker compose up -d` 로 재기동 → `docker compose ps`에서 `db`가 `(healthy)` 확인.
- **구분법**: `_create_connection`에서 실패 → 컨테이너 죽음(`up -d`). / 재사용 커넥션 끊김 → `pool_pre_ping`이 처리.
- 컨테이너가 자꾸 꺼지면(WSL/Docker Desktop 불안정) → 클라우드 PG 토글이 근본 대안.

---

## 자주 겪는 에러 모음 (setup.md에서 발췌)

### `connection refused` — DB 연결 실패
도커 컨테이너 미기동. `docker compose ... ps` 확인 후 `up -d`.

### `uvicorn`이 엉뚱한 파이썬(3.13)으로 실행됨
`python -m uvicorn ...`로 실행 (conda 환경 일치). `(nodevelture)` 활성화 확인.

### `ModuleNotFoundError`
conda 환경 비활성 또는 패키지 미설치. `conda activate nodevelture` → `pip install -r requirements.txt`.

### Alembic `Target database is not up to date`
`alembic upgrade head`.

### 포트 충돌 (`5432`/`8000` 사용 중)
다른 포트로 실행(`--port 8001`)하거나 점유 프로세스 정리. ngrok 공유 시 포트는 jyj 서버 기준만 맞으면 됨.

### `.env` 변경이 반영 안 됨
`.env`는 `--reload` 감시 대상 아님 → 서버 직접 재시작.

### 채팅 응답 없음 (Gemini)
- `GEMINI_API_KEY` 형식 확인 (`AIzaSy...` 형태)
- Redis 미실행 시 컨텍스트 조립 실패 → 도커 redis 또는 Upstash 확인

---

## CI/CD — 백엔드 자동 배포 (GitHub Actions)

> 수동 `gcloud run deploy`를 자동화. **`dev`에 `backend/**` 변경이 머지되면** `.github/workflows/deploy-backend.yml`이 Cloud Run에 배포한다. 배포는 `--set-*` 없이 돌려 **기존 시크릿·env를 보존**(누락 사고 차단) + 배포 후 `/health` 확인.

### 동작
- 트리거: `push → dev` 중 `backend/**` 변경(문서만 바뀌면 배포 안 함) · 수동(`workflow_dispatch`)도 가능.
- 명령: `gcloud run deploy nodevelture-api --source . --region us-central1 --min-instances=1 --quiet` (워크플로 내부).
- 직렬화(`concurrency`)로 배포 겹침 방지.

### 1회 셋업 — GCP 인증 (둘 중 하나)
GitHub Actions가 GCP에 배포하려면 **배포용 서비스계정(SA) + 권한**이 필요. 아래는 `gcloud`로 1회만(레포 관리자 + GCP 권한 보유자가 실행).

**공통: 배포 SA 생성 + 권한 부여**
```bash
PROJECT=nodevelture-499003
PROJNUM=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
SA=gh-deployer@$PROJECT.iam.gserviceaccount.com

gcloud iam service-accounts create gh-deployer --project $PROJECT --display-name "GitHub Actions deployer"
# Cloud Run 배포 + 소스 빌드(Cloud Build) + 런타임 SA 위임 + 이미지/스테이징
for R in roles/run.admin roles/cloudbuild.builds.editor roles/iam.serviceAccountUser \
         roles/artifactregistry.writer roles/storage.admin roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="$R"
done
# 런타임 SA(컴퓨트 기본)에 대해 'act as' 권한
gcloud iam service-accounts add-iam-policy-binding ${PROJNUM}-compute@developer.gserviceaccount.com \
  --member="serviceAccount:$SA" --role="roles/iam.serviceAccountUser" --project $PROJECT
```

**옵션 A — Workload Identity Federation (키리스, 권장)**
```bash
gcloud iam workload-identity-pools create gh-pool --project $PROJECT --location global --display-name "GitHub"
gcloud iam workload-identity-pools providers create-oidc gh-provider \
  --project $PROJECT --location global --workload-identity-pool gh-pool \
  --display-name "GitHub OIDC" --issuer-uri "https://token.actions.githubusercontent.com" \
  --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition "assertion.repository=='woawoal/NodeVelture'"
# SA에 이 레포가 가장(impersonate) 가능하도록 바인딩
gcloud iam service-accounts add-iam-policy-binding $SA --project $PROJECT \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/projects/${PROJNUM}/locations/global/workloadIdentityPools/gh-pool/attribute.repository/woawoal/NodeVelture"
```
→ GitHub 레포 **Settings▸Secrets and variables▸Actions** 에 두 개 등록:
- `GCP_WIF_PROVIDER` = `projects/<PROJNUM>/locations/global/workloadIdentityPools/gh-pool/providers/gh-provider`
- `GCP_DEPLOY_SA` = `gh-deployer@nodevelture-499003.iam.gserviceaccount.com`

**옵션 B — SA 키 (간편, 장기키)**
```bash
gcloud iam service-accounts keys create key.json --iam-account $SA --project $PROJECT
```
→ GitHub Secret `GCP_SA_KEY` 에 `key.json` 전체 내용 붙여넣기. 그리고 워크플로의 인증 스텝을 주석대로 `credentials_json: ${{ secrets.GCP_SA_KEY }}` 로 교체. (보안상 옵션 A 권장 — 키 유출/로테이션 부담 없음.)

### 주의
- 워크플로는 `--set-*`를 **일부러 안 씀** → 시크릿/env 보존. 새 시크릿을 추가했다면 **그 1회만** 수동 배포(③의 풀 명령)로 등록하고, 이후는 자동 배포가 보존.
- DB 마이그레이션은 자동 적용 안 함(설계) → 스키마 변경 시 `alembic upgrade head` 별도(자동화하려면 워크플로에 단계 추가 가능하나, 프로덕션 DB 변경이라 신중히).
