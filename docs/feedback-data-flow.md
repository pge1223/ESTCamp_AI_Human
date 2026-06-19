# 피드백 데이터 흐름 정리

피드백 기능은 크게 4가지 흐름으로 나뉜다.

---

## 1. 작가 피드백 (문장 피드백)

### 트리거 방식

| 방식 | 조건 |
|------|------|
| **수동** | 오른쪽 패널 "피드백 받기" 버튼 클릭 |
| **자동** | 자동 피드백 ON 상태에서 AI 응답 스트리밍 종료 2초 후 |
| **에디터 선택 구간** | 에디터에서 텍스트 드래그 선택 후 "선택 구간 피드백" 버튼 |

```
handleFeedback() 또는 triggerFeedback(text)
  └─ handleSendAuthorMessage(text, { mode: 'feedback', hideUser: true })
       └─ POST /chats/{chatId}/author/message
            payload: { content: 사용자 문장, author_id, mode: 'feedback' }
```

**chat 모드**: 마지막 사용자 메시지 전체 (`lastUserMsg.text`)
**editor 모드**: 선택 구간 있으면 선택 텍스트, 없으면 마지막 800자 (`getEditorFeedbackText()`)

---

### 백엔드: `/author/message` (mode=feedback)

```
[feedback 모드 — chat 모드와 다름, 스택이 짧다]

build_feedback_prompt(persona_id, world_context)
  ├─ DB: Session → World (세계관 문자열만, 등장인물·요약·메모 없음)
  └─ 프롬프트 구성:
       ├─ 작가 기본 페르소나 (PERSONA_PROMPTS[author_id])
       ├─ 작가별 feedback_lens (무엇을 볼지 — 감각/리듬/구조 등)
       ├─ 출력 형식 규칙 (번호 목록·볼드 헤더·경어·칭찬 금지)
       └─ 세계관 컨텍스트

LLM 호출 → 피드백 텍스트 생성
  └─ [SUGGEST:YES/NO] 마커 파싱
       YES → 이후 자동으로 추천 문장 생성 요청
       NO  → 추천 없이 피드백 텍스트만 표시

Redis: append_author_history() → 패널 내 대화 기록에 저장
```

> **참고**: 피드백 모드는 RAG·메모·요약 없이 **세계관+작가 렌즈+사용자 문장**만으로 판단한다.  
> 일반 채팅 모드(`mode: 'chat'`)와 달리 프롬프트 스택이 의도적으로 짧다.

---

### 추천 문장 자동 생성 (피드백 직후)

```
피드백 응답 수신 후 shouldRecommend=true 이면 자동 실행

fetchRecommendation(aiMsgId, authorCharacterId, userText, aiFeedback)
  └─ POST /chats/{chatId}/author/rewrite
       payload: { original: 사용자 원문, feedback: 방금 받은 피드백 텍스트, author_id }

       백엔드 build_rewrite_prompt() 참고 데이터:
         ├─ original        — 사용자가 쓴 원문
         ├─ feedback        — 방금 생성된 피드백 텍스트
         ├─ 작가 문체       — author.novel_style (페르소나별 문체 규칙)
         ├─ 작가 고쳐쓰기 규칙 — author.rewrite_rule
         ├─ 추가 스타일 규칙 — load_persona_rule(author_id) (파일 기반)
         ├─ DB: World       — 세계관
         ├─ DB: story_summary — 현재 줄거리
         ├─ Redis: memos    — 작가 메모
         ├─ RAG: memory.retrieve_relevant(original) — 원문과 관련된 과거 사건
         └─ Redis: author_history (최근 4턴) — 최근 작가 채팅 맥락

       절대 규칙:
         - 원문 단어를 그대로 반복하지 않음
         - 원문 표현 순서를 그대로 따르지 않음
```

#### 선택지 카드가 뜨는 경우

```
응답에 **1. 제목** / **2. 제목** 형식이 있으면 → parseNumberedChoices()로 선택지 파싱
사용자가 카드 선택 → handleChoiceSelect(msg, choice)
  └─ fetchRecommendation(msg.id, authorId, msg.userText, choice.body)
       → 선택된 방향의 피드백 본문으로 추천 문장 재생성
```

---

### 참고 데이터 요약 (피드백)

| 단계 | 데이터 | 출처 |
|------|--------|------|
| 피드백 생성 | 사용자 원문 | 채팅 마지막 메시지 / 에디터 선택 구간 |
| 피드백 생성 | 세계관 | DB World |
| 피드백 생성 | 작가 렌즈·페르소나 | personas.py 하드코딩 |
| 추천 문장 생성 | 원문 + 피드백 | 이전 단계 결과 |
| 추천 문장 생성 | 세계관 + 줄거리 | DB World, DB story_summary |
| 추천 문장 생성 | 작가 메모 | Redis memos |
| 추천 문장 생성 | 관련 과거 사건 | RAG (memory.retrieve_relevant) |
| 추천 문장 생성 | 최근 작가 채팅 4턴 | Redis author_history |

---

## 2. 실시간 맞춤법 교정

### 트리거

```
실시간 교정 ON 상태에서:
  chat 모드   : 대화 기록 없음 (교정 대상 없음, editor에만 적용)
  editor 모드 : 본문 변경 → 2.5초 debounce 후 마지막 문단을 교정

proofread(chatId, lastParagraph, currentAuthor.characterId)
  └─ POST /chats/{chatId}/proofread
       payload: { text: 마지막 문단, character_id }
```

### 백엔드: `/proofread`

```
[1] 보호 용어 수집 (창작 고유명사 — 오류로 잡지 않음)
    DB: Session → World → glossary (이전에 추출된 용어집)
    DB: Character.name (모든 등장인물 이름)
    최초 요청 시 glossary=null → LLM으로 세계관 텍스트에서 고유명사 자동 추출 → DB 캐시

[2] 맞춤법 검사
    services.proofread (F-QC-02, 네이버 맞춤법 기반)
    → 보호 용어 제외 후 diff 검출
    → errors: [{ original, corrected, type }]

[3] 개인 오답 누적
    DB: User.error_profile 갱신
    → 2회 이상 틀린 항목 → frequent=True 표시

[4] 작가 톤 메모 생성 (오류 있을 때만)
    LLM 호출 (경량)
    → 작가 페르소나 말투로 교정 내용 한 줄 메모
    → '빨간펜 선생님'이 아닌 '협업 작가의 여백 메모' 톤

응답: { errors: [...], memo: "한 줄 메모", count: N, checker_ok: bool }
```

### 교정 제안 처리 (프론트)

```
오류 제안 카드 표시
  ├─ "수정" 클릭 → onApplyCorrection() → 본문 내 해당 단어 치환
  └─ "넘기기" 클릭 → addGlossaryTerm(chatId, original)
       POST /chats/{chatId}/glossary
       → DB: World.glossary에 단어 영구 추가 (이후 교정에서 보호)
```

---

### 참고 데이터 요약 (맞춤법 교정)

| 데이터 | 출처 | 용도 |
|--------|------|------|
| 검사 대상 텍스트 | 에디터 마지막 문단 | 교정 입력 |
| 보호 용어 | DB World.glossary + Character.name | 고유명사 오검출 방지 |
| 세계관 텍스트 | DB World (title/setting/rules/description) | glossary 자동 추출 원본 |
| 개인 오답 이력 | DB User.error_profile | frequent 플래그, 능동 경고 |
| 작가 페르소나 톤 | proofread.py AUTHOR_TONE | 메모 말투 |

---

## 3. 능동 경고 (진입 시 자주 틀리는 것 미리 보기)

```
채팅 페이지 진입 시 (하루 1회, 본인이 닫으면 그날 다시 안 뜸)

getErrorWarmup(chatId, limit=3)
  └─ GET /chats/{chatId}/error-warmup?limit=3

       DB: Session → User.error_profile
       → 2회 이상 틀린 항목만 골라 상위 3개 반환
       → LLM 미사용 (누적 데이터 직접 활용)

localStorage: warmup_off_{chatId}_{오늘날짜} = '1' (닫으면 저장)
```

---

## 4. 문장 저장 (💾 버튼)

```
AI 추천 문장 카드 오른쪽 클릭 → 💾 아이콘 클릭

handleSaveSentence(msgId, content)
  └─ saveSentence({ userId, content, sessionId: chatId })
       POST /mypage/sentences (또는 /users/{userId}/sentences)
       → DB: 저장된 문장 (마이페이지 "저장한 문장" 탭에서 확인 가능)

저장 성공 시 → 1.5초 동안 아이콘 변경으로 피드백 표시
```

---

## 전체 피드백 흐름 한눈에 보기

```
사용자 문장 작성
    │
    ├─ [글 쓰는 중] 실시간 교정 (2.5초 debounce)
    │    └─ 네이버 맞춤법 + 보호어 제외 → 제안 카드
    │         ├─ 수정 → 본문 치환
    │         └─ 넘기기 → 용어집 추가
    │
    └─ [전송 후] AI 응답 수신
         │
         ├─ 자동 피드백 ON → 2초 후 자동 피드백 요청
         │    └─ 작가 피드백 텍스트 (세계관 + 작가 렌즈)
         │         └─ [SUGGEST:YES] → 추천 문장 자동 생성
         │              (원문 + 피드백 + 세계관 + 줄거리 + 메모 + RAG)
         │
         └─ 자동 피드백 OFF → "피드백 받기" 버튼으로 수동 요청
```
