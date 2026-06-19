<!-- markdownlint-disable MD060 -->
# DB 모델 명세

> SQLAlchemy 2.0 (`Mapped[]` + `mapped_column`). 마이그레이션 head: **`l2m3n4o5p6q7_add_speaker_to_dialogues`**.
> 핵심 11테이블 — 창작(world·character·session·dialogue·novel) · 사용자(user) · 개인화(saved_sentence·user_chat_taste·user_taste_profile) · 멀티모달(illustration) · 운영(api_log).

## ERD (텍스트)

```
User ─┬─ World ──── Character
      │     │            │
      │     └── Session ─┤
      │           │      │
      ├───────────┤      │
      │        Dialogue ─┘   (speaker_type=character → character_id)
      │           │
      │        (완료 후) Novel(1:1) · Illustration(1:N)
      │
      ├─ SavedSentence       (개인화 RAG 근거 문장)
      ├─ UserChatTaste       (세션별 취향)
      └─ UserTasteProfile    (전역 취향 — 마이페이지)

ApiLog ─ User · Session       (호출·토큰·비용 로그)
```

---

## 창작 코어

### `users`

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| username | VARCHAR(50) UNIQUE | 사용자명 |
| email | VARCHAR(255) UNIQUE, null | 이메일 |
| hashed_password | VARCHAR(255), null | bcrypt 해시 |
| is_active | BOOLEAN | 활성 여부 |
| **voice_profile** | JSON, null | 말투 프로파일(F-VM, 💡 말투 추천 근거) |
| **error_profile** | JSON, null | 맞춤법 오답노트(자주 틀리는 항목 → 능동 경고) |
| **is_admin** | BOOLEAN | 관리자 여부(토큰 대시보드 등) |
| created_at | TIMESTAMP | 가입일 |

### `worlds` (세계관)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| user_id | UUID (FK→users, CASCADE) | 소유자 |
| title | VARCHAR(200) | 제목 |
| description | TEXT | 요약·줄거리 |
| genre | VARCHAR(50) | 장르 |
| setting | TEXT | 시대/공간 배경 |
| rules | TEXT, null | 세계관 규칙 |
| **tags** | JSON, null | 자동 분류 태그(F-WD-06) |
| **glossary** | JSON, null | 맞춤법 보호 용어집(LLM 추출 + '넘기기' 누적). null=미추출 |
| **hidden_facts** | JSON, null | 숨겨진 설정·복선(차로운 추리 모드에서 주입) |
| **relations** | JSON, null | 인물 관계도(설정집 등장인물 탭) — 사용자 직접 입력 `[{from, to, label, dx?, dy?}]` |
| created_at / updated_at | TIMESTAMP | 생성·수정일 |

### `characters` (등장인물)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| world_id | UUID (FK→worlds, CASCADE) | 소속 세계관 |
| **user_id** | VARCHAR(100) | 기기별 식별자(FK 아님) |
| name | VARCHAR(100) | 이름 |
| role | ENUM | protagonist / supporting / villain / narrator |
| personality | TEXT | 성격·말투·특징 |
| **prompt** | TEXT | 행동지시문(AI가 이 인물 연기 시 반드시 따름) |
| is_ai_controlled | BOOLEAN | AI 제어(조연=true) |
| created_at | TIMESTAMP | 생성일 |

> 주인공은 `session.protagonist_id`로 지정. 세계관 수정 시 기존 인물은 이름·역할 잠금, 성격·prompt만 보강.

### `sessions` (창작 세션)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| world_id | UUID (FK→worlds, CASCADE) | 세계관 |
| user_id | UUID (FK→users, CASCADE) | 유저 |
| protagonist_id | UUID (FK→characters) | 사용자가 맡을 주인공 |
| **author_id** | INTEGER, null | 작가 페르소나(1 백야·2 차로운·3 한여름·4 김도현) |
| status | ENUM | active / paused / completed |
| started_at / updated_at / ended_at | TIMESTAMP | 시각 |
| **context_summary** | TEXT, null | 내부 서사 상태 |
| **current_state** | TEXT, null | 현재 상태 |
| **story_summary** | TEXT, null | 누적 줄거리 요약(긴 대화 일관성) |

### `dialogues` (대화 로그)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| session_id | UUID (FK→sessions, CASCADE) | 소속 세션 |
| character_id | UUID (FK→characters, SET NULL), null | AI 캐릭터(user 발화 시 null) |
| speaker_type | ENUM | user / character |
| **speaker** | TEXT, null | 화자 이름(@등장인물 분리 표시용) |
| content | TEXT | 발화 내용(AI는 `나레이션\n\n"대사"` 형태) |
| turn_order | INTEGER | 대화 순서(0부터) |
| created_at | TIMESTAMP | 저장 시각 |

### `novels` (소설 초안)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| session_id | UUID (FK→sessions, UNIQUE) | 원본 세션(1:1) |
| title | VARCHAR(200) | 제목(기본 "제목 없음") |
| content | TEXT | 본문 |
| status | ENUM | draft / generating / final |
| created_at / updated_at | TIMESTAMP | 생성·수정일 |

> 변환은 「채팅 종료」 시 `POST /sessions/{id}/novel/convert` — 대화 로그를 결정적으로 이어붙여 upsert.

---

## 개인화 (취향·저장)

### `saved_sentences` (개인화 RAG 근거)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| user_id | UUID (FK→users, CASCADE) | 소유자 |
| session_id | UUID (FK→sessions, SET NULL), null | 출처 세션 |
| content | TEXT | 저장한 문장 |
| label | VARCHAR(50), null | 분류 라벨 |
| created_at | TIMESTAMP | 저장 시각 |

> 저장 문장을 의미검색해 **취향저격 추천**의 톤 근거로 주입(저장 톤 → 추천 톤 인과 측정됨).

### `user_chat_taste` (세션별 취향)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| user_id / chat_id | UUID | UNIQUE(user_id, chat_id) |
| works | JSONB | 입력한 취향 작품 목록 |
| taste_profile | JSONB, null | LLM 추출 선호 장르·키워드 |
| updated_at | TIMESTAMP | 갱신 시각 |

### `user_taste_profile` (전역 취향 — 마이페이지)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| user_id | UUID (PK) | 유저당 1행 |
| selected_works | JSONB | 선택 작품 |
| taste_profile | JSONB, null | 선호 장르·키워드 |
| updated_at | TIMESTAMP | 갱신 시각 |

---

## 멀티모달 · 운영

### `illustrations` (삽화)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| session_id | UUID (FK→sessions) | 소속 세션 |
| image_url | TEXT | base64 data URL |
| caption | TEXT | 장면 설명 |
| created_at | TIMESTAMP | 생성 시각 |

### `api_logs` (AI 호출 로그 — 비용 추적)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID (PK) | 기본키 |
| user_id / session_id | UUID, null | 요청 유저·세션 |
| endpoint | VARCHAR(255) | 호출 경로 |
| model_used | VARCHAR(100) | 사용 모델 |
| prompt_tokens / completion_tokens | INTEGER | 입출력 토큰 |
| total_cost | FLOAT | 추정 비용(USD) |
| created_at | TIMESTAMP | 호출 시각 |

---

## 관계 정리

| 관계 | 종류 | 비고 |
|------|------|------|
| User → World / Session / SavedSentence | 1:N | User 삭제 시 CASCADE |
| World → Character / Session | 1:N | World 삭제 시 Character CASCADE |
| Session → Dialogue | 1:N | Session 삭제 시 CASCADE |
| Session → Novel | 1:1 | UNIQUE |
| Session → Illustration | 1:N | 장면별 삽화 |
| Character → Dialogue | 1:N | character_id SET NULL(인물 삭제 시 기록 보존) |
| User → UserTasteProfile | 1:1 | 전역 취향 |
| User → UserChatTaste | 1:N | 세션별 취향(UNIQUE user+chat) |
