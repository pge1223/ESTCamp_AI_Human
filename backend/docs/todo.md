# 백엔드 TODO (본인 담당 — 서버 파트)

> 가연님: DB 모델 / Alembic / LLM 연동 / 소설 변환
> 본인: API 서버 / 인증 / 스트리밍 / 인프라 / 배포

---

## 1주차 후반 — 기본 API 완성

- [ ] **JWT 인증** — 로그인 API, 토큰 발급/검증, 의존성 주입
- [ ] **에러 핸들링 미들웨어** — 전역 예외 처리, 일관된 에러 응답 형식
- [ ] **Chat API 확정** — 프론트엔드와 요청/응답 구조 합의 후 구현
  - 작가모드: 이벤트 입력 → AI 문단 생성
  - 등장인물모드: 사용자(주인공) ↔ 캐릭터(AI) 대화

---

## 2주차 — 채팅 핵심 구현

- [ ] **SSE 스트리밍 실제 구현** — 현재 틀만 존재, PERSO API 연결 후 완성
- [ ] **API Log 미들웨어** — 모든 요청 자동 기록 (토큰 수, 비용, 엔드포인트)
- [ ] **환경변수 스위칭 구조** — PERSO API ↔ Ollama 폴백 전환
- [ ] **Redis CacheService 연결 확인** — Docker 실행 후 실제 동작 테스트
- [ ] **프론트엔드 통합 테스트** — CORS, 실제 API 호출, 스트리밍 확인

---

## 2주차 후반 — 품질 / 운영

- [ ] **비용 모니터링** — ApiLog 기반 토큰·비용 집계 엔드포인트
- [ ] **로그 시각화 (간단히)** — 요청 로그 조회 API

---

## 3주차 — 배포

- [ ] **Dockerfile 작성** — FastAPI 앱 컨테이너화
- [ ] **docker-compose 앱 추가** — db + redis + app 통합 실행
- [ ] **Render / Railway 배포** — 실제 서버 배포
- [ ] **환경변수 프로덕션 설정** — SECRET_KEY, DB URL 등
- [ ] **README 실행 방법 업데이트**
- [ ] **발표 자료 백엔드 파트 정리**

---

## 완료

- [x] FastAPI 프로젝트 구조 (`api/v1/`)
- [x] PostgreSQL + Redis Docker 설정
- [x] DB 모델 7개 (User, World, Character, Session, Dialogue, Novel, ApiLog)
- [x] Pydantic 스키마 6종
- [x] CRUD API 엔드포인트 (세계관, 캐릭터, 세션, 대화, 소설)
- [x] Alembic 마이그레이션 설정
- [x] 페르소나 프롬프트 템플릿 (`personas.py`)
- [x] ngrok으로 로컬 서버 팀원 공유
- [x] 백엔드 문서 작성 (architecture, api, models, setup, coding-rules)
