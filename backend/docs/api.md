<!-- markdownlint-disable MD060 MD022 MD032 MD031 -->
# API 명세

> 최종 갱신: 2026-06-14. 이 문서는 **엔드포인트 인덱스 + 핵심 흐름**입니다. 전체 요청/응답 스키마는 **Swagger UI**(`/docs`)를 기준으로 보세요.

- Base URL (로컬): `http://localhost:8000/api/v1`
- Base URL (배포): `https://nodevelture-api-958641405309.us-central1.run.app/api/v1`
- Swagger UI: `/docs` · 헬스체크: `GET /health` (prefix 없음, 루트)

> 라우터 등록: `app/api/v1/router.py`. 도메인별 파일: `app/api/v1/endpoints/`.

---

## 작가 / 페르소나 — `/authors`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /authors` | 작가 4인(백야·차로운·한여름·김도현) 목록 |
| `GET /authors/{author_id}` | 작가 상세 |
| `GET /authors/{author_id}/questions` | 세계관 설정용 질문지 |

## 세계관 — `/worlds`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /worlds?user_id={uuid}` | 목록 |
| `POST /worlds?user_id={uuid}` | 생성 (`{title, description, genre, setting, rules}`) |
| `GET·PUT·DELETE /worlds/{world_id}` | 조회 / 수정 / 삭제(연관 캐릭터·세션 cascade) |
| `POST /worlds/{world_id}/tags/classify` | **세계관 태그 자동분류**(F-WD-06, LLM 멀티라벨) |
| `PATCH /worlds/{world_id}/tags` | 태그 수정 |

> `worlds.glossary`(JSON) — 맞춤법 보호 용어집(LLM 자동추출 + '넘기기' 누적). proofread가 사용.

## 등장인물 — `/worlds/{world_id}/characters`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET·POST /` | 목록 / 생성 (`{name, role, personality, prompt, is_ai_controlled}`) |
| `GET·PUT·DELETE /{character_id}` | 조회 / 수정 / 삭제 |

`role`: `protagonist`(주인공·사용자) / `supporting`(조연) / `villain`(빌런) / `narrator`(화자)

## 세션 — `/sessions`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /sessions?user_id={uuid}` | 내 세션 목록 |
| `POST /sessions` | 시작 (`{world_id, user_id, protagonist_id, author_id}`) |
| `GET·DELETE /sessions/{session_id}` | 조회 / 삭제 |
| `PATCH /sessions/{session_id}/complete` | 완료(active→completed) → 소설 변환 가능 |

> `session.author_id`(1~4) = 선택 작가 persona. 소설 문체·표시에 사용.

## 대화 — `/sessions/{session_id}/dialogues`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /` | 대화 목록(`turn_order` 순) — 채팅 이어쓰기 복원에 사용 |

---

## 채팅 (코어) — `/chats` ★

| 메서드 · 경로 | 설명 |
|---|---|
| `POST /chats/{chat_id}/messages` | 사용자 메시지 수신 + Redis/DB 저장 → `{messageId}` 반환 |
| `GET /chats/{chat_id}/stream` | **★ SSE 스트리밍**(아래 구조) |
| `POST /chats/{chat_id}/reaction` | 작가 리액션(F-AS-05) — 감정분류 → 작가 톤 한 줄 |
| `GET /chats/{chat_id}/suggest` | 다음 전개 제안 / 입력 없으면 막힘 도움(F-AS-01/03) |
| `POST /chats/{chat_id}/stuck` | 막힘 도움(라이터스 블록) |
| `POST /chats/{chat_id}/npc-react` | 조연 다중 동시 반응(F-CH-09) |
| `POST /chats/{chat_id}/memo` · `GET /memos` · `PUT /memos` · `DELETE /memo/{index}` | 작가 메모(F-CH-11) — 프롬프트 `[작가 메모]` 주입 |
| `PATCH /chats/{chat_id}/state` | 세션 상태 갱신 |
| `POST /chats/{chat_id}/suggestions` | (입력 추천 보조) |

### 채팅 스트림 SSE 구조 ★

```
GET /chats/{chat_id}/stream
    ?content=<사용자 입력>
    &character_id=<baekya|charoun|hanyeoreum|kimdohyeon>
    &mode=author
    &speaker=<등장인물 이름>    ← @등장인물 멘션(F-CH-18). 있으면 그 인물 시점·서사로 전개
    &world_context=<무시됨>     ← 서버가 항상 DB에서 재구성(세계관 수정 즉시 반영). 전송해도 무시
    &check_consistency=<true|false>
```

응답 `text/event-stream` — 4종 이벤트:
```
event: delta                      ← ★ narration 토큰 즉시 흘림(체감 TTFB↓)
data: {"narration":"<부분 텍스트>"}

event: reply
data: {"messageId","narration","dialogue","memories":[…RAG],"consistency":{consistent,violations:[{established,conflict,severity}]}}

event: audio                      ← TTS 첫 문장(ElevenLabs). 키/IP 차단 시 미전송
data: {"messageId","audio":"<base64 mp3>"}

event: done
```
> 프론트는 `delta`로 점진 표시, `reply`로 나레이션/대사 분리·타자기 렌더, `audio` 자동 재생.
> `consistency`(check_consistency=true 시) → 모순이면 화면 **🔍 '설정↔충돌' alert**(라이브 토글). 비차단.

## 작가 AI 패널 — `/chats/{chat_id}/author`

| 메서드 · 경로 | 설명 |
|---|---|
| `POST /message` | 작가에게 질문(원고 피드백 등) |
| `POST /rewrite` | 문장 리라이트 |
| `POST /taste-recommend` | 취향 기반 대사 추천 |
| `GET /history` | 작가 대화 기록(작가별 분리) |

---

## 소설 변환 — `/sessions/{session_id}`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /novel` | 소설 초안 조회 |
| `POST /novel/generate` | 대화 로그 → **작가 문체 소설** 변환(F-NV-02, 문체 RAG) |
| `POST /novel/convert` | 대화 로그 → 소설(LLM 없이 **결정적 이어붙이기**, 빠름·무비용) |
| `PUT /novel/draft` | 초안 저장 |
| `PATCH /novel` | 제목/본문 수정 |

## 삽화 — `/sessions/{session_id}/illustrations`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /illustrations/recommend` | 장면 추천 |
| `POST /illustrations/generate` | 삽화 생성(Vertex Gemini Flash Image) |
| `POST /illustrations/generate-openai` | 삽화 생성(OpenAI gpt-image-1, 키 없으면 502 graceful) |
| `GET·POST /illustrations` | 저장 목록 / 저장 |
| `DELETE /illustrations/{illus_id}` | 삭제 |

## 오탈자 교정 — (풀경로, `proofread.py`)

| 메서드 · 경로 | 설명 |
|---|---|
| `POST /chats/{chat_id}/proofread` | 맞춤법 검사(F-QC-02) → 오류쌍 + 작가 톤 메모 + 자주틀림. 등장인물·세계관 **고유명사 보호**, 자모·늘임 무시 |
| `GET /users/{user_id}/error-notebook` | 개인 오답노트(자주 틀린 순) |
| `GET·POST·DELETE /chats/{chat_id}/glossary` | 세계관 보호 용어집 조회 / '넘기기' 추가 / 삭제 |

요청: `{text, character_id, persona_memo}` · 응답: `{errors:[{original,corrected,type,frequent,count}], memo, count, checker_ok}`
> `checker_ok=false` = 네이버 검사기 동작 실패(조용한 미검사) — 프론트가 '깨끗함'으로 오인 금지.

## 마이페이지 — `/mypage`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /profile` · `/stats` · `/dashboard` | 프로필·창작 통계·대시보드 |
| `GET /works` · `/works/{session_id}` · `/works/{session_id}/wiki` | 작품 목록·상세·설정집(세계관/인물/관계도/타임라인) |
| `GET /recent` · `/author-records` · `/achievements` | 최근 작업·AI 작가 기록·업적 |
| `GET·POST·DELETE /sentences[/{id}]` | 문장 보관함 |
| `GET /taste` · `POST /taste/setup` | 취향 프로필 |

> 오답노트는 `/users/{id}/error-notebook`(proofread) 사용.

## 취향 — `/chats/{chat_id}`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /taste` | 저장된 취향 |
| `POST /taste/analyze` | 취향 분석(취향저격 추천) |

## 사용자 — `/users`

| 메서드 · 경로 | 설명 |
|---|---|
| `POST /register` | 회원가입(레거시) |
| `POST /me` | **Neon Auth 동기화**(로그인 유저 행 생성/갱신) |
| `GET /users/{user_id}` | 조회 |
| `GET·POST /users/{user_id}/voice-profile` | 말투 프로필(F-PR-01) 조회/저장 |

## 세계관 프리셋 — `/world-examples`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /world-examples/random/{author_id}` | 랜덤 세계관 프리셋(F-WD-07/08) |

## 토큰 분석 — `/api-logs`

| 메서드 · 경로 | 설명 |
|---|---|
| `GET /` · `/summary` · `/total` · `/by-model` · `/session/{id}` · `/dashboard` | 토큰/비용 집계(F-SY-09) |

---

## 공통 에러 코드

| 코드 | 의미 |
|------|------|
| 400 | 잘못된 요청(상태/식별자 불일치 등) |
| 403 | 권한 없음(예: 남의 메시지 수정) |
| 404 | 리소스 없음 |
| 409 | 중복(이미 존재) |
| 422 | 입력값 유효성 실패 |
| 500 | 서버 내부 오류 |

**에러 응답 형식**
```json
{ "detail": "에러 메시지" }
```
