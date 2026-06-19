# Chat 페이지 데이터 흐름 정리

---

## 1. Chat 왼쪽 패널 (스토리 채팅)

### 페이지 진입 시 초기 로드

```
스토리리스트 → /chat 이동
  └─ getSession(chatId)                 DB: sessions 테이블
       ├─ getWorld(session.world_id)    DB: worlds 테이블
       ├─ getCharacters(world_id)       DB: characters 테이블
       └─ getDialogues(chatId)          DB: dialogues 테이블 (이전 대화 전체 복원)
```

복원된 dialogues는 `narration + "대사"` 포맷을 파싱해 `narration` / `dialogue` 필드로 분리해 화면에 표시.

---

### 사용자가 대사를 전송할 때

```
사용자 입력 → handleSend()
  │
  ├─ [1] POST /chats/{chatId}/messages         (사용자 메시지 먼저 저장)
  │         payload: { content, character_id, world_context, speaker }
  │         → Redis: history에 lpush (최대 20턴 유지)
  │         → DB: Dialogue 행 insert (speaker_type=user)
  │
  └─ [2] GET /chats/{chatId}/stream (SSE)      (AI 응답 스트리밍)
            params: content, character_id, world_context, speaker, check_consistency
```

#### 백엔드 `/stream` 내부 처리

```
get_context(chatId)
  ├─ Redis: history        (최근 20턴, 없으면 DB fallback)
  ├─ Redis: state          (internal_note 기반 현재 서사 상태)
  ├─ Redis: summary        (누적 줄거리 요약, 없으면 DB session.story_summary)
  ├─ Redis: characters     (등장인물 텍스트 캐시)
  ├─ Redis: memos          (작가 메모 목록)
  └─ Redis: phase          (도입부/전개/절정/결말)

world_context가 없으면 → DB에서 직접 빌드
  ├─ Session → World (제목/장르/배경/요약/규칙)
  ├─ Characters (사용자 조종 인물 / AI 서술 인물 / 캐릭터 지시문)
  └─ Session.story_summary

RAG: memory.retrieve_relevant(chatId, db, content)
  └─ 현재 입력과 관련된 과거 대화 기억 검색 → 일관성 보강용

build_messages() → LLM 호출
  ├─ system: CRITICAL_OUTPUT_RULE + protagonist_rule + speaker_rule
  │           + OUTPUT_RULES + INPUT_RULES + WRITER_STYLE_RULE + 작가 페르소나
  └─ context 주입 (user 역할 메시지):
       ├─ [주요 등장인물] (Redis characters)
       ├─ [사건 요약] (Redis summary)
       ├─ [작가 메모] (Redis memos)
       ├─ [관련 기억] (RAG 결과)
       ├─ [현재 상태] (Redis state)
       ├─ [현재 스토리 단계] (Redis phase)
       └─ 최근 대화 10턴 verbatim (history[:10])
```

#### AI 응답 수신 후 처리

```
SSE "delta" 이벤트 (토큰 스트리밍, 배포 완료)
  └─ narration 토큰을 생성 즉시 흘림(_partial_narration) → 첫 토큰 체감 ↓ (프론트는 타자기로 렌더)

SSE "reply" 이벤트 (최종 구조화)
  ├─ narration, speaker, dialogue, protagonist_dialogue, memories, consistency, out_of_genre/genre_note
  ※ 검수 facts에서 인물 관계도(참고용)는 제외 → 관계 변화는 모순으로 안 잡음

SSE "audio"(나레이션 첫 문장 TTS, 선택) · "done"

후처리:
  ├─ _resolve_speaker(): speaker를 등록된 AI 인물로 강제 보정
  ├─ 나레이션 솔로 신호 감지 ("혼자/아무도 없" 등) → speaker/dialogue 강제 비움
  ├─ story_phase 역행 방지 로직 적용
  ├─ Redis: history에 AI 응답 append
  ├─ Redis: state = internal_note 갱신
  ├─ DB: Dialogue insert (speaker_type=character)
  ├─ DB: ApiLog insert (토큰 사용량/비용)
  └─ 5턴마다: memory.refresh_session_summary() → Redis summary 갱신 → DB 동기화
```

#### 입력 추천 (`💡` 버튼)

```
fetchSuggestions()
  ├─ 음성 프로파일 있으면: POST /chats/{chatId}/voice-suggest
  │     payload: { npc_dialogue(마지막 AI 대사), genre }
  └─ 없으면: POST /chats/{chatId}/suggestions
        payload: { character_id, world_context }
```

#### 작가 리액션 (아바타 자막, F-AS-05)

```
사용자 전송 후 → POST /chats/{chatId}/reaction
  payload: { content(사용자 대사), character_id, world_context }
  → 작가 페르소나 톤으로 짧은 한 줄 리액션 반환
  → 아바타 위에 15초간 표시
```

---

### 참고 데이터 요약

| 레이어 | 데이터 |
|--------|--------|
| DB | Session, World, Character (세계관/인물 설정), Dialogue (이전 대화) |
| Redis | history (최근 20턴), state (현재 서사 상태), summary (줄거리 요약), characters, memos, phase, turn 카운터 |
| LLM context | 세계관 · 인물 지시문 · 줄거리 요약 · 작가 메모 · RAG 기억 · 현재 상태 · 스토리 단계 · 최근 10턴 대화 |
| localStorage | 원고 내용, 음성 반응 ON/OFF, 능동 경고 날짜 |

---

## 2. Chat 오른쪽 패널 (작가 AI)

### 패널 초기화

```
페이지 진입 시:
  ├─ GET /chats/{chatId}/memos          Redis: memos 목록 로드
  └─ getTaste(chatId, userId)           DB: UserTasteProfile (취향 프로파일 복원)
                                        → tasteWorks, tasteProfile 상태 복원
```

### 사용자가 패널에 텍스트를 입력하고 전송할 때

```
authorInput → handleSendAuthorMessage()
  │
  └─ POST /chats/{chatId}/author/message
       payload: { content, author_id, mode }

       백엔드 참고 데이터:
         ├─ DB: Session → World (세계관 문자열)
         ├─ DB: Characters (등장인물)
         ├─ DB: Dialogue 최근 5턴 (스토리 흐름 파악)
         ├─ Redis: memos (작가 메모)
         ├─ Redis: summary (줄거리 요약)
         ├─ Redis: author_history (패널 내 대화 기록)
         ├─ Redis: prev_user_questions (중복 질문 방지)
         └─ 작가 페르소나 시스템 프롬프트 (백야/차로운/한여름/김도현)

       응답 수신 후:
         ├─ parseNumberedChoices() → 번호 항목 있으면 선택지 카드로 표시
         └─ shouldRecommend !== false → 자동으로 추천 문장 생성 요청
              POST /chats/{chatId}/author/rewrite
                payload: { original(사용자 입력), feedback(AI 피드백), author_id }
```

### 태그 버튼별 동작

| 태그 | 동작 | API / 데이터 |
|------|------|-------------|
| `#세계관` | 세계관 정보 토글 표시 | 이미 로드된 `world` 상태 (추가 API 없음) |
| `#등장인물` | 등장인물 목록 토글 표시 | 이미 로드된 `dbCharacters` 상태 (추가 API 없음) |
| `#에피소드` | "지금까지 주요 에피소드 정리해줘" 자동 전송 | `POST /author/message` |
| `#추천` | 대사 제안 3개 요청 | `POST /chats/{chatId}/suggestions` |
| `#취향저격ai` | 아래 섹션 참고 | `POST /author/taste-recommend` |
| `#도움말` | 사용 안내 패널 토글 | 정적 UI (API 없음) |

### 메모

```
메모 저장/수정:
  ├─ PUT /chats/{chatId}/memos    payload: { memos: [...] }
  └─ Redis: memos 키에 JSON 저장

메모는 다음 LLM 호출 시 context에 [작가 메모 — 반드시 반영할 것]으로 주입됨
```

### 맞춤법 교정 (실시간 교정 ON 시)

```
본문 변경 2.5초 후:
  POST /chats/{chatId}/proofread
    payload: { text(마지막 문단), character_id }
    → errors: [{original, corrected, type}]
    → 교정 제안 카드 표시, '넘기기' 클릭 시 용어집에 영구 추가
```

---

### 참고 데이터 요약

| 레이어 | 데이터 |
|--------|--------|
| DB | Session → World (세계관), Characters, 최근 Dialogue 5턴 |
| Redis | memos, summary, author_history (패널 내 대화), prev_user_questions |
| 작가 페르소나 | personas.py: 백야/차로운/한여름/김도현 — 피드백 톤 · 추천 방향 |
| 상태(state) | world, dbCharacters (페이지 진입 시 로드, 이후 재사용) |

---

## 3. `#취향저격ai` 버튼을 눌렀을 때

### 프론트엔드

```
handleTasteRecommend()
  └─ POST /chats/{chatId}/author/taste-recommend
       payload: { user_id, author_id(현재 선택된 작가) }
```

### 백엔드 내부 처리

```
[1] 사용자 취향 프로파일 조회
    DB: UserTasteProfile (user_id 기준)
    → 선호 장르, 선호 키워드
    → 없으면 "취향 정보 없음 (마이페이지에서 설정 후 더 정확한 추천 가능)"

[2] 소설 컨텍스트 조회
    DB: Session → World (제목/장르/배경/요약/규칙)
    DB: Characters (등장인물 목록)
    DB: Session.story_summary
    Redis: key_summary (더 최신이면 우선 사용, 앞 400자만)

[3] 최근 대화 기록 조회 (최신 10턴)
    Redis: key_history → reversed → role/content 변환
    → "주인공"(user) / "AI"(character) 레이블로 포맷

[4] 담당 작가 페르소나 조회
    personas.py: _AUTHOR_PERSONALITY[author_id]
    → taste_type_labels: 추천 방향 선택지 목록
      (예: '감정 폭발 순간', '말 없는 긴장', '반전 대사' 등)

[5] 프롬프트 조립 → LLM 호출
    TASTE_RECOMMEND_SYSTEM.format(
      taste_section    ← [1] 취향 프로파일
      novel_section    ← [2] 소설 컨텍스트
      dialogue_section ← [3] 최근 대화
      author_section   ← [4] 작가 페르소나 + 추천 방향 목록
    )

[6] 출력 형식 (JSON)
    {
      "recommendations": [
        { "type": "추천 방향", "narration": "묘사", "dialogue": "대사", "reason": "이유" },
        ...  (3개)
      ]
    }
```

### 취향 프로파일이 없을 때 → 취향 입력 패널

```
tasteWorks 입력 (엔터 키) → handleTasteInputKeyDown()
  └─ analyzeTaste(chatId, { user_id, works: [...] })
       POST /taste/analyze (또는 /chats/{chatId}/taste/analyze)
         → LLM이 작품 목록 분석 → 선호 장르·키워드 추출
         → DB: UserTasteProfile upsert
         → tasteProfile 상태 갱신
```

---

### 참고 데이터 요약

| 데이터 | 출처 | 용도 |
|--------|------|------|
| 선호 장르 / 선호 키워드 | DB UserTasteProfile | 취향 반영 |
| 세계관 (제목/장르/배경/규칙) | DB World | 소설 컨텍스트 |
| 등장인물 | DB Character | 소설 컨텍스트 |
| 줄거리 요약 | Redis summary (최신) / DB story_summary | 현재 상황 파악 |
| 최근 대화 10턴 | Redis history | 직전 문장 흐름 |
| 작가 페르소나 | personas.py 하드코딩 | 추천 방향 선택지 제한 |
