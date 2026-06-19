# 가연 개발 로그

---

## 2026-06-17

### 작업 내용

#### 1. 메인 페이지 사이드바 — 드래그 방식 → 토글 버튼 방식 전환

**배경**: 메인 페이지 우측 개인 섹션(내 서재·내 소설 목록 등)이 드래그로 너비를 늘렸다 줄였다 하는 방식이었는데, 버튼 클릭으로 열고 닫는 방식으로 변경 요청.

**구현**
- 드래그 관련 state·핸들러 전부 제거 (`isDraggingPanel`, `panelRef`, `handleMouseMove`, `handleMouseUp`, `handlePanelDragStart`)
- `showPanel` state 추가, 헤더 안에 토글 버튼 배치 → 클릭 시 `author-panel-slide`가 `transform: translateX()`로 슬라이드 인/아웃
- 패널 안에 닫기 버튼(✕) 추가
- 토글 버튼: 처음엔 원형 → 가로로 늘림 → 평소엔 테두리 없이 SVG 3줄(☰) 아이콘만 보이다 호버 시 pill 테두리 + 배경색이 나타나는 형태로 마무리

---

#### 2. 버그: 메인 페이지 CSS 클래스 충돌로 채팅 페이지 피드백 패널이 먹통됨

**문제**: 메인 페이지 토글 버튼 작업 후 "소설작성 페이지에서 피드백 창이 안 열린다"는 보고.

**원인**: `main.css`에 새로 추가한 `.panel-toggle-btn`, `.author-panel-slide`, `.author-panel` 클래스명이 `components/AuthorPanel.jsx`(채팅·에디터 우측 작가 패널)가 쓰는 클래스명과 동일. CSS는 전역이라 두 페이지를 모두 방문하면 메인 페이지의 `.author-panel-slide { transform: translateX(100%); }` 규칙이 `AuthorPanel`에도 적용되어 패널이 항상 화면 밖으로 밀려남.

**수정**: 메인 페이지 전용 클래스를 전부 `main-` 접두사로 분리 (`main-panel-toggle-btn`, `main-author-panel-slide`, `main-author-panel`, `main-panel-close-btn` 등).

---

#### 3. 버그: 다크 테마에서 메인 페이지 패널 배경이 반투명

**문제**: 백야·차로운(다크 테마) 선택 시 메인 페이지 토글 패널을 열면 배경이 비쳐서 뒤 카드가 겹쳐 보임.

**원인**: 패널 배경이 `color-mix(in srgb, var(--theme-color) 8%, var(--bg-main))`였는데 다크 테마의 `--bg-main`이 사실상 투명에 가까운 값.

**수정**: 불투명 색상인 `--card-main`을 베이스로 변경 (`color-mix(in srgb, var(--theme-color) 10%, var(--card-main))`), 라이트 테마 오버라이드도 동일하게 통일.

---

#### 4. 버그: 이어쓰기 시 항상 백야 작가로 표시됨

**문제**: 한여름 등 다른 작가와 작업하던 소설을 "내 소설 목록"에서 이어쓰기해도 우측 작가 패널이 항상 백야(author1)로 뜸.

**원인**: `chat/ui.jsx`에서 세션 로드 후 `if (session?.author_id) setAuthorId(session.author_id)`로 테마용 `authorId`는 갱신하지만, 우측 패널이 어떤 작가를 보여줄지 결정하는 `currentAuthorIdx`는 컴포넌트 마운트 시점에 한 번만 `useState`로 초기화되고 이후 갱신되지 않음. 세션의 실제 `author_id`가 늦게 도착해도 반영이 안 됨.

**수정**: 세션 로드 useEffect에서 `session.author_id`를 받으면 `AUTHOR_IDS.indexOf(...)`로 인덱스를 다시 계산해 `setCurrentAuthorIdx`도 함께 호출하도록 수정 (`frontend/src/pages/chat/ui.jsx`).

---

#### 5. 기능: 소설 완결 버튼 추가 (내 소설 목록 / 채팅창 / 집필형 에디터)

**배경**: 완결 처리를 어디서든 할 수 있도록 — 목록에서 바로 완결 가능, 글 쓰는 화면에서도 저장과 별개로 완결 가능.

**구현**
- **내 소설 목록**(`storylist.jsx`): 진행 중인 세션에 `완결` 버튼 추가(삭제 버튼은 유지). 확인창 → `completeSession()` 호출 → 상태를 `completed`로 갱신. 완결된 소설은 `이어쓰기 →` 대신 `수정하기`로 바뀌고 클릭 시 `/editor`(집필형)로 이동
- **채팅창**(`chat/ui.jsx`): 기존 단일 `저장` 버튼을 `저장`(완결 없이 목록으로 이동) / `완결`(확인창 → `completeSession` + `generateNovel` → 읽기 페이지로 이동) 두 개로 분리
- **집필형 에디터**(`editor/ui.jsx`): 기존엔 자동저장 + `저장` 버튼만 있었음. `완결` 버튼 추가 — 확인창 → 초안 저장(`saveDraft`) → `completeSession` → 읽기 페이지로 이동. `editor/ui.css`가 `@import '../chat/ui.css'`로 스타일을 공유하므로 별도 CSS 작업 불필요

**수정 파일**
- `frontend/src/pages/storylist/storylist.jsx`, `storylist.css`
- `frontend/src/pages/chat/ui.jsx`, `ui.css`
- `frontend/src/pages/editor/ui.jsx`
- `frontend/src/pages/main/main.jsx`, `main.css`

---

### 남은 작업

- [x] 메인 페이지 사이드바 토글 버튼 전환
- [x] 메인-채팅 CSS 클래스 충돌 버그 수정
- [x] 다크 테마 패널 배경 투명도 버그 수정
- [x] 이어쓰기 작가 테마 미반영 버그 수정
- [x] 소설 완결 기능 (목록/채팅/에디터 3곳)
- [ ] 완결된 세션을 에디터(`/editor`)에서 다시 저장할 때 상태가 `completed`로 유지되는지 백엔드 검증
- [ ] Cloud Run 재배포 후 삽화 생성(Vertex Gemini 2.5 Flash Image) 실사용 테스트

---

## 2026-06-15

### 작업 내용

#### 1. illustration.py — fal.ai → Vertex Gemini 2.5 Flash Image 전환 (stash 충돌 해결)

**배경**: `git stash pop` 과정에서 `illustration.py` 충돌 발생. upstream(dev, jyj 작업)이 fal.ai FLUX를 Vertex AI Gemini 2.5 Flash Image로 이미 교체해둔 상태였고, 가연님 stash는 이전 fal.ai 버전 기반 변경.

**해결**: upstream(Vertex 버전) 채택. fal.ai는 유료에다 데이터센터 IP가 차단당하는 문제가 있었는데, Vertex는 ADC 인증이라 Cloud Run에서 별도 키 없이 동작하고 기존 GCP 크레딧으로 결제 가능.

```python
_IMAGE_MODEL = "gemini-2.5-flash-image"

def _generate_image_sync(prompt: str, ratio: str) -> str:
    from vertexai.generative_models import GenerativeModel
    llm._ensure_vertex()   # llm.py와 동일한 vertexai.init(ADC) 재사용
    ...
    model = GenerativeModel(_IMAGE_MODEL)
    resp = model.generate_content(full_prompt, generation_config={"response_modalities": ["TEXT", "IMAGE"]})
    # 응답 이미지 바이트 → base64 data URL (별도 스토리지 불필요)
```

미사용 `from app.core.config import settings` import 제거.

**수정 파일**: `backend/app/services/illustration.py`

---

#### 2. voice-suggest 백엔드 변경사항 되돌림

**배경**: voice-suggest 관련 백엔드 동작에 문제가 있어 원인 분석 중 팀장님이 해당 부분을 처음부터 다시 작업하기로 함 → 가연님 쪽 임시 변경분을 전부 되돌리고 팀장님 작업분을 기다리기로 함.

---

### 남은 작업

- [x] illustration.py Vertex 전환 (stash 충돌 해결)
- [x] voice-suggest 변경분 되돌림 (팀장님 재작업 대기)
- [ ] 삽화 생성 기능 Cloud Run 재배포 후 동작 확인

---

## 2026-06-14

### 작업 내용

#### 1. 채팅 입력 도움말(`#도움말`) 태그 추가

**배경**: 작가 패널의 `#세계관`·`#에피소드` 같은 태그 옆에, 대사/독백/행동 서술 문법을 안내하는 `#도움말` 태그를 추가해 사용자가 입력 규칙을 바로 확인할 수 있게 함.

**내용**: 클릭 시 카드로 4가지 입력 규칙 안내
- 대사 → 큰따옴표 `"왜 그러는 거야?"`
- 독백·속마음 → 작은따옴표 `'이 사람, 뭔가 숨기고 있어.'`
- 행동·서술 → 따옴표 없이 그대로
- `@등장인물` → 해당 인물 시점으로 전환

**수정 파일**: `frontend/src/pages/chat/ui.jsx`, `ui.css`

---

#### 2. 삽화 생성 기능 — 백엔드 신규 구현 + 읽기 페이지 UI 연동

**배경**: 완결된 소설의 특정 장면을 그림으로 만들어주는 삽화 기능. 이번엔 백엔드 엔드포인트부터 신규 구현하고 읽기 페이지에 UI를 연동.

**백엔드 (`illustration.py`, 최초 버전은 fal.ai FLUX 사용)**
- 2가지 모드: 직접 입력(사용자 장면 설명 → LLM 정제·필터 → 이미지 생성) / AI 추천(소설 내용 → LLM이 장면 후보 4종 제시 → 사용자가 선택)
- 장면 추천: `dramatic`(핵심) / `emotional`(감정) / `foreshadowing`(복선) / `fanservice`(팬서비스) 4유형
- 입력 필터링: 선정적·폭력적 표현 검수 후 `appropriate` / `refine_needed` / `inappropriate` 판정
- 스타일(웹툰풍·수채화풍·흑백·실사·파스텔) × 분위기(따뜻함·어두움·몽환적·긴장감·로맨틱) × 비율(1:1·9:16·16:9) 조합 지원
- `backend/app/api/v1/endpoints/illustrations.py` 신규 엔드포인트 + `router.py` 등록

**프론트 (읽기 페이지 `read.jsx`에 모달로 연동)**
- 모드 선택 → (직접입력 or AI추천 장면 선택) → 스타일/분위기/비율 선택 → 생성 → 결과 표시까지 단계별 모달 플로우
- `frontend/src/lib/illustrationApi.js` 신규 — API 연동 함수

**수정 파일**
- `backend/app/api/v1/endpoints/illustrations.py`(신규), `backend/app/services/illustration.py`(신규), `backend/app/api/v1/router.py`, `backend/app/core/config.py`
- `frontend/src/lib/illustrationApi.js`(신규), `frontend/src/pages/read/read.jsx`, `read.css`

---

### 남은 작업

- [x] `#도움말` 태그 추가
- [x] 삽화 생성 기능 백엔드 + 읽기 페이지 UI 연동 (fal.ai FLUX 최초 버전)
- [ ] fal.ai 데이터센터 IP 차단 이슈 → Vertex 전환 필요 (다음날 처리)

---

## 2026-06-13

### 작업 내용

#### 1. 채팅 미러링 버그 수정

**문제**: AI가 사용자 입력을 그대로 반복하는 미러링 현상 발생.

**원인**: Redis는 `lpush`로 저장하므로 history가 **최신순** 정렬(index 0 = 가장 최근). 그런데 코드가 `history[-1]`(가장 오래된 메시지)을 체크해 현재 사용자 메시지 제거를 시도 → 제거 실패 → 유저 메시지가 history 안에도 남고 `user_content`에도 한 번 더 붙어 LLM이 동일한 user 메시지를 두 번 연속으로 보게 됨 → 미러링 발생.

**수정** (`chats.py`):
```python
# 수정 전 — history[-1]은 가장 오래된 메시지
if context["history"] and context["history"][-1].get("role") == "user":
    context["history"] = context["history"][:-1]

# 수정 후 — history[0]이 가장 최근(현재 유저 메시지)
if context["history"] and context["history"][0].get("role") == "user":
    context["history"] = context["history"][1:]
```

---

#### 2. 등장인물 미등장 버그 수정

**문제**: 세계관에 등록한 등장인물들이 소설 채팅에서 등장하지 않음.

**원인**: `_COMMON_STYLE_RULE`에 "새 인물 임의 추가 최소화"라는 규칙만 있었고, 세계관에 이미 등록된 인물과 미등록 새 인물을 구분하지 않았음 → AI가 등록된 등장인물도 "아직 안 나온 새 인물"로 판단해 등장 회피.

**수정** (`personas.py`):
- `_COMMON_STYLE_RULE`: "새 인물" → "세계관에 없는 새 인물"로 한정 + 등록 인물은 자연스럽게 등장시킨다 명시
- `get_author_prompt` author 모드: `[등장인물 등장 규칙]` 섹션 추가

```python
# _COMMON_STYLE_RULE 변경
"세계관에 없는 새 인물·사건·장소 임의 추가 최소화함. "
"단, [세계관 정보]의 [등장인물]에 등록된 인물은 자연스러운 흐름에서 적극 등장시킴."
```

---

#### 3. 주인공(사용자 캐릭터) 내면 서술 + 대사 생성 금지

**문제**: AI가 주인공(사용자가 직접 연기하는 캐릭터)의 내면 독백, 감정, 대사를 대신 써버리는 문제.

**원인**: world_context의 protagonist 정보가 프롬프트 **맨 뒤** `[세계관 정보]` 안에 묻혀 있었고, 앞에 있는 "author mode = 소설 작가로서 모든 인물 서술 가능" 스타일 규칙이 더 강하게 작동.

**수정 내용**

`_build_world_context()` (`chats.py`): `session.protagonist_id` + `Character.is_ai_controlled`로 인물을 분리해 world_context에 구분 주입.

```
[사용자 조종 인물 — AI가 절대 대신 서술하지 않음]
- 한서윤 (protagonist): ...
※ 이 인물의 행동·대사·내면은 사용자 입력이 전부입니다.

[AI 서술 인물 — 이 인물들의 반응·대사를 생성]
- 강지후 (protagonist): ...
- 채린 (supporting): ...
※ speaker 필드에 말하는 인물 이름을 반드시 명시.
```

`build_messages()` (`chats.py`): world_context에서 주인공 이름을 추출해 **프롬프트 최상단**(`CRITICAL_OUTPUT_RULE` 바로 다음)에 `[최우선 규칙 — 역할 구분]` 블록을 동적으로 주입. 단순히 world_context 안에 넣는 것보다 LLM이 훨씬 강하게 따름.

```python
def _extract_protagonist_name(world_context: str) -> str:
    """world_context에서 [사용자 조종 인물] 이름 추출."""

def _extract_ai_char_names(world_context: str) -> list[str]:
    """world_context에서 [AI 서술 인물] 이름 목록 추출."""
```

주입되는 규칙 (예시):
```
[최우선 규칙 — 역할 구분]
이 채팅에서 사용자는 한서윤 역할을 직접 연기합니다.
AI는 강지후·채린의 반응·대사만 생성합니다.
절대 금지: 한서윤의 내면·감정·생각을 narration에 서술하는 것.
절대 금지: 한서윤의 대사를 dialogue에 생성하는 것.
절대 금지: speaker 필드에 한서윤을 넣는 것.
```

---

#### 4. 대화 speaker 표시 오류 수정

**문제**: 채린이 말하는 장면에서도 대화 뱃지가 "강지후"로 고정 표시됨.

**원인**: JSON 스키마에 `speaker` 필드가 없어 AI가 누가 말하는지 응답에 포함하지 않음 → 프론트가 `dbCharacters.find(c => c.role !== 'protagonist')?.name`으로 첫 번째 비주인공 이름을 모든 AI 대화에 고정 표시.

**수정**:
- `story.py OUTPUT_RULES`에 `speaker` 필드 추가
- `parse_ai_response` (`prompts/__init__.py`): `speaker` 추출
- SSE payload (`chats.py`): `speaker` 포함
- 프론트 `CharMessage` (`ui.jsx`): `msg.speaker` 우선 사용

```javascript
// ui.jsx
const charName = msg.speaker || characterName || msg.name;
```

**수정 파일**
- `backend/app/api/v1/endpoints/chats.py` — 미러링 fix, world context 분리, protagonist 최우선 규칙 주입, speaker 추출 + SSE payload
- `backend/app/core/personas.py` — `_COMMON_STYLE_RULE` 등록 인물 구분, author 모드 등장인물 등장 규칙 추가
- `backend/app/prompts/story.py` — `OUTPUT_RULES` speaker 필드 추가, narration 주인공 서술 금지 명시
- `backend/app/prompts/__init__.py` — `parse_ai_response` speaker 추출
- `frontend/src/pages/chat/ui.jsx` — speaker 수신 + 우선 표시

---

### 남은 작업

- [x] 채팅 미러링 버그 수정
- [x] 등장인물 미등장 버그 수정
- [x] 주인공 내면/대사 AI 서술 금지
- [x] 대화 speaker 표시 오류 수정
- [ ] personas.py few-shot 수정 (사용자 시나리오 기반)
- [ ] personas.py baekya 신체반응 금지 원칙 추가
- [ ] F-PR-01 사용자 프로필/취향 스키마 + 엔드포인트 (MBTI·장르·취미)
- [ ] F-PR-03 개인화 프롬프트 — 취향 기반 추천·코칭
- [ ] 삽화 생성 테스트 (소설 완성 후)

---

## 2026-06-12

### 작업 내용

#### 1. chats.py merge conflict 해결

**문제**: `feature/ygy`와 `dev` 브랜치가 동시에 `chats.py`를 수정해 충돌 마커 잔존.

**해결**: HEAD(feature/ygy) 유지. Redis 헬퍼들이 `chat_context.py`로 분리된 구조를 살리고, incoming 브랜치의 Redis 인라인 코드 블록 제거.

---

#### 2. Voice Mirroring — 채팅 대사 추천 voice-suggest 연동

**배경**: 말투 프로파일이 있는 사용자에게 `/voice-suggest` 엔드포인트 기반 맞춤 대사를 추천하도록 연동. 기존 일반 suggestions는 폴백으로 유지.

**추가 함수 (`chatApi.js`)**
```javascript
export async function getVoiceSuggestions(chatId, payload) {
  const res = await fetch(`${API_BASE_URL}/chats/${chatId}/voice-suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) return { suggestions: [] };
  return res.json();
}
```

**`fetchSuggestions` 수정 흐름 (`chat/ui.jsx`)**
```
말투 프로파일 있음 → voice-suggest 호출 → 추천 있으면 사용
           ↓ (실패 or 추천 없음)
           폴백: 기존 getSuggestions 호출
```

**추천 칩 렌더 개선**: voice-suggest 응답은 `{label, text}` 오브젝트 — `label`(예: "솔직하게 답하기")을 칩 위에 작게 표시. 기존 문자열 응답과 하위 호환 유지.

```jsx
{label && <span className="suggestion-chip__label">{label}</span>}
{text}
```

**수정 파일**
- `frontend/src/lib/chatApi.js` — `getVoiceSuggestions` 추가
- `frontend/src/pages/chat/ui.jsx` — `fetchSuggestions` voice-suggest 분기, 칩 렌더 개선
- `frontend/src/pages/chat/ui.css` — `.suggestion-chip__label` 스타일 추가

---

#### 3. 소설 목록 → 마이페이지 버튼 추가

소설 목록(storylist) 헤더에 마이페이지 이동 버튼 추가.

**수정 파일**
- `frontend/src/pages/storylist/storylist.jsx` — 헤더에 `<button onClick={() => navigate('/mypage')}>마이페이지 →</button>` 추가
- `frontend/src/pages/storylist/storylist.css` — `.storylist-header`에 `justify-content: space-between` 추가

---

#### 4. 마이페이지 말투 설정 카드 + 네비게이션 추가

**말투 설정 카드**: 말투 프로파일 로드 상태에 따라 분기.
- 프로파일 없음: "설정하기 →" 안내
- 프로파일 있음: `speech_level`, `sentence_length`, `tone.primary[:2]`, `emoji_style` 분석 태그 + `summary_for_user` 한 줄 표시 + "수정 →" 버튼

**NAV 연결**: 사이드 네비게이션에 `{ id: '말투 설정', icon: '✨' }` 추가 → 클릭 시 `/voice-profile`로 이동.

**수정 파일**
- `frontend/src/pages/mypage/mypage.jsx` — voice profile 상태 로딩, 카드 렌더, NAV 항목 추가
- `frontend/src/pages/mypage/mypage.css` — `.mp-voice-card`, `.mp-voice-tag` 등 스타일 추가

---

#### 5. 말투 설정 폼 — localStorage 저장·복원 + 수정 모드

**배경**: 폼을 작성하다 나가거나 재진입 시 처음부터 다시 써야 하는 문제 해결.

**구현**
- 모든 폼 상태(`requiredAnswers`, `optionalChecked`, `optionalAnswers`, `selectedGenres`, `genreAnswers`, `userSamples`, `optionalContext`)를 `useEffect`로 변경 시마다 `localStorage`에 자동 저장
- 초기 렌더 시 `loadSaved()`로 복원 (없으면 빈 기본값)
- `selectedGenres`(`Set`)은 `[...selectedGenres]`로 직렬화 후 복원 시 `new Set()` 변환
- 완료 화면에 "수정하기" 버튼 추가 — 클릭 시 `setDone(false)`로 폼으로 복귀

**수정 파일**
- `frontend/src/pages/voice/voice.jsx` — `STORAGE_KEY`, `loadSaved()`, `useEffect` 자동저장, 수정하기 버튼 추가
- `frontend/src/pages/voice/voice.css` — `.voice-btn-secondary` 스타일 추가

---

### 남은 작업

- [x] Voice Mirroring — voice-suggest 채팅 연동
- [x] 소설 목록 마이페이지 버튼
- [x] 마이페이지 말투 카드 + NAV 연결
- [x] 말투 설정 폼 localStorage 저장·복원
- [ ] personas.py few-shot 수정 (사용자 시나리오 기반)
- [ ] personas.py baekya 신체반응 금지 원칙 추가
- [ ] 채팅 입력 Enter 오작동 수정

---

## 2026-06-11

### 작업 내용

#### 1. Voice Mirroring (F-VM) — 사용자 말투 기반 대사 추천 기능 구현

**배경**: 사용자가 NPC 대사에 답할 때 "뭐라고 하지?"에서 막히는 문제를 해결하기 위해, 사용자의 말투를 분석해 그 사람처럼 들리는 대사 후보를 추천하는 기능 설계 및 구현.

**구조 (2단계)**
```
1단계: 사용자 샘플 문장 → 말투 프로파일 JSON 추출 (VOICE_PROFILE_SYSTEM)
2단계: 프로파일 + 현재 장면 + NPC 대사 → 사용자 대사 후보 5개 생성 (build_voice_suggest_prompt)
```

**핵심 설계 원칙**
- 말투 분석 프롬프트는 **생성 금지** — 분석만 수행, 원문 복사 절대 금지
- 대사 추천 프롬프트는 **원본 샘플 미참조** — summary_for_prompt(요약)와 generation_guidelines만 주입
- 말투 70% + 장면 맥락 30% 비율 반영, 충돌 시 장면 감정 우선

**추가 엔드포인트**

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/chats/{id}/voice-profile` | 사용자 샘플 문장 분석 → voice_profile 생성 + User DB 영구 저장 |
| POST | `/chats/{id}/voice-suggest` | 저장된 프로파일 기반 대사 5개 추천 |

**voice-profile 요청 바디**
```json
{
  "user_samples": ["자유 입력 문장"],
  "guide_answers": ["가이드 문장에 대한 사용자 답변"],
  "optional_context": "원하는 말투 방향 (선택)"
}
```

**voice-suggest 요청 바디**
```json
{
  "npc_dialogue": "NPC가 한 말",
  "scene_summary": "현재 장면 요약",
  "genre": "로맨스",
  "relationship_summary": "관계 설명",
  "character_profile": "등장인물 정보",
  "user_intent": "원하는 반응 방향",
  "user_emotion": "현재 감정",
  "constraints": "장면 제한 사항"
}
```

**voice-suggest 응답 구조 (5개 후보)**
```json
{
  "suggestions": [
    {"type": "honest_response",   "label": "솔직하게 답하기",    "text": "...", "emotion": "...", "intensity": 2, "why": "..."},
    {"type": "soft_response",     "label": "부드럽게 넘기기",    "text": "...", ...},
    {"type": "evasive_response",  "label": "회피하거나 농담하기", "text": "...", ...},
    {"type": "emotional_response","label": "감정 드러내기",      "text": "...", ...},
    {"type": "bold_response",     "label": "한 발 다가가기",     "text": "...", ...}
  ],
  "applied_voice_features": [],
  "safety_note": ""
}
```

**VOICE_PROFILE_SYSTEM 주요 분석 항목**
- `speech_level`, `sentence_length`, `rhythm`, `tone` (primary/secondary/avoid_overdoing)
- `situation_styles` — 당황·서운·미안·거절·설렘 등 상황별 말투 패턴
- `language_habits` — 종결어미·감탄사·선호 단어·피해야 할 단어
- `mirroring_risk` — 원문 반복 위험도 (낮음/보통/높음)
- `generation_guidelines` — 대사 추천 프롬프트에 자동 주입되는 금지 규칙
- `summary_for_user` — 사용자에게 보여줄 말투 요약
- `summary_for_prompt` — 생성 프롬프트에 넣을 짧은 요약
- confidence 값 (0.0~1.0), 샘플 3개 미만 시 0.6 이하 제한

---

#### 2. User 모델 voice_profile 컬럼 추가 + Alembic 마이그레이션

**배경**: voice_profile은 세션이 아닌 유저 단위 정보라 User 테이블에 영구 저장하는 것이 올바른 설계.

**변경 사항**
- `User` 모델에 `voice_profile: JSON` 컬럼 추가
- 마이그레이션 수동 작성 및 Neon DB 적용 완료

**마이그레이션 결과**
```
Running upgrade b2c3d4e5f6a7 -> c3d4e5f6a7b8, add voice_profile to users
```

**흐름**
```
POST /voice-profile
  → Session(chat_id) → user_id 조회
  → LLM 분석 → User.voice_profile = profile (DB 저장)

POST /voice-suggest
  → Session(chat_id) → user_id 조회
  → User.voice_profile 로드 → 대사 5개 생성
```

**수정 파일**
- `app/models/user.py` — voice_profile JSON 컬럼 추가
- `app/api/v1/endpoints/chats.py` — 두 엔드포인트 추가, User import 추가, Redis → DB 저장으로 변경
- `app/prompts/__init__.py` — VOICE_PROFILE_SYSTEM, build_voice_suggest_prompt 추가
- `migrations/versions/c3d4e5f6a7b8_add_voice_profile_to_users.py` — 마이그레이션 파일 신규 작성

---

### 남은 작업

- [x] F-WD-06 World.tags 컬럼 + 마이그레이션 + 엔드포인트
- [x] F-AS-02 POST /stuck 엔드포인트
- [x] F-CH-09 POST /npc-react 엔드포인트
- [x] Voice Mirroring (F-VM) — voice-profile + voice-suggest 엔드포인트
- [x] User.voice_profile 컬럼 + 마이그레이션 적용
- [ ] personas.py few-shot 사용자 시나리오 기반 수정
- [ ] personas.py baekya 신체반응 금지 원칙 추가
- [ ] 서버 배포 보조 (F-SY-08)

---

## 2026-06-10

### 작업 내용

#### 1. Neon 클라우드 DB 연동 (asyncpg SSL 처리)

**배경**: 팀 DB를 공유 클라우드로 전환. Neon 서버리스 PostgreSQL 사용.

**문제**: Neon URL이 `postgresql://...?sslmode=require` 형식인데 asyncpg는 `sslmode` 쿼리 파라미터를 지원하지 않아 연결 오류 발생.

**수정**: `_prepare_db_url()` 함수 추가 — URL 자동 변환 + SSL 처리.

```python
# database.py
def _prepare_db_url(url: str) -> tuple[str, dict]:
    # postgresql:// → postgresql+asyncpg:// 변환
    # sslmode=require → connect_args={"ssl": "require"} 로 이동
```

**수정 파일**
- `app/database.py` — `_prepare_db_url()` 추가
- `migrations/env.py` — `_prepare_db_url` import 및 적용 (Alembic도 동일 URL 변환 필요)
- `requirements.txt` — `psycopg2-binary==2.9.9` 추가 (팀원 `ModuleNotFoundError` 대응)
- `.env.example` — Neon URL 형식 예시 추가

**alembic upgrade head 결과**: 6개 migration 모두 Neon DB에 적용 완료.

---

#### 2. session.py 머지 충돌 해결

**문제**: `feature/ygy`와 `dev` 브랜치가 동시에 `session.py`를 수정해 충돌 마커(`<<<<<<<`, `=======`, `>>>>>>>`) 잔존 → `SyntaxError: invalid decimal literal`.

**해결**: 두 브랜치 변경사항 모두 살려서 수동 병합.

```python
# 최종 session.py — 두 브랜치 컬럼 모두 포함
author_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
current_state: Mapped[str | None] = mapped_column(Text, nullable=True)
story_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
```

---

#### 3. Alembic migration 체인 충돌 해결

**문제**: `a1b2c3d4e5f6` migration의 `down_revision`이 `81fac960a2a7`(feature/ygy)와 `e1f2a3b4c5d6`(dev) 두 개를 가리켜 체인 오류.

**해결**: `down_revision = 'e1f2a3b4c5d6'`으로 통일.

최종 migration 체인:
```
81fac960a2a7 → d4e5f6a7b8c9 → e1f2a3b4c5d6 → a1b2c3d4e5f6
```

---

#### 4. personas.py 업데이트 (출력 품질 개선)

동완님 피드백 기반으로 작성한 `personas_applied.py` 내용 반영.

**추가된 것**
- `_COMMON_STYLE_RULE` — 사용자 말 반복 금지 등 공통 출력 규칙 (9개)
- `_PERSONA_STYLE_RULES` — 페르소나별 `[금지 예시]` + `[규칙]` + `[예시]` (4개)
- `load_persona_rule(persona_id, compact=False)` — 공통 + 페르소나 규칙 조합 반환. `compact=True`시 `[예시]` 섹션 제거해 캐릭터 모드 토큰 절약
- `_RULE_DIR` — 외부 `.txt` 규칙 파일 경로 (jyj RAG 연동 준비용, 없으면 내장 규칙 fallback)

**수정된 것**
- `hanyeoreum.novel_style` — `[금지 표현]`이 dict 문자열 안에 섞여 있던 것 제거, `_PERSONA_STYLE_RULES`로 이동
- `hanyeoreum` few-shot — "심장이 한 박자 늦게 뛰었다" → "그가 내 젖은 소매를 먼저 보았다"로 교체 (직접 신체 반응 표현 제거)
- `get_author_prompt()` — mode="author" 시 `style_rules` 주입, mode="character" 시 `compact_style_rules` 주입
- `build_novel_system()` — `style_rules` 주입

**남은 개선 포인트**
- `baekya [규칙]`에 신체 반응 금지 원칙 추가 필요: "신체 반응(심장, 등골, 식은땀, 떨림)도 직접 쓰지 않음. 외부 관찰과 행동으로만 표현함."
- few-shot User 입력을 실제 사용자 입력 형식(큰따옴표 대사, 별표 서술)으로 교체 필요 (현재 전부 나레이터 서술 형식)

---

#### 5. F-WD-06 World.tags 컬럼 + 자동 분류 엔드포인트

**배경**: 세계관 태그를 LLM으로 자동 분류해 검색·필터에 활용.

**구현**
- `World` 모델에 `tags: Mapped[list | None] = mapped_column(JSON, nullable=True)` 추가
- `WorldResponse` 스키마에 `tags: list[str] | None = None` 추가
- Alembic 마이그레이션 수동 작성 및 Neon DB 적용 완료 (`b2c3d4e5f6a7`, down_revision: `a1b2c3d4e5f6`)

**추가 엔드포인트**

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/worlds/{id}/tags/classify` | 세계관 텍스트(title·description·setting·rules) → LLM 2단계 자동 태그 분류 |
| PATCH | `/worlds/{id}/tags` | 태그 수동 수정 |

**수정 파일**
- `app/models/world.py` — tags 컬럼 추가
- `app/schemas/world.py` — WorldResponse tags 필드 추가
- `app/api/v1/endpoints/worlds.py` — classify_tags, update_tags 엔드포인트 추가
- `migrations/versions/b2c3d4e5f6a7_add_tags_to_worlds.py` — 마이그레이션 파일 신규 작성

---

#### 6. F-AS-02 / F-CH-09 chats.py 엔드포인트 추가

**배경**: 동완님 작업 분담. `app/prompts/__init__.py`에 추가된 프롬프트 상수들을 엔드포인트에 연결.

**추가 엔드포인트**

| 메서드 | 경로 | 프롬프트 | 기능 |
|---|---|---|---|
| POST | `/chats/{id}/stuck` | `STUCK_HELP_SYSTEM` | 창작 막혔을 때 힌트 3개 (situation + hints[]) |
| POST | `/chats/{id}/npc-react` | `build_multi_npc_prompt()` | 조연 NPC 다중 동시 반응 (narration + responses[] + state_changes) |

**동작 방식**
- `stuck`: `world_context` 미입력 시 Redis에서 자동 조회, 최근 대화 6턴 포함
- `npc-react`: 요청 바디에 `npcs: [{name, personality, relationship}]` 리스트 전달. `recent_dialogue` 미입력 시 Redis에서 최근 4턴 자동 조회

**수정 파일**
- `app/api/v1/endpoints/chats.py` — `StuckRequest`, `NpcInfo`, `NpcReactRequest` Pydantic 모델 + 두 엔드포인트 추가, import에 `STUCK_HELP_SYSTEM`, `build_multi_npc_prompt` 추가

**참고**
- F-QC-01(consistency.py 호출)은 기존 `stream_response` 내에 이미 구현돼 있었음. `suggestion` 필드는 LLM 응답을 그대로 pass-through하므로 별도 수정 불필요.
- GET `/chats/{id}/suggest` (SUGGEST_NEXT_SYSTEM)는 이미 존재하므로 중복 추가 없음.

---

### 남은 작업

- [x] Neon 클라우드 DB 연동
- [x] session.py 머지 충돌 해결
- [x] personas.py 출력 규칙 개선 적용
- [x] F-WD-06 World.tags 컬럼 + Alembic migration + 엔드포인트
- [x] F-AS-02 POST /stuck 엔드포인트
- [x] F-CH-09 POST /npc-react 엔드포인트
- [ ] personas.py few-shot 사용자 시나리오 기반 수정
- [ ] personas.py baekya 신체반응 금지 원칙 추가
- [ ] 서버 배포 보조 (F-SY-08)

---

## 2026-06-09

### 작업 내용

#### 1. ContextManager 구현 (10턴 초과 시 대화 요약 주입)

**문제**: 대화가 길어질수록 전체 히스토리를 LLM에 그대로 전달해 토큰 낭비 + 컨텍스트 창 초과 위험.

**구현**: 10턴 초과 시 오래된 대화를 LLM으로 요약해 `sessions.context_summary`에 저장, 이후 요청부터 `[요약 + 최근 10턴]`만 LLM에 전달.

**동작 방식**

```
1~10턴:  그대로 전달 (최근 10턴)
11턴~:   오래된 턴(전체 - 최근 10) → summarize_history() → context_summary 저장
         LLM 전달: [이전 대화 요약] + [최근 10턴]
```

**수정 파일**
- `services/llm_router.py` — `summarize_history()` 메서드 추가 (Gemini로 3~4문장 요약)
- `endpoints/dialogues.py` — `turn_count > 10` 시 요약 트리거 + `context_summary` 주입 로직 추가, 히스토리 조회 `limit(20)` → `limit(CONTEXT_WINDOW=10)`
- `models/session.py` — `context_summary: Text` 컬럼 추가
- `migrations/versions/a1b2c3d4e5f6_add_context_summary_to_sessions.py` — migration 수동 작성 (Alembic Windows asyncpg 연결 문제 우회)

**Alembic 우회 이유**: asyncpg가 Windows에서 `localhost`를 IPv6(::1)로 먼저 시도 → WinError 1225 ConnectionRefused. Docker exec로 직접 SQL 실행 후 migration 파일 수동 작성.

```sql
-- Docker exec로 직접 실행
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS context_summary TEXT;
```

---

### 남은 작업

- [x] ContextManager 구현 (10턴 초과 시 요약)
- [ ] NovelConverter — `llm_router.generate_novel()` 실제 호출 연결
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)

---

## 2026-06-08

### 작업 내용

#### 1. 전역 에러 핸들링 미들웨어 추가

**문제**: DB/LLM 에러 발생 시 raw 500 응답이 나가서 프론트에서 원인 파악 불가.

**수정**: `main.py`에 전역 예외 핸들러 4개 추가. 어떤 에러든 항상 구조화된 JSON으로 반환.

| 상황 | error 키 | 상태코드 |
|---|---|---|
| 요청 데이터 형식 오류 | `validation_error` | 422 |
| 404, 400 등 의도된 에러 | `http_error` | 해당 코드 |
| DB 쿼리/연결 오류 | `database_error` | 500 |
| 그 외 모든 에러 | `internal_server_error` | 500 |

```python
# 수정 전
500 Internal Server Error  ← 원인 모름

# 수정 후
{"error": "validation_error", "message": "요청 데이터가 올바르지 않습니다.", "detail": [...]}
```

**수정 파일**
- `main.py` — `RequestValidationError`, `HTTPException`, `SQLAlchemyError`, `Exception` 핸들러 추가

---

#### 2. StreamingResponse 내부 DB 저장 버그 수정

**문제**: `dialogues/stream` 호출 시 서버 로그에는 저장 성공으로 찍히는데 `api_logs`, `dialogues`(AI 응답)가 DB에 실제로 저장되지 않는 버그.

**원인**: FastAPI의 `Depends(get_db)` 세션은 라우트 함수가 `return`하는 시점에 cleanup(commit/close)이 실행됨. 그런데 `StreamingResponse`의 `generate()` 제너레이터는 라우트 함수가 return한 **이후** ASGI 프레임워크가 소비하는 구조. 결과적으로 `generate()` 안에서 `db.flush()`를 호출해도 세션이 이미 닫혀서 commit이 보장되지 않아 rollback됨.

**수정**: `generate()` 내부에서 DB 쓰기가 필요한 경우 `Depends` 세션 대신 `AsyncSessionLocal()`로 독립 세션을 생성해 직접 commit.

```python
# 수정 전 — flush만 하고 commit 보장 안 됨
db.add(api_log)
await db.flush()

# 수정 후 — 독립 세션으로 명시적 commit
async with AsyncSessionLocal() as save_session:
    save_session.add(api_log)
    save_session.add(ai_dialogue)
    await save_session.commit()
```

**수정 파일**
- `endpoints/dialogues.py` — `generate()` 내부 AI 응답 + ApiLog 저장을 독립 세션으로 전환
- `endpoints/chats.py` — `generate()` 내부 AI 응답 + ApiLog 저장을 독립 세션으로 전환

---

#### 2. 동작 확인

Swagger UI → `POST /api/v1/sessions/{session_id}/dialogues/stream` 호출 후 psql 직접 확인:

```sql
SELECT model_used, prompt_tokens, completion_tokens, total_cost FROM api_logs;
-- gemini-2.5-flash | 39 | 11 | 0.00001245  ← 저장 확인
```

- `api_logs` 1건 저장 ✅
- `dialogues` USER + CHARACTER 모두 저장 ✅

---

### 남은 작업

- [ ] 컨텍스트 트리밍 (토큰 수 기준 히스토리 잘라내기)
- [x] ContextManager 구현 (10턴 초과 시 요약)
- [ ] NovelConverter — `llm_router.generate_novel()` 실제 호출 연결
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)

---

## 2026-06-07

### 작업 내용

#### 1. 토큰 사용량 추적 및 ApiLog 저장 구현

평가 기준 **"응답 엔진 운영 효율 (10점)"** 대응 작업.
매 LLM 호출마다 입력 토큰, 출력 토큰, 추정 비용을 `api_logs` 테이블에 저장.

---

#### 2. `services/llm_router.py` 수정

- Gemini 모델별 토큰 단가 상수 추가 (`_PRICE_PER_M`)
- `calc_cost()` 함수 추가 — 토큰 수 × 단가로 USD 비용 계산
- `_stream_gemini()` — 스트리밍 완료 후 `response.usage_metadata`에서 토큰 수 수집 (`usage_out` 파라미터)
- `stream_character_response()`, `stream()` — 스트리밍 후 `event: log` SSE 이벤트로 토큰 정보 전달
  - 이 이벤트는 클라이언트에 전달되지 않고 엔드포인트 레이어에서만 소비됨

**Gemini 단가 기준 (2025)**

| 모델 | 입력 (1M tokens) | 출력 (1M tokens) |
|------|-----------------|-----------------|
| gemini-2.5-flash | $0.15 | $0.60 |
| gemini-1.5-flash | $0.075 | $0.30 |

---

#### 3. `endpoints/dialogues.py` 수정

- `stream_character_response()` 반환값 중 `event: log` 감지
- 클라이언트에 전달하지 않고 `ApiLog` 레코드 생성 후 PostgreSQL 저장

---

#### 4. `endpoints/chats.py` 수정

- Gemini 스트리밍 완료 후 `response.usage_metadata`에서 토큰 직접 수집
- AI 응답 저장 시 `ApiLog`도 함께 저장

---

#### 5. `schemas/api_log.py` 신규 생성

- `ApiLogResponse` — 로그 목록 조회용
- `ApiLogSummary` — 일별 집계 조회용

---

#### 6. `endpoints/api_logs.py` 신규 생성 (보고서용 조회 API)

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/v1/api-logs/` | 호출 로그 목록 (session_id 필터 가능) |
| `GET /api/v1/api-logs/summary?days=7` | 일별 토큰·비용 집계 |
| `GET /api/v1/api-logs/total` | 전체 누적 통계 |

---

### 데이터 흐름 (토큰 추적 포함)

```
LLM 스트리밍 호출
  → Gemini 응답 청크 → SSE로 클라이언트 전달
  → 스트리밍 완료 후 usage_metadata 수집
  → event: log (내부 전달) → ApiLog DB 저장
      - model_used, prompt_tokens, completion_tokens, total_cost, session_id

GET /api/v1/api-logs/total → 전체 누적 비용 확인
GET /api/v1/api-logs/summary → 일별 사용량 (보고서 그래프용)
```

---

### 남은 작업

- [ ] 컨텍스트 트리밍 (토큰 수 기준 히스토리 잘라내기)
- [ ] ContextManager 구현 (10턴 초과 시 요약)
- [ ] NovelConverter — `llm_router.generate_novel()` 실제 호출 연결
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)

---

## 2026-06-05 (2)

### 작업 내용

#### 1. MongoDB 완전 제거 → PostgreSQL 단일 DB 전환

팀 결정으로 MongoDB를 걷어내고 PostgreSQL 단일 구조로 일원화.
RAG 벡터 임베딩도 현재 스코프에서 불필요하다는 판단으로 함께 제거.

**제거한 것들**
- `motor`, `sentence-transformers` 패키지 제거
- `services/rag_service.py` 삭제 (임베딩 저장/검색 서비스)
- `database.py`의 MongoDB 클라이언트 코드 제거
- `main.py`의 motor import 제거
- `docker-compose.yml`의 mongo_data 볼륨 제거
- `.env` / `.env.example`의 MONGODB_URL, MONGODB_DB_NAME 제거

**PostgreSQL로 전환한 엔드포인트**
- `endpoints/worlds.py` — Motor 쿼리 → SQLAlchemy
- `endpoints/characters.py` — Motor 쿼리 → SQLAlchemy
- `endpoints/dialogues.py` — Motor 쿼리 → SQLAlchemy
- `endpoints/novels.py` — MongoDB 대화 조회 → SQLAlchemy
- `api/chats.py` — MongoDB 의존성 제거, PostgreSQL 저장 연동

**모델/스키마 복원**
- `models/dialogue.py` — Pydantic DocumentModel → SQLAlchemy ORM 복원 (embedding 필드 없이)
- `models/session.py` — dialogues relationship 복원
- `models/__init__.py` — Dialogue import 복원
- `schemas/dialogue.py` — str → UUID 타입 복원, from_attributes 복원

---

#### 2. git merge 충돌 해결

dev 최신화 없이 push했다가 `git stash` → `git pull origin dev` → `git stash pop` 과정에서 `chats.py` 충돌 발생.

충돌 내용: 팀장님이 Redis 캐시 구조 추가, 가연님이 MongoDB 저장 코드 추가 — 두 버전이 겹침.
해결: Redis 캐시 구조(팀장님) + PostgreSQL 저장(가연님) 두 가지 모두 살려서 병합.

---

#### 3. Alembic migration 추가

```
migrations/versions/81fac960a2a7_add_dialogues_table.py
```

dialogues 테이블 PostgreSQL에 신규 추가. `alembic upgrade head`로 적용 완료.

---

#### 4. PostgreSQL 저장 동작 확인

Swagger UI → `POST /api/v1/worlds/` 테스트 후 psql에서 직접 확인:
```sql
SELECT id, title, genre FROM worlds;
-- 1 row 반환 확인
```

---

### 데이터 흐름 (현재 구조)

```
사용자 메시지 전송 (POST /api/chats/{chat_id}/messages)
  → Redis에 히스토리 저장 (실시간 캐시)
  → PostgreSQL dialogues 테이블에 영구 저장 (chat_id가 유효한 session UUID인 경우)

AI 응답 요청 (GET /api/chats/{chat_id}/stream)
  → Redis에서 최근 대화 히스토리 조회
  → 페르소나 시스템 프롬프트 + 히스토리 조합
  → Gemini 2.5 Flash 호출
  → SSE 스트리밍으로 프론트에 전달
  → 완료 후 AI 응답 PostgreSQL에 저장
```

---

### 남은 작업

- [ ] Redis 캐싱 구현 (최근 N개 대화, 캐릭터 정보, 호감도)
- [ ] ContextManager 구현 (10턴 초과 시 요약)
- [x] 토큰 사용량 기록 및 비용 모니터링
- [ ] 컨텍스트 트리밍 (토큰 한도 초과 방지)
- [ ] NovelConverter (대화 → 소설 변환)
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)

---

## 2026-06-05

### 작업 내용

#### 1. chats.py DB 연결 (팀장님 TODO 파트 구현)

`api/chats.py`의 `send_message`, `stream_response` 두 함수에 MongoDB 연결 추가.

**`send_message` 변경사항**
- 기존: 랜덤 ID만 반환, 저장 없음
- 변경: MongoDB turn 수 조회 → `DialogueDocument` 생성 → `save_with_embedding()`으로 임베딩 포함 저장 → 저장된 ID 반환

**`stream_response` 변경사항**
- 기존: 히스토리 없이 매번 새로 Gemini 호출
- 변경:
  1. MongoDB에서 최근 10개 대화 조회
  2. 대화 히스토리 텍스트 조합
  3. 시스템 프롬프트 + 히스토리 + 사용자 입력 합쳐서 Gemini 호출
  4. 스트리밍하면서 응답 텍스트 수집
  5. 완료 후 AI 응답 MongoDB에 저장 (임베딩 포함)

---

#### 2. 동작 확인 (로컬 테스트)

- `POST /api/chats/test-ygy/messages` → 201 응답, MongoDB `dialogues` 컬렉션에 `speaker_type: 'user'` + 임베딩 저장 확인
- `GET /api/chats/test-ygy/stream` → 백야 페르소나로 SSE 스트리밍 응답 확인, MongoDB에 `speaker_type: 'character'` + 임베딩 저장 확인

---

### 데이터 흐름 (현재 구조)

```
사용자 메시지 전송 (POST /api/chats/{chat_id}/messages)
  → MongoDB에 사용자 발화 저장 (텍스트 + 임베딩 벡터)

AI 응답 요청 (GET /api/chats/{chat_id}/stream)
  → MongoDB에서 최근 10개 대화 히스토리 조회
  → 페르소나 시스템 프롬프트 + 히스토리 조합
  → Gemini 2.5 Flash 호출
  → SSE 스트리밍으로 프론트에 전달
  → 완료 후 AI 응답 MongoDB에 저장 (텍스트 + 임베딩 벡터)
```

---

### 남은 작업

- [x] Alembic migration 재생성 (Character/User/World 모델 수정사항 반영)
- [ ] Redis 캐싱 구현 (최근 N개 대화, 캐릭터 정보, 호감도)
- [ ] ContextManager 구현 (10턴 초과 시 요약)
- [ ] 토큰 한도 관리
- [ ] NovelConverter (대화 → 소설 변환)
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)

---

## 2026-06-04

### 작업 내용

#### 1. DB 이중 구조 설계 및 구현

강사님 피드백 + 팀 회의 결과로 DB 이중 구조 도입 결정.

| DB | 저장 데이터 |
|----|------------|
| PostgreSQL | User, World, Character, Session, Novel, ApiLog |
| MongoDB | Dialogue (대화 로그 + RAG 벡터 임베딩) |
| Redis | 응답 캐싱 (CacheService) |

**이유:** Dialogue는 채팅 로그라 쓰기가 매우 빈번하고, RAG 벡터 임베딩을 함께 저장해야 해서 MongoDB가 적합. PostgreSQL은 관계형 데이터 유지.

---

#### 2. MongoDB 인프라 세팅

- `docker-compose.yml` — MongoDB 서비스 및 볼륨 추가
- `requirements.txt` — `motor`, `sentence-transformers` 추가
- `core/config.py` — `MONGODB_URL`, `MONGODB_DB_NAME` 환경변수 추가
- `database.py` — Motor 클라이언트(`mongo_client`) 및 `get_mongo_db()` 의존성 추가
- `main.py` — FastAPI `lifespan`으로 앱 시작 시 MongoDB 자동 연결/종료 관리
- `.env.example` — MongoDB 환경변수 예시 추가

---

#### 3. Dialogue PostgreSQL → MongoDB 이전

- `models/dialogue.py` — SQLAlchemy ORM 모델 제거, Pydantic `DialogueDocument`로 교체. `embedding` 필드(RAG용 벡터) 추가
- `models/session.py` — `dialogues` relationship 제거 (Dialogue가 MongoDB로 이전됨)
- `models/__init__.py` — `Dialogue` import 제거
- `schemas/dialogue.py` — ID 타입 `uuid.UUID` → `str` 변경 (MongoDB 호환), `from_attributes` 제거
- `endpoints/dialogues.py` — SQLAlchemy 쿼리 전체 Motor 쿼리로 전환. 대화 저장 시 임베딩 자동 생성
- `endpoints/novels.py` — 대화 로그 조회를 PostgreSQL → MongoDB로 변경

---

#### 4. RAG 서비스 구현

`services/rag_service.py` 신규 작성.

**핵심 기능 2가지:**
- `save_with_embedding()` — 대화 저장 시 `sentence-transformers`로 텍스트 벡터 생성 후 MongoDB에 함께 저장
- `search_similar()` — 새 메시지 입력 시 과거 대화 중 의미상 유사한 것 top-k 검색 (Python 코사인 유사도, MongoDB Atlas 없이 동작)

**임베딩 모델:** `paraphrase-multilingual-MiniLM-L12-v2` (한국어 지원, 로컬 실행)

---

#### 5. LLMRouter PromptBuilder + RAG 연결

`services/llm_router.py` 업데이트.

- `_build_prompt()` 함수 추가 — 페르소나 시스템 프롬프트 + RAG 컨텍스트 + 대화 히스토리 조합
- `stream_character_response()` 호출 시 RAG 검색 결과 자동 프롬프트 주입
- 실제 AI 호출 부분은 TODO (PERSO API / Ollama 연결 예정)

---

#### 6. Alembic 초기 Migration 생성

```bash
alembic revision --autogenerate -m "init"
alembic upgrade head
```

PostgreSQL에 6개 테이블 생성 (users, worlds, characters, sessions, novels, api_logs). `dialogues` 테이블은 MongoDB로 이전했으므로 제외.

---

#### 7. DB 모델 수정

팀 요구사항 반영:

**Character 모델**
- `background`, `appearance` 제거 → `prompt` 필드 하나로 통합
- `system_prompt` → `prompt`로 이름 변경
- `user_id` 추가 (String 타입, users 테이블 FK 없음 — 기기별 랜덤 식별자)
- `dialogues` relationship 제거

**User 모델**
- `email`, `hashed_password` → nullable (로그인 기능 추후 구현 예정)

**World 모델**
- `rules` → nullable (선택 입력)

스키마(character, user, world)도 모델 변경사항 반영.

---

### 데이터 흐름 (현재 구조)

```
사용자 메시지
  → PostgreSQL에서 Session/Character 유효성 검증
  → 사용자 발화를 MongoDB에 저장 (텍스트 + 임베딩 벡터)
  → 과거 대화에서 유사한 내용 검색 (RAG)
  → 페르소나 프롬프트 + RAG 컨텍스트 + 대화 히스토리 조합
  → LLM 호출 (TODO: PERSO API / Ollama)
  → AI 응답을 MongoDB에 저장 (텍스트 + 임베딩 벡터)
  → SSE 스트리밍으로 프론트에 전달
```

---

### 남은 작업

- [x] `chats.py` DB 연결 (메시지 MongoDB 저장, 대화 히스토리 프롬프트 주입)
- [ ] Alembic migration 재생성 (모델 수정사항 반영)
- [ ] Redis 캐싱 구현 (최근 N개 대화, 캐릭터 정보, 호감도)
- [ ] ContextManager 구현 (10턴 초과 시 요약)
- [ ] 토큰 한도 관리
- [ ] NovelConverter (대화 → 소설 변환)
- [ ] Guardrail (연령대별 콘텐츠 필터)
- [ ] DB 시드 데이터 (페르소나 4개 기본 캐릭터)
