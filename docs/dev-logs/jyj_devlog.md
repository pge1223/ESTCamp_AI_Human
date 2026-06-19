<!-- markdownlint-disable MD024 -->
# jyj 개발일지

---

## 2026-06-16 (TTFB 개선·세계관 수정 기능·CER 측정·배포·자기평가서)

> **TTFB 실효 개선**(저장·요약 deferral + min-instances=1 → p50 8.7→**5.9s**·p95 16.5→**6.8s**). 세계관 수정 기능(688ad35) 백엔드 e2e 전부 통과 + 프론트 UI 보완(집필형 진입 버튼·공백·복귀). CER 0.071 측정. Cloud Run 00043→00045 재배포(시크릿 보존). 자기평가서 갱신.

### 작업 내역

#### 1. TTFB 단축 — 저장·요약을 reply 뒤로 deferral 🔥

- **계측 먼저**(추측 금지): 스트림 단계분해 = context 0.7s · retrieval 0.3s · **생성 2s** · **post-gen(DB저장+요약) 1.5s**. 응답 텍스트는 이미 만들어졌는데 **Neon 크로스리전 커밋·요약 재생성을 기다렸다 보여주던** 구조.
- **수정**: `reply` yield를 DB저장·요약 **앞으로** 이동(Dialogue id 미리 생성해 `messageId` 일관성 유지). 서버측 total_to_reply **4.6→3.2s**(저장·요약 ~1.5s 제거). `[TTFB]` 단계 로그 추가(모니터링).
- **min-instances=1**: scale-to-zero 콜드스타트 제거(워밍업 17s 관측) → **프로덕션 p50 8.7→5.9s, p95 16.5→6.8s**(꼬리지연 절반↓).
- 남은 건 토큰 스트리밍(첫 토큰 기준) + Neon 리전 정렬.

#### 2. CER 측정 완료 (cer_eval)

- ElevenLabs TTS → Whisper base, 4문장 평균 **CER 0.071**(목표 ≤0.10 충족). 개별 0.032/0.043/0.167/0.040 — "단팥빵→단팝방" 받침 오인식이 평균을 끌어올림(large-v3로 개선 여지).

#### 3. 세계관 수정 기능(688ad35) — e2e + 프론트 진단·보완

- **백엔드 e2e(프로덕션) 전부 통과**: updateWorld(PUT 200)·수정 영속(호러→로맨스)·캐릭터 create/update/delete·**수정 후 서버 권위 재구성 즉시반영**. chats.py가 `world_context`를 항상 DB에서 재구성하도록 바뀜.
- **프론트 "안 뜸" 진단**: worldEdit UI(라우트·버튼·파일)는 `feature/jyj`에 정상 푸시됐으나 **dev에 미머지**(PR #101 머지 후 커밋됨) → Vercel 프로덕션(dev 빌드)에 미노출. 코드 문제 아님.
- **UI 보완**: ① 집필형(editor) 헤더에 `✎ 세계관` 버튼(채팅엔 있는데 집필엔 없던 비대칭 해소) ② **공백 수정** — `worldview.css`의 `.form-group{height:275px}`(생성 페이지용)가 수정 화면에 과한 세로 공백 → `.worldedit-container` 한정 `height:auto` 오버라이드 ③ 저장 후 **들어온 모드로 복귀**(from: chat→/chat, editor→/editor, 목록→뒤로).

#### 4. 배포 + 배포 명령 보강

- Cloud Run **00043**(TTFB deferral + min-instances=1) → **00045**(세계관 수정 688ad35). `--set-secrets/--set-env-vars` **생략**으로 기존 시크릿(`DATABASE_URL·REDIS_URL·FAL_KEY·OPENAI_API_KEY`) 전부 보존 — 안전 재배포.
- **server-ops 표준 배포 명령에 `OPENAI_API_KEY` 누락 발견** → 그대로 쓰면 전체교체로 폴백 키 삭제 위험(FAL_KEY 사고 재판). 명령에 `OPENAI_API_KEY`·`--min-instances=1` 추가 + 안전 재배포 팁 기록.

#### 5. 자기평가서 + OpenAI 키 진단

- **자기평가서** — 한 일(개인화 RAG·TTFB·평가 방법론)·**약점→근거→개선계획**(MOS·세계관 가드 프롬프트 한계·테스트셋 n)·배운점(자기채점 거품/프롬프트 한계/RAG는 추천층) 갱신.
- **OpenAI 키** — `insufficient_quota` 재확인(잔액 0 아님 — **결제수단 미등록/크레딧 만료/org 불일치** 중 하나). 진짜 GPT 비교는 결제 풀리면 `provider=` 지원으로 자동 작동.

### 검증 / 배포

- 백엔드 e2e(세계관 수정) 전부 통과 · 프론트 빌드 **2912 모듈 변환 ✓**(로컬 윈도우 EPERM은 Vercel 무관) · Cloud Run **00045** health ok · 시크릿 4종 보존 확인.

### 다음 할 일

- **feature/jyj → dev PR 머지**(worldEdit + 공백수정 + 복귀 + 집필형 버튼 프로덕션 노출, dev 1승인 필수) · **SSE 토큰 스트리밍 배포**(첫 토큰 기준 TTFB) · **MOS**(휴먼 5~10명) · Neon 리전 정렬

---

## 2026-06-15 (이어서 4 — 강사 피드백 분석·평가 엄밀화·개인화 RAG·균형 테스트셋)

> 강사님 피드백 **냉철 분석**(받을것/거를것). 평가의 **자기채점 거품**을 발견 → 독립 심판·출제편향 제거·인과 ablation으로 엄밀화(**단발 변환은 무승부 확정**). **개인화 RAG(취향저격)** 인과 검증. 세계관 정합성 가드. **균형 테스트셋 40문항**.

### 작업 내역

#### 1. 강사님 피드백 냉철 분석 (scrum/2026-06-15.md)

- 강사님 피드백 7개를 "공격 예고편"으로, 우리 시각을 🟢받을것/🟡조건부/🔴거를것으로 3단 분류. 핵심: **"기능을 더 만들라"가 아니라 "있는 걸 증명·가시화하라"** — 진짜 리스크는 구현 부족이 아니라 설명 부족.

#### 2. 진짜 GPT 비교 배선

- `llm.generate(provider=)` 오버라이드(베이스라인/심판을 특정 모델로 강제) · `evaluate.score_novel(judge_provider=)`(독립 심판) · `evidence_report` 공정 베이스라인(세계관+페르소나 동일 주입) + provider 자동선택(openai→groq).

#### 3. 측정 엄밀화 — 자기채점 거품 제거 🔥

- **자기채점(Gemini가 Gemini 채점)은 거품**: "문체 우위 +1.00"이 **독립 심판(Groq/Llama)으론 ±0으로 소멸**.
- **공정 베이스라인 ablation**(세계관·페르소나 동일, RAG만 차이) → **단발 변환은 무승부 확정**(캐릭터 +0.1·문체 -0.1·완성도 -0.3, 노이즈). "캐릭터 +0.6"은 100% 맥락 핸디캡 거품이었음.
- 결론: **단발 변환 품질로는 GPT/Gemini를 못 이긴다(정직).** 차별점은 변환이 아니라 장기기억·검수.

#### 4. rag_recall_eval (신규) — 기억 RAG 정량(엄밀)

- 동어반복 제거: target 비밀 + **의미적으로 비슷한 방해 비밀 3개** 경쟁 + **POST-only 매장**(스트리밍 안 해 rolling summary 미생성 → OFF 깨끗). 결과 **검색 top-1 12/12(100%)**(방해 속에서도 1순위), 그러나 **응답 반영 +17%p**(검색 성공해도 모델이 답에 항상 쓰진 않음 — 검색≠생성).

#### 5. consistency_eval (신규) — 모순 탐지 정량(출제 편향 제거)

- 내가 출제·라벨 → **독립 모델(Groq) 교차 라벨링**으로 편향 제거. 합의셋(나↔독립 92%) 기준 **검수기 정확도 95%, recall 100%/정상오탐 10%**. **애매 케이스 2건은 내 라벨이 독립과 갈림**(출제 편향 노출). recall 편향(놓치느니 잡음) 성격 확인.

#### 6. 개인화 RAG — 취향저격 (personalize.py 신규) ⭐

- 미사용 자산이던 **`SavedSentence`(사용자 저장 문장)를 의미검색**해 취향저격 추천의 근거로 주입(memory 임베딩 인프라 재사용). 개인화 경계 준수(추천 층만).
- **인과 e2e**(통제 실험): 동일 세계관·장면·작가, **저장 톤만 다른** 3명 → 추천 톤 **DARK 4.0 < NONE 5.9 < WARM 6.9 완벽 단조**(효과 +2.9). **교훈: RAG는 생성(+17%p)보다 추천 층에서 ROI가 크다** — 1순위 판단이 데이터로 확인됨.

#### 7. 세계관 정합성 가드

- **작가 피드백·취향추천 프롬프트**에 "입력이 세계관 장르·배경과 충돌(현실에 용)하면 문체보다 먼저 지적" 가드 추가(4작가 공유, 과민 방지 포함). 라이브 검증(용→충돌 지적 / 정상→헛경고 없음).
- **generate_novel(집필 변환)엔 프롬프트 가드 2회 시도했으나 무효**(변환 모델의 입력 충실 렌더링 편향) → 토큰만 늘어 되돌림. 장르 일탈은 **상류(채팅 out_of_genre·피드백 가드)에서 차단**되므로 실사용 영향 제한적.

#### 8. 균형 테스트셋 40문항 (testset.jsonl + testset_eval, 신규)

- 가이드북 분포(일상40/페르소나30/엣지20/안전10)로 정식 평가셋 + 독립 심판 채점. **페르소나 82%·일상 76%·엣지 68%·안전 거절 4/4(100%)**. 엣지서 현실+용 6/20·메타 이탈 7/20 등 **약점 노출**(generate_novel 세계관 가드 부재).

### 검증 / 배포

- 측정 스크립트 다수 신규(`rag_recall_eval`·`consistency_eval`·`testset_eval`·`personalize_e2e`) · 발표_정량근거 **부록 G-6~G-9 신설** + 자기채점 거품 정정. PR #95 머지, #101 누적.

### 다음 할 일

- **MOS(휴먼 평가)** — 유일한 major 공백 · 테스트셋 n 확대 · generate_novel 구조적 세계관 가드(프롬프트로는 안 됨)

---

## 2026-06-15 (이어서 3 — 작가 음성 리액션·문맥 기반 리액션·머지 충돌 해결)

> 작가 아바타가 **목소리로** 리액션(ElevenLabs TTS). 키를 Cloud Run에 못 올리는 제약을 **Vercel 서버리스 함수 프록시**로 우회. 리액션을 고정 풀 → **사용자 입력+작가 답변 문맥 기반 LLM 생성**으로. origin/dev(가은 PR #98) 머지 충돌 해결.

### 작업 내역

#### 1. 작가 리액션 음성(TTS) — Vercel 서버리스 프록시 🔊

- **제약**: ElevenLabs 키를 Cloud Run에 못 올림(키 정책 + 데이터센터 IP 차단). → 백엔드 경유 불가.
- **해결**: `frontend/api/tts.js`(Vercel 서버리스 함수)가 ElevenLabs를 프록시. 키는 **Vercel 서버사이드 env**에만(브라우저 노출 X, `VITE_` 아님), 송신 IP도 Cloud Run과 달라 **차단 우회**. Cloud Run은 리액션 텍스트만 생성(키 불필요).
- `ttsApi.speakReaction`(겹침 취소·실패 무시) + chat에 **🔊/🔇 토글**(localStorage). `vercel.json` rewrite가 `/api/` 안 삼키게 예외(`/((?!api/).*)`).
- 키 매핑: 키1 차로운·한여름 / 키2 백야·김도현.

#### 2. 문맥 기반 리액션 (감정 매칭)

- 기존: 사용자 입력만 보고 감정 분류 → **고정 풀**(reactions.py)에서 한마디.
- 변경: **사용자 입력 + 작가 답변** 문맥으로 감정 파악 → 작가 말투로 짧은 한마디 **LLM 생성**(`generate_reaction`, `personas.reaction_tone`). 호출 시점을 전송 즉시 → **응답 완료 후**로 이동(답변을 봐야 문맥 감정이 잡힘).
- **건혁님 감정 풀 보존**: 생성 실패 시 `pick_reaction` 폴백 — reactions.py 미수정(머지 충돌 없음).

#### 3. 리액션 타임아웃 폴백

- 리액션을 onDone에 걸었더니, 스트림이 느리거나 멈춰 **50초 타임아웃(수동 close → onDone 미발동)** 이면 리액션이 통째로 안 뜨던 회귀 → 타임아웃 경로에서도 `fireReaction` 호출하게 보강.

#### 4. origin/dev 머지 충돌 해결

- 가은님 PR #98 머지 중 `ui.jsx` onDone 충돌(**dev: 스트림 실제 msgId 교체** vs **mine: 리액션 생성**) → **양쪽 다 살려** 해결(id 교체 후 리액션 생성).

### 검증 / 배포

- 프론트 빌드 통과. 배포된 백엔드 `/reaction`은 아직 **옛 코드(풀 고정문장만 반환)** 확인 → 문맥 리액션 활성화하려면 **Cloud Run 재배포 필요**. 프론트는 feature/jyj(PR #95) Production 반영.

### 다음 할 일

- 백엔드 재배포(`generate_reaction` 활성화) · 첫문장 낭독(F-AV-02)도 Vercel 프록시로 이전 검토 · illustrations 502(Vertex 런타임 SA) 별도 점검

---

## 2026-06-15 (이어서 2 — 혼자 장면 모순·자막 강화·데모 보강)

> **"떠난 인물이 다시 말함" 모순 버그 해결**(4차 시도 끝에 캐릭터 컨텍스트 제거 방식). 작가 리액션 자막 존재감 강화. 데모 시나리오에 문장 추천·검수RAG·엔터테인먼트 비트 추가. Cloud Run 00033→00036.

### 작업 내역

#### 1. "떠난 인물이 다시 말함" 모순 해결 🔥 (4차 시도)

- **증상**: AI가 나레이션에 "박영감 떠남·주인공 혼자"라고 써놓고 dialogue에 박영감 대사를 생성(자기 나레이션과 모순).
- **원인**: 화자검증(L1)은 정상(박영감=등록 인물). 진짜 뿌리는 프롬프트에 **"캐릭터 대사 무조건 생성"** 지시가 3개(`protagonist_rule` "AI는 인물 반응만 생성" / `_build_world_context` "speaker 반드시 명시" / reaction_instruction "대사·행동만"). → 모델이 "혼자"를 무시하고 인물을 재등장시킴.
- **교훈**: 1~3차로 *"떠난 인물 쓰지 마"* 금지 규칙만 추가 → **실패**(무조건 생성 지시가 더 셈).
- **해결(4차)**: 입력에 **혼자/텅 빈/홀로/독백/적막** 감지(`_is_solo`) 시 그 턴만 → ① protagonist_rule을 "인물 등장 금지·나레이션만"으로 뒤집고 ② **[주요 등장인물] 블록 자체를 프롬프트에서 제거**(모델이 볼 인물이 없음) ③ reaction_instruction 끝에 최우선 금지. **새 입력 5/5 나레이션만** 검증.
- 한계: 키워드 휴리스틱(그 단어 없으면 미발동), LLM 캐시는 반복 입력 시 옛 응답.

#### 2. 작가 리액션 자막 존재감 강화

- `.author-reaction-subtitle` 15→**19px**·굵기 700·완전 흰색·그림자 강화(가독성↑).

#### 3. 데모 시나리오 보강

- **💡 문장 추천**(말투 기반) 비트 + **검수 RAG**(설정 모순 — UI 미노출이라 정량근거/스크립트로 시연) + **엔터테인먼트**(리액션·TTS·취향저격) 비트 추가. 시간 제약 완화(7분 넘어도 OK).

#### 4. 교정 오탐 제외

- 문장부호 뒤 공백+따옴표(`다. "이제`)를 띄어쓰기 오탐에서 제외(`_is_punct_quote_fp`).

### 검증 / 배포

- 혼자 장면 5/5 PASS. Cloud Run **00036**. PR #94(누적 9커밋).

### 다음 할 일

- 혼자 장면 키워드 휴리스틱 → **명시적 독백 모드 토글**로 견고화 · 검수 RAG **UI 노출**(백엔드는 violations 계산 중) · 화자 L3(스키마 enum)

---

## 2026-06-15 (이어서 — 멀티워드 화자·정량 측정·발표자료·전체 점검)

> 멀티워드 등장인물 이름 보존 + @멘션 주인공 화자지정 공고히. 정량 측정 스크립트 3종(완료율/TTFB/CER) + 라이브 실측. 발표자료 3종(발표 35분·데모 7분·정량근거 공식 평가표). 서비스 전체 점검(e2e + 코드감사) — 치명 버그 0. Cloud Run 00032.

### 작업 내역

#### 1. 멀티워드 화자 이름 보존

- `_extract_ai_char_names`/`_extract_protagonist_name` 정규식 `[^\s(]+`이 공백서 끊겨 **'편의점 점장'→'편의점', '박 영감'→'박'** 으로 잘리던 것 → ` (`(역할) 또는 `:` 앞까지 전체 캡처. 라이브 검증('편의점 점장' 보존).
- `models/__init__`에 **SavedSentence 등록**(누락 보완 — Illustration 때와 동일). 미등록 시 일부 모델만 import하는 스크립트가 ORM 관계 해석 실패.

#### 2. @멘션 주인공 화자지정 공고히

- 주인공을 @멘션해 **콕 지정**하는 건 유효한 의도라 드롭다운 유지. 단 화자=주인공이면 *"주인공이 아니라 주인공 시점"* 모순 프롬프트가 나가던 것 → **주인공 발화로 분기 처리**(공백 정규화 매칭, "AI가 주인공 대사 새로 지어내지 말 것").

#### 3. 정량 평가 측정 스크립트 + 실측

- `completion_rate.py`(완료율)·`ttfb_eval.py`(TTFB p50/p95)·`cer_eval.py`(CER, Whisper) 신규.
- 라이브 실측: **완료율 65.2%**(30/46), **TTFB p50 8.7s**(스트림이 토큰 스트리밍 아닌 *완성 후 1회 전송* = 전체 응답시간 + Neon 리전 지연 → 개선 계획 문서화).

#### 4. 발표 자료 3종

- **발표자료.md**(35분: 발표 28+시연 7, 가이드 기획서 필수항목 매핑) 신규
- **데모_시나리오.md** 7분 개편(삽화 생성·화자 고정·@멘션 올바른 사용)
- **발표_정량근거.md** 공식 평가표(검문소 방식 G-Eval·CER·TTFB·완료율) + 실측 통합

#### 5. 서비스 전체 점검

- 라이브 e2e: **GET 18종 200**, 완료세션 빈소설 0, 스트림·삽화·교정 정상
- 코드 감사: **치명 버그 0**. 모델등록·마이그레이션 단일head·speaker흐름·빈본문방지 정상. 사소(낮음): @멘션 멀티워드 입력 시 드롭다운 닫힘, 스트림 에러 로그 문구 OpenAI→Vertex 불일치, `formatter.py` 죽은 코드.

### 검증 / 배포

- Cloud Run **00032**(멀티워드 화자). voice-suggest는 이미 dev 머지·라이브 정상 확인. **PR #94**(멀티워드 화자·측정 스크립트·발표자료).

### 다음 할 일

- @멘션 주인공 공고히 배포 · 화자 L3(JSON 스키마 enum) · **Neon 리전 정렬**(TTFB 근본) · CER·MOS 측정으로 평가표 완성

---

## 2026-06-15 (채팅 핫픽스·화자 보강·삽화 엔진 전환·로딩 성능)

> **운영 장애 2건 잡음**: 작가 응답 전면 실패(speaker UnboundLocalError) + 삽화 fal.ai 403. 화자 흔들림 **2겹 방어**(L1 검증+L2 프롬프트) 라이브 검증. 삽화 **Vertex Gemini 2.5 Flash Image** 전환+DB저장. 마이페이지 로딩 진단(병렬화 역효과→쿼리병합+캐시). 읽기 진행률 상단 고정. Cloud Run 다회 재배포(00026→00031).

### 작업 내역

#### 1. 작가 응답 전면 실패 복구 (운영 장애) 🔥

- 채팅 스트림 `generate()` 중첩함수에서 입력화자·응답화자를 **같은 `speaker` 이름**으로 써 클로저 로컬 취급 → 할당 전 참조 **UnboundLocalError**로 **모든 작가 응답이 error 이벤트**. 응답화자를 `reply_speaker`로 분리. 라이브 스트림 실측 복구 확인.

#### 2. 화자 흔들림 방지 — 2겹 (L1+L2)

- **L1 출력화자 검증**(`_resolve_speaker`): AI가 정한 speaker를 등록 인물로 강제 보정(미등록/주인공/공백오타→정규화·빈값). 결정론적 안전망.
- **L2 프롬프트 화자 고정 규칙**: speaker는 등록 인물 enum 내에서만, **새 인물 임의 등장 금지**(필요시 narration만).
- 검증: 단위 7케이스 + **라이브 적대적 입력 3종**(낯선손님 유도·주인공 독백 등) 전부 PASS.

#### 3. 삽화 — fal.ai → Vertex Gemini 2.5 Flash Image

- fal.ai(유료·IP차단·**403 Forbidden**) 대신 **Vertex Gemini 2.5 Flash Image**(ADC·GCP크레딧, IP차단無). `Illustration` 모델·마이그레이션(`k1l2m3n4o5p6`)으로 세션별 삽화 **DB 영속 저장**. 라이브 생성·저장·조회 검증.
- **저장 중 표시**: 2.5MB base64 업로드 지연 동안 버튼 '삽화 저장 중…'+비활성화.

#### 4. 마이페이지('내 서재') 로딩 성능

- 진단: dashboard **6.9s**(쿼리 6~7개 순차) + **Neon 쿼리당 ~2s floor**(Cloud Run us-central1 ↔ Neon **ap-southeast-1**, 지구 반대편).
- **병렬화(독립 세션) 시도 → 8.7s로 역효과**(Neon 커넥션 establish 경합) → 롤백. **단일 세션+Novel 2쿼리→1쿼리 병합 → ~3s**. 프론트 dashboard/stats **캐시**(재방문 즉시).

#### 5. 읽기 진행률 상단 고정 + 배포 안전성

- 읽기 진행률이 스크롤 시 사라지던 것: `index.css`의 `overflow-x:hidden`이 **sticky 헤더를 깨뜨림** → 진행률을 `position:fixed`로 분리해 뷰포트 최상단 고정(라벨은 추후 제거, 바만 유지).
- **배포 명령에 `FAL_KEY` 누락 발견** → `--set-secrets` 전체교체 특성상 삽화 키 삭제 위험. 표준 명령에 `FAL_KEY=FAL_KEY:latest` 영구 추가(server-ops·메모리 기록).

### 검증 / 배포

- Cloud Run 재배포 00026→**00031**. 라이브 실측: 작가응답·삽화생성·화자검증·dashboard(~3s) 정상.
- **PR #88이 채팅 핫픽스 직전 커밋에서 머지돼 dev에 핫픽스 누락** 발견 → **PR #90**으로 반영(코멘트로 머지 우선 명시).

### 다음 할 일

- **PR #90 머지** → dev/main 동기화(채팅 핫픽스 포함). 머지 후 Vercel production 반영
- **화자 보강 L3**(JSON 스키마 enum 강제) — 발표 후 더 단단히
- **Neon 리전 정렬**(us 리전 이전 or pooled 엔드포인트) — 쿼리당 ~2s floor 근본 해결
- @멘션 드롭다운에서 **주인공 제외** + 단팥빵 스크립트 정정(낯선손님 충돌·@멘션 오용 제거)

---

## 2026-06-14 (이어서 — 소설변환 버그·교정 톤·능동추천·정리)

> 채팅 종료 후 **'읽기' 빈 화면** 버그 진단·수정·복구 → 읽기 단편 장 구분 → 교정 메모 **조롱 금지 가드** → **오답노트 능동 경고**(반응형→예측형 1단계) + **삭제 기능** → 발표 데모 시나리오 + 죽은 파일 정리. 백엔드 Cloud Run 4회 재배포(리비전 00018→00021).

### 작업 내역

#### 1. 소설 빈 본문 버그 — 진단·수정·복구

- **증상**: 채팅 종료 후 '읽기'가 아무것도 안 뜸. 원인 = ① 한 소설(`황궁의 붉은 장미`) `content`가 **0자**, ② `generate`가 빈 소설을 그대로 반환해 **영구 고정**, ③ `handleEnd`가 `generateNovel` 실패를 `catch{}`로 **조용히 삼킴**
- **수정**: 백엔드 generate **빈 본문 저장 방지**(strip 후 비면 대화로그 폴백) + **빈 소설이면 재생성 덮어쓰기**, read **빈 본문 안내 + 「다시 변환」 버튼**, 채팅 종료 실패 시 **토스트** 안내
- **복구**: 황궁 빈 소설 재생성(0→183자), 완료 세션 8개 전부 본문 정상 확인

#### 2. 읽기 페이지 — 단편 장 구분

- 단락 5개 이하(장 1개뿐)면 `제 1장` 헤더·목차 **숨기고 본문만** — 단편이 대부분이라 "제1장"만 덩그러니 뜨던 어색함 제거

#### 3. 교정 메모 — 사용자 조롱 금지 가드

- 백야 교정 메모가 *"숨바꼭질이라도 하나?"* 처럼 **사용자를 놀림** → 백야 톤 `시니컬→건조` 완화 + **전 작가 공통 '조롱·비아냥·면박 금지' 하드 가드** 추가(글자 코멘트일 뿐 사람 평가 아님)

#### 4. 능동 추천 1단계 — 오답노트 능동 경고 (반응형→예측형)

- AI/RAG 차별점 분석 후 *"데이터(취향·오답)는 이미 쌓이는데 소비 레이어가 없다"* 판단 → 착수
- `GET /chats/{id}/error-warmup`(2회 이상 틀린 것 상위 N, **LLM 미사용**) + 채팅 진입 시 **카드**(하루 1회·닫으면 그날 안 뜸). 글쓰기 **전에** 자주 틀리는 것 미리 제시

#### 5. 오답노트 삭제

- `DELETE /users/{id}/error-notebook`(서비스 `remove_entry`) + 마이페이지 항목별 **✕ 버튼**

#### 6. 잡정리

- 마이페이지 '내 소설 목록' 버튼 **이모지 제거**·✕ 정렬 보정, **죽은 파일 삭제**(write 스텁·neonStub 4개, 참조 0 확인)

#### 7. 문서

- **`데모_시나리오.md` 신규**(발표 5분 시연 — 타임라인·멘트·촬영 체크리스트·NG컷), 사용자_시나리오 **8) 교정 섹션**·기능정의서 **F-QC-02** 갱신

### 검증 / 배포

- 백엔드 Cloud Run **재배포 리비전 00018→00021**, `error-warmup`·`DELETE`·소설 재생성 **라이브 검증**(실데이터). 프론트 `npm run build` 반복 통과

### 다음 할 일

- **Vercel Production Branch 확인** — dev 머지분이 라이브에 안 뜨는 이슈. main(6/1 옛 스캐폴드) 아니라 `dev` 추적인지 점검(아니면 dev→main)
- **능동 추천 2단계** — 취향 기반 **세계관 씨앗 추천**(쿠팡식 예측형)
- **교정 누적 기준 강화** — 현재 `session.user_id`(세션 소유자) 누적 → 로그인 유저 누적으로 변경 검토(공유 세션 혼선 방지)

---

## 2026-06-14

> 사용자 흐름 **매끄러움 폴리시** — alert 13곳을 토스트로, 로딩 배경 핑크 제거, 메인 프로필 즉시표시(병렬+캐시). 메인 작가선택 사이드바 프로필 카드, 라이트 테마 카드 색, 탭 메타(lang/title/favicon) 정비.

### 작업 내역

#### 1. 사용자 흐름 점검 후 UX 폴리시

- **alert() 13곳 → 공용 토스트**(`lib/toast.jsx`+`toast.css`, App 루트 `<ToastHost/>`) — 논블로킹·라우팅 넘어가도 유지. 검증/안내=중립, 실패=빨강. (main 로그인 유도·worldview 검증·chat 세션·storylist 삭제)
- **'잠시만요' 로딩 영상 배경 핑크 제거** — `loadingVideo.jsx` 오버레이가 `rgba(255,255,255,0.8)`(반투명)이라 뒤 페이지(마이페이지)의 **직전 작가 테마색**(한여름=핑크)이 비치던 것 → `#f4f3f7` 불투명으로 차단
- **메인 프로필 즉시 표시** — 카드 조회가 `await syncCurrentUser()` 뒤에 직렬로 걸려 늦게 뜨던 것 → ① 동기화와 **병렬화** ② **localStorage 캐시**(stale-while-revalidate)로 재방문 0초 표시 후 백그라운드 갱신

#### 2. 메인 작가선택 사이드바 — 프로필 카드

- 마이페이지 미니 프로필과 같은 톤으로 **아바타 이니셜·닉네임·작품수** 카드를 사이드바 맨 위에 + 아래 구분선. `getProfile(userId)` 연동, 로그인 시에만 표시

#### 3. 테마·메타 정비

- **라이트 테마(한여름·김도현) 작가 카드** — 흰색(`--card-main`)으로 뜨던 것 → `color-mix(테마색 14%)` 틴트 + 테마 테두리(다크 테마는 유지)
- **탭 메타** — `index.html` `lang="en"→"ko"`(Edge "영어 번역할까요?" 팝업 제거)·`<title> frontend→NodeVelture`·favicon을 서비스 로고(`/assets/logo.png`)로

#### 4. 마이페이지 레이아웃 (이어서)

- **오답노트 탭** 추가(error_profile 상위 10 + 가장많이틀린순/최신순 토글) · 사이드바 260px·메인 폭·왼쪽 여백 조정

### 검증

- 프론트 `npm run build` 반복 통과 · alert 0곳 확인 · 클라우드 백엔드 e2e 전체 200(오답노트 엔드포인트 포함)

### 다음 할 일

- **Vercel 로그인 마무리(P0)** — Neon Auth 허용 도메인에 `*.vercel.app` 등록(미등록 시 세션 안 잡혀 user_id 불일치 → 소설 목록 빈 채). 건혁님과
- **로딩/빈상태 문구·톤 통일** — "불러오는 중"/"…중입니다"/"없습니다"vs"없어요" 혼재 정리(UX 점검 잔여)
- **TTS 클라우드 결정** — ElevenLabs 무료플랜 IP 차단(401) → 유료 전환 or 로컬 시연 확정
- **발표 정량 근거(F-EV-06)** — GPT·긴 시나리오·다회 평균으로 신뢰값
- **비식별화(PII 마스킹)** — RAG 적재 전 마스킹(평가 요구)

---

## 2026-06-13

> 오탈자 교정 **고유명사 보호** 고도화 + 마이페이지 **오답노트** + **Vercel 배포 대응**(apiBase 절대URL) + @등장인물 멘션. 클라우드 **마이그레이션 incident** 추적·복구. PR #83 생성.

### 작업 내역

#### 1. 오탈자 교정 — 창작 고유명사 보호 (proofread)

- **등장인물 이름·세계관 제목을 맞춤법 교정에서 제외** — 일반 맞춤법기가 "카이렌의→카이 레인의"처럼 창작 명사를 쪼개던 것. 세션의 등장인물·세계관에서 보호어 집합 구성, 조사 붙어도 부분문자열로 매칭
- **하이브리드 세계관 용어집** — 세계관 자유서술에서 **LLM 1회 자동추출**(캐시) + **'넘기기' 누적**(영구 허용) + 수동삭제 escape. `world.glossary` 컬럼·마이그레이션(`j0k1l2m3n4o5`), GET/POST/DELETE 엔드포인트, chat·editor 넘기기 배선
- **자모(ㅋㅋ·ㅠㅠ)·늘임(좋아아아) 무시** — 감정 표현이라 오타 아님 → 항상 제외
- **`checker_ok` 가드** — 네이버 검사기가 못 돌면(차단/변경) '조용히 검사 안 됨'을 호출부가 알게 status 반환

#### 2. 마이페이지 오답노트 탭

- `error_profile`(자주 틀린 맞춤법 누적)을 **상위 10개** + **가장 많이 틀린 순 / 최신순** 토글로. 최신순 위해 error_profile에 `last`(마지막 틀린 시각) 기록

#### 3. @등장인물 멘션 (F-CH-18)

- 입력창 `@` → 등장인물 드롭다운·태그 칩 → 그 **인물 대사로 전송**. `stream?speaker=` + `build_messages` 화자 지시 → 작가AI가 **그 인물 시점·서사로 전개**, 말풍선 이름도 인물로

#### 4. 배포 / API (Vercel 대응)

- **`apiBase` 상대경로(`/api/v1`) → 절대 URL 전환** — 코드가 `/api/v1` 하드코딩이라 dev 프록시에서만 동작, **Vercel 배포본에선 자기 도메인 호출 → 전부 실패**(작가목록·로그인·소설목록)였음. 배포(PROD)에선 `VITE_API_BASE_URL`로 백엔드 직접 호출, SSE도 직결

#### 5. UI

- **작가 테마 적용 수정** — 소설읽기 진입 시 목록에서 `authorId` 전달 + read state 우선(직전 작가 색 깜빡임 제거)
- **chat/editor 작가 패널 너비 vw 비율화** — 고정 px라 창 줄이면 왼쪽이 찌부러지던 것 → vw 비율로 **창 축소 시 좌우 비율 유지**

#### 6. 클라우드 e2e + 마이그레이션 incident 복구

- 라이브 리비전 00016이 `World.glossary` **모델 코드는 배포됐는데 마이그레이션 미적용** → worlds 테이블 조회가 전부 500(`SELECT ... worlds.glossary` asyncpg 에러) = **sessions·mypage·채팅·proofread 핵심 마비**. 로그로 컬럼 누락 확정 → `alembic upgrade head`로 복구 후 **전체 e2e 200 재확인**

#### 7. 문서 · PR

- **업무분담·기능정의서 현행화**(Cloud Run·Vercel·교정·@멘션·TTS 반영, 업무분담 중복 정리)
- **PR #83**(feature/jyj → dev, 13커밋) 생성 — 리뷰/배포 주의(마이그레이션·재배포·TTS) 본문에 정리

### 이슈

- **TTS 클라우드 무음** — ElevenLabs **무료플랜이 클라우드/데이터센터 IP를 차단**(401). 로컬(가정 IP) 200 / Cloud Run 401로 확정. 백야 음성을 v1(`XTqHG…`)+동완님 키(KEY_1)로 매핑 수정(로컬 200 검증). 클라우드 음성은 **유료 전환 or 로컬 시연** 필요
- **Vercel 로그인 user_id 불일치** — 데이터는 `jyj@asd.asd`(11~12 소설) 아래 정상. Neon Auth에 vercel.app 도메인 미등록 시 세션이 안 잡혀 다른/빈 user_id로 조회 → 빈 목록

### 검증

- 클라우드 e2e 전체 통과(health·authors·sessions·mypage·**proofread·glossary·오답노트·stream**) · proofread 보호어/자모·늘임 필터 단위 테스트 · 프론트 빌드 반복 통과

---

## 2026-06-12

> 시연 안정화 — Cloud Run 배포본에서 **작가 AI 응답이 안 나오던 장애를 로그로 끝까지 추적·복구**(원인 2종: memos Redis 타입 충돌 · Vertex SDK 인자 비호환). 채팅 타자기 효과·소설 읽기 무한로딩 등 체감/안정성 폴리시, 기능정의서·README 문서 현행화.

### 작업 내역

#### 1. Cloud Run "작가 답변 안 옴" 장애 디버깅·복구 (오늘 가장 큰 건)

배포는 성공하는데 채팅 응답이 안 와서, `gcloud run services logs read`로 실제 트레이스백을 까서 원인 2개를 잡음.

- **(주범1) memos Redis 키 타입 충돌(WRONGTYPE)** — `session:{id}:memos`를 `save_memos`(PUT)는 `SET`(문자열 JSON), `get_context`·`list_memos`는 `LRANGE`(리스트)로 접근 → 메모를 한 번 저장한 세션은 이후 `lrange`가 `WRONGTYPE` 500. **채팅도 매 메시지 `get_context`가 같은 lrange를 타서 AI 응답까지 통째로 죽던 것.** → `_read_memos()`(키 타입 보고 list/string 분기) 도입, `get_context`·`list_memos` 교체 + 프롬프트 렌더가 dict 메모(`m['text']`)도 처리
- **(주범2) Vertex SDK가 `request_options` 인자를 안 받음** — `llm._gen_once`가 `generate_content(..., request_options={"timeout":40})` 호출. `request_options`는 **google-generativeai(AI Studio) 전용** → `vertexai`는 거부 → 두 모델 다 실패 + 폴백 없음(`LLM_PROVIDER_CHAIN` 미설정 → gemini 단독)으로 무응답. **인증/SA 문제 아님(Vertex 연결은 정상).** 로컬은 vertexai 버전이 받아줘 통과한 **버전 드리프트** → `USE_VERTEX`면 `request_options` 미전달로 수정
- **F-AS-05 `reactions` import 복구** — 머지 때 chats.py import 블록이 origin/dev 걸로 덮이며 `from app.core.reactions import EMOTIONS, pick_reaction`가 증발 → `/reaction` 호출 시 NameError. import 복구
- 각 수정 후 **Cloud Run 재배포**(`backend/`에서 `--source .` = Dockerfile 빌드, env/시크릿 보존) → 로그로 응답 복구 확인. (배포 함정: `.env`는 이미지에 안 올라감·루트에서 배포하면 Buildpacks로 실패·Vertex는 런타임 SA로 인증 — `server-ops.md`에 정리)

#### 2. 채팅 응답 타자기(typewriter) 효과

- 백엔드가 응답을 통째로(구조화 JSON) 보내 토큰 스트리밍이 어려우므로 **프론트에서 받은 텍스트를 한 글자씩 노출**(`TypedText`/`CharMessage`) — 나레이션 타이핑 → 끝나면 대사 타이핑, 타이핑 중 자동 스크롤 추종. **복원된 과거 대화는 즉시 표시**(재타이핑 X). "한 번에 뜨는 팝" 제거로 체감 개선, 속도는 기본값으로 조절

#### 3. 말풍선 줄바꿈 · 소설 읽기 무한로딩 수정

- **말풍선 한글이 글자 단위로 세로 쪼개지던 버그** — `.bubble`·`.narration-text`에 `word-break: keep-all` + `overflow-wrap: anywhere` + `width: fit-content`로 **어절 단위** 줄바꿈. 깨진 CSS 주석(`\*`)도 정리
- **소설 읽기 무한 로딩 수정** — 읽기 페이지가 작가별 `loading.mp4`가 끝나야(`onEnded`) 본문을 보이는데, 작가 1·2·4엔 파일이 없어 404 → `onEnded` 미발화 → 무한 로딩. `<video>`에 **`onError` + 6초 안전 타임아웃 폴백** 추가로 어느 작가든 멈추지 않게(+ 로딩 작가 id 기본값 보정)

#### 4. 프론트 기동 복구 + Vertex 로컬 인증

- **`@neondatabase/neon-js` 미설치로 프론트 먹통** — 머지로 추가된 로그인 의존성이 node_modules에 부분 손상(우산 패키지만 누락). `node_modules` 삭제 후 **클린 재설치**로 복구(서브경로 `auth/react`·`ui/css` 확인)
- **Vertex 로컬 ADC 재인증** — `gcloud auth application-default login` + `set-quota-project`로 로컬에서도 Groq 폴백 없이 Gemini 사용

#### 5. 문서 현행화

- **기능정의서 전면 동기화** — 엔진 표기 Groq→**Vertex**, 완료분 상태 갱신(F-WD-06·F-CH-09·F-CH-10·F-AS-05·F-QC-02·F-NV-07·F-SY-11 등 ✅), 신규 **F-PR-03/04**(개인화·관심사 추천 RAG, **비식별화=키워드만**) 추가, §4 업무분담은 중복 스냅샷 제거 후 `업무분담.md` 포인터로 분리, §5 잔여/차별점·비식별화(평가 요구) 명시
- **README 전면 재작성** — 옛 기획안(CoAuthor·PERSO·파인튜닝·Render)을 **실제 구현**(Vertex·Neon·Upstash·RAG 3종·React/Vite·Cloud Run)으로 교체. 차별점 3축·작가 4인·아키텍처·로컬 실행·구조·팀
- **server-ops.md** — 06-12 Cloud Run 장애(원인 2종 + 배포 함정) 기록

#### 6. TTS 진단 (F-AV-02, 동완 기능)

- ElevenLabs TTS 무음 원인 진단 — `backend/.env`에 `ELEVENLABS_API_KEY_1/_2`가 없음(키 없으면 `synthesize`가 빈 음성 반환 → `event:audio` 미전송 → 무음). 키 추가 위치·작가별 매핑(`_1`/`_2`)·voice ID 계정 확인 가이드

#### 7. (설계) 리액션 영상 자막 매핑

- 작가 리액션 영상에 영상 대사와 맞는 자막을 **영상→자막 하드코딩 맵**으로 붙이는 방향 설계 — `/reaction` API 텍스트 대신 영상 매칭 자막으로 교체하는 구조(영상 목록·트리거 확정 대기)

### 검증

- Cloud Run 로그로 작가 응답 복구 확인 · 프론트 빌드/기동 정상 · `chats.py`·`llm.py` 문법 검사 OK

---

## 2026-06-11

> 시연일 — 팀 PR 5건 머지·마이그레이션 정리로 dev 안정화, Cloud Run **공개 배포 게이트 해제**, 데모용 우회·아바타 협업 UI, F-AS-05 리액션 자막을 dev/배포본까지 연결, 채팅 페이지 UI 전면 폴리시.

### 작업 내역

#### 1. 팀 PR 리뷰·머지 (팀장)

- **#64**(pge 마이페이지 대시보드·집필 연동) · **#65**(ygh 사용자정보 연동·`is_admin`) · **#66**(pge 작가 AI 히스토리 작가별 분리·토큰 최적화) · **#67**(ygy TTS `event:audio` 분리·F-VM voice) · **#68**(ygh 소설 읽기 UX·메인 UI) 리뷰·머지
- 머지 워크플로(전원 1승인) 유지

#### 2. 마이그레이션 정리 (배포 안정화)

- **#65 `is_admin` 컬럼 마이그레이션 누락 보완**(`e5f6a7b8c9d0`) — 모델엔 추가됐는데 마이그레이션이 없어 `select(User)` 크래시 위험 → 추가
- **#66 mypage 마이그레이션 `down_revision` 수정**(`c3d4e5f6a7b8` → `e5f6a7b8c9d0`) — multiple-head 방지
- 배포 전 **운영 Neon DB head 일치 확인**(`current == heads == f1a2b3c4d5e6`, single head) → 재배포 시 마이그레이션 불필요 확정

#### 3. Cloud Run 공개 배포 게이트 해제

- 조직 DRS(`iam.allowedPolicyMemberDomains`)가 `allUsers` 차단해 `--allow-unauthenticated` 실패 → 프로젝트 오버라이드(allowAll)·~15분 전파 후 `run.invoker` 부여, **익명 `GET /health` 200 확인**
- **로그인 의존성(`@neondatabase/neon-js`) 미설치 시 빈 스텁으로 우회**(vite alias) — 앱 기동 보장(패키지 설치되면 자동 복구)

#### 4. F-AS-05 작가 리액션 — 백엔드 복구 + 프론트 자막 완성 (#70)

- **`POST /chats/{id}/reaction` dev 복구** — #64/#66의 `chats.py` 재작성(chat_context 분리) 때 누락돼 `reactions.py`가 死코드였던 것. 감정분류(LLM closed-set) + 작가 톤 풀 추출 구조 그대로 복구 → dev/배포본에서도 자막 동작 (별도 PR #69는 #70로 통합·닫음)
- **프론트 자막** — 작가 사진 위 **영화 자막 스타일**(흰 글씨+그림자). 대사 입력 시 `/reaction` 호출해 표시, 접두사 '- ', 15초 노출, 페이드인(상하 이동 없음), `text-wrap: balance`로 줄바꿈 정돈
- **폰트** — 마루부리(네이버 무료 상업용 바탕체) 로컬 `@font-face`(오프라인 동작)

#### 5. 채팅 아바타 협업 UI + 체감 개선

- **작가 아바타 협업 UI** — 생각중 표시·기억 소환·일관성 지적·메모 받아적기
- **'작가가 쓰는 중' 즉시 표시** — 전송 직후 바로 띄워 스트리밍 체감 지연 제거

#### 6. 채팅 페이지 UI 폴리시

- **버튼 확대**(집필형·채팅 종료·전송) · **IME 엔터 버그 수정**(한글 조합 중 Enter 전송 시 글자 중복/줄바꿈 → `isComposing` 가드, 입력칸 전체)
- **피드백 시 원문(사용자 채팅) 숨김** — 피드백 프롬프트가 패널에 그대로 노출되던 것 제거(작가 AI 답변만 표시)
- **작가 답변 좌우 여백** 확보

#### 7. 작가 패널(우측) — 토글 버그·리사이즈·영상 자리

- **토글 버튼 먹통 수정** — `main.css` ↔ `chat/ui.css`가 `.author-panel-slide`/`.author-panel`를 전역 중복 정의, main의 `flex:0 0 400px`가 채팅의 `width:0`을 덮어써 패널이 안 닫히던 것. 채팅 규칙을 `.chat-layout`으로 스코프해 충돌 차단
- **마우스 드래그 리사이즈** — 패널 왼쪽 핸들로 너비 조절(320~760px), 안쪽 콘텐츠 자동 reflow
- **사진/영상 영역 16:9** — 건혁님 1920×1080 영상 대비 `aspect-ratio: 16/9` + `<video>` 선제 스타일, `object-fit: contain`(전체 표시)

#### 8. 메인·소설목록 정리

- 메인: **로그아웃 버튼을 우측 패널 하단**으로 이동, "작가를 선택하세요" 문구 제거
- 소설목록: **마이페이지(내 서재) 이동 버튼** 추가

#### 9. 배포 운영

- **로컬 데모 환경** — venv 동기화(누락된 google 패키지) · `.env` localhost 전환 · Vertex ADC 확인 → 로컬 백엔드 `/reaction` 실동작 검증(200, 작가 톤 반응)
- 데모 후 **서버 cloud 복귀**(`.env`) + **재배포 절차 정리**(`--source` 빌드, 기존 시크릿 보존 위해 `--set-secrets` 미사용, 마이그레이션 불필요 확인)

#### 10. 문서

- **업무분담** — 분담 기준 **기능 단위 책임제**로 전환 / F-VM(가연 로그인·말투 팝업)·마이페이지(가은)·F-PR-03(개인화는 코치층만)·관심사 추천 RAG(가은)·오탈자 메모태그(윤정) 추가, storylist 중복·개인화 경계 명시
- **스크럼** — 06-11 강사 스크럼·17:30 회의 반영

#### 11. UI 폴리시 추가 (#71 머지 이후)

- **작가 패널 기본 너비 최대(760px)** — 진입 시 패널이 넓게 열리도록 기본값을 리사이즈 상한(760px)으로 설정
- **소설 읽기 로딩 화면** — 영상 테마 배경 적용 + 로딩 표시 중앙 정렬
- **로그인 버튼 위치 통일** — 헤더의 로그인 버튼 제거, 로그아웃과 동일하게 **작가 패널 하단**으로 이동(로그인/로그아웃 위치 일관성)

### 검증

- 프론트 `npm run build` 통과(반복 확인) · 백엔드 `/reaction` 200 OK(감정분류 + 작가 톤 풀 추출) · 익명 `/health` 200 · alembic `current == heads`(single head)

---

## 2026-06-10

> Vertex AI 전환으로 **속도(8s→2s)·언어누수 동시 해결** + 데모 안정화. 작가 리액션(F-AS-05) 구현, 개인화 경계 설계 확정, 팀 PR 6건 리뷰·머지·충돌 해결.

### 작업 내역

#### 1. LLM 엔진 Vertex AI 전환 (#58 — 가장 큰 건)

- **Vertex AI(ADC) 지원** — `USE_VERTEX=true` 시 Gemini 2.5 Flash + 임베딩을 Vertex로(`services/llm.py`). `USE_VERTEX=false`면 기존 폴백(Groq/Gemini) **그대로**(하위호환)
- **응답 8s→2s** — Gemini thinking off + flash-lite
- **언어누수 해결** — Groq Llama 한자/일본어 산발 → Vertex Gemini로 **한국어 깨끗**(E2E 소설 출력 검증, `私の` 사라짐)
- 신규 GCP 프로젝트라 Vertex는 **gemini-2.5 계열만** 가용(2.0/1.5/3.x 404). ADC(`gcloud auth application-default login`)·키 형식·모델·Redis 이슈 → `server-ops.md` 기록
- **`persona_eval.py`** — 작가 4명 블라인드 분류 정확도·stylometry 정량 평가(강사님 "분류 모델 돌려봐라" 대응)

#### 2. 문체 RAG 복구 + 채팅 회귀 수정 (#58)

- 머지로 빠졌던 **`novels.py` `use_style` 문체 RAG 연결 복구**
- `chats.py` `get_author_prompt` import 복구 — **채팅 크래시 회귀** 수정

#### 3. 프론트 — 작가 테마 새로고침 유지 (#58)

- `useAuthorTheme` 훅 + 전 페이지(chat·chatlist·intro·read·worldview) 적용. chat/read는 `session.author_id` 기준

#### 4. F-AS-05 작가 리액션 (신규)

- `core/reactions.py` — 작가별 × 감정 6종(tension·fear·sadness·joy·calm·resolve) 리액션 풀 + `pick_reaction`(작가/감정 폴백·직전 리액션 회피)
- `chats.py` — `classify_emotion`(LLM closed-set JSON) + `POST /{id}/reaction`. **LLM은 감정만 분류, 문장은 작가 톤 풀에서 추출** → 작가 문체 100% 보장 + 빠르고 저렴
- 문장 내용 확장은 동완(F-CH-16) 담당

#### 5. 배포 — Cloud Run 구성

- `Dockerfile` + `.dockerignore` + `server-ops.md` 배포 기록

#### 6. 기획·설계 결정

- **개인화 경계 확정** — 개인화는 **코치/추천 층에만**, 소설 출력 문체엔 개인 정체성(MBTI·말투) **주입 금지**(문체는 작가 페르소나가 책임). 강사님 "personal 반영"을 *창작 취향*으로 해석 → F-PR-03로 정리
- 06-10 아침 스크럼·14:00 강사님 스크럼·중간점검 체크리스트 반영, 팀 회의(15:00) **채팅 페이지 고도화 분담**, F-AV-04(감정→아바타 자막) 동기화

#### 7. 팀 PR 리뷰·머지·충돌 해결

- **#53**(모델 가중치 840MB 재유입 정리 — #31 regression 차단) · **#57**(ygy personas 충돌 union 해결) · #56·#58·#59·#60 리뷰·머지 조율
- 마이그레이션 **multiple-head 점검**(#43·#60 단일 head 확인), import/컨트랙트 정합 검증

### 검증

- **E2E 스모크 9/9** (Neon + Upstash + **Vertex**) — author_id 저장·스트리밍(`reply`)·소설 변환까지 전 체인, 소설 한국어 깨끗
- 작가 리액션 `pick_reaction` 동작 확인(작가/감정별 출력)

---

## 2026-06-09

> 강사님 피드백("LLM 활용이 핵심" → 16:00 "RAG 없으면 차별점 없다") 대응에 집중한 날.
> 멀티엔진 LLM 파이프라인 → RAG 3종(기억·검수·문체) → 백엔드 백로그 일괄 → Neon 전환까지.

### 작업 내역

#### 1. LLM 멀티엔진 파이프라인 (오전 — 가장 큰 건)

- **Groq 엔진 추가 + 엔진 토글** — `LLM_PROVIDER`로 Groq↔Gemini 전환, 모델/키 폴백 추상화(`services/llm.py`). Gemini 무료 한도 소진 문제를 Groq(넉넉한 무료)로 우회
- **정교한 분기 파이프라인** — 프로바이더 체인 · n키 순환 · 429(쿼터) 분기 · 인증/일시오류 분류 · 쿨다운 · 지수 백오프. "팀 핵심이 LLM 성능"이라는 요구에 대응
- **OpenAI(GPT) 프로바이더 추가 + 크로스 프로바이더 폴백** — `.env` 한 줄로 Groq↔Gemini↔GPT 전환. `.env.example` 팀 가이드 정비
- **author_id → 작가 persona 문체 연동** — 세션의 `author_id`(1~4)를 persona로 매핑해 소설 변환을 작가 문체로(`novels.py`), Gemini 모델명도 `.env` 설정화

#### 2. RAG 3종 구축 (핵심 차별점 — "ChatGPT와 뭐가 다르냐"의 답)

- **세계관 일관성 RAG (F-CH-10)** — 강사님 16:00 "RAG 없으면 차별점 없다"에 정면 대응
  - 누적 요약: `services/memory.py` — N턴마다 이전 요약+최근 대화만 증분 요약해 `story_summary`에 누적(토큰 절약)
  - 세계관·등장인물 주입: `chats.py _build_world_context` — 세션→세계관·캐릭터·줄거리를 프롬프트에 자동 주입
  - **의미 검색**: `llm.embed`(Gemini `gemini-embedding-001`) + `memory.retrieve_relevant`(코사인 top-K) — 오래된 대화를 검색해 보강. **6턴 전 비밀("민준=잠입 형사")을 정확히 회상** 검증
- **설정 일관성 검수 (F-QC-01)** — `services/consistency.py`. 확립된 설정·기억과 새 응답을 LLM(JSON 모드)으로 대조해 모순 탐지. **형사↔의사 모순 탐지 / 정상 통과** 검증
- **문체 RAG (F-NV-08)** — `services/style.py` + `data/style_samples.json`(작가당 12개). 장면과 가까운 작가 문체 예시를 few-shot으로 주입. `use_style` 토글 + 3회 평균 채점 시 **ON > OFF(+1.0점)** 검증

#### 3. 채팅 응답 안정화 (가은님 구조화 버전 #49 머지 대응)

- `event:token` 스트리밍 → **narration/dialogue JSON 구조화**로 정합. `llm.generate(json_mode=True)`로 **유효 JSON 강제**(Groq `response_format` / Gemini `response_mime_type`)
- `parse_ai_response` 견고화 — 깨진 JSON·`null` 값 폴백 처리(슬라이싱 크래시 수정)
- **출력 한국어 강제** 프롬프트 추가 (Groq Llama 한자/일본어 누수 완화)

#### 4. 백엔드 기능 (jyj 백로그 일괄)

- **F-CH-11** 작가 메모 백엔드 — `POST /chats/{id}/memo` → 프롬프트 `[작가 메모]` 주입 (+ 조회/삭제)
- **F-AS-01/03** 어시스턴트 — `GET /chats/{id}/suggest` 다음 전개·막힘 도움 3개 제안
- **F-SY-09** 토큰 분석 — `/api-logs`에 `by-model`·`session/{id}` 집계 추가(기존 summary·total + 세션·모델별 완성)
- **F-SY-10** 토큰 절약 — 프롬프트 verbatim 대화를 최근 10턴으로 제한(그 이전은 요약+RAG가 커버)
- **F-EV-06** 근거 리포트 측정 — `services/evaluate.py`(LLM-judge 4축 채점) + `scripts/evidence_report.py`(맨손 vs 우리)

#### 5. 프론트엔드 (테마·메모 패널)

- **작가별 테마 전 화면 적용** — 채팅(`chat/ui.css`)·소설 목록(`chatlist.css`)·소설 읽기(`read.css`)를 `data-author` + CSS 변수(`--theme-color`/`--bg-main`/`--text-main` 등 + `color-mix`)로 통일. 라이트/다크 자동, 글자 가독성 확보
- **채팅 메모 패널 재배치/확대** — 세계관 요약·등장인물을 위로, 작가 메모를 아래로. 폭 340px, 입력창 높이를 채팅 입력과 정렬
- `chatlist.jsx` 중복 `handleRead` 함수 제거(Vite 파스 에러 수정)

#### 6. 시연 · 문서

- 시연 데모 3종: `scripts/rag_demo.py`(기억) · `consistency_demo.py`(검수) · `style_demo.py`(문체 off/on 평균)
- **`docs/rag/성능지표.md`** — RAG 3종 켰을 때/껐을 때 실측 결과 (발표 근거)
- **`docs/scrum/`** — 6/9 팀 스크럼 정리 + **16:00 강사님 피드백**(RAG 필수·어시스턴트·토큰 분석) 기록
- **기획 문서 현행화** — `PROJECT_STATUS.md`·`기능정의서.md`/`.html`(Groq엔진·소설변환/읽기·author_id 완료 반영), **`업무분담.md` 신설/분리**(팀 공유용)
- **서비스 방향 확정**: "진지한 창작 도구(척추) + 엔터테인먼트(껍데기)", 다리 = "캐릭터랑 놀듯 대화 → 진짜 내 소설"
- 어제치 **`2026-06-08` 개발일지** 작성

#### 7. 인프라

- **Neon 클라우드 DB 전환**(가연님 셋업) — `.env` `DATABASE_URL`을 Neon으로(로컬은 주석 보존). `database.py _prepare_db_url`이 `postgresql://...?sslmode=require` → **asyncpg + SSL 자동 변환**
- `psycopg2-binary` 설치 (alembic 마이그레이션 sync 경로용)

### 이슈

- **Groq Llama 언어 누수** — 한자·일본어가 산발적으로 섞임. 프롬프트로 빈도는 줄지만 박멸 안 됨 → **GPT 전환이 근본 해결**(엔진은 `.env` 한 줄로 전환 가능)
- **F-EV-06 단일 회차 노이즈** — 다회 평균 필요. 짧은 시나리오는 RAG '기억' 강점이 안 드러나 맨손과 비슷하게 나옴 → 긴 시나리오+GPT 필요
- **requirements.txt psycopg2 미반영** — 가연님 dev 브랜치엔 있으나 feature/jyj엔 아직 → pull 필요
- **Neon 라이브 검증 대기** — `e2e_smoke`로 직접 확인 예정(공용 DB라 마이그레이션은 가연님 영역)

### 다음 할 일

- GPT vs Gemini 엔진 결정(가은님 비교) → 언어 누수·품질 개선
- 프론트 연결: 메모 패널·제안 버튼(가은님), 토큰 대시보드 화면(건혁님)
- Neon e2e 검증 + 필요 시 마이그레이션(가연님)
- 근거 리포트를 GPT·긴 시나리오·다회 평균으로 신뢰값 산출

---

## 2026-06-08

### 작업 내역

#### 인프라 / DB 트러블슈팅 (가장 큰 건)

- **DB 커넥션 간헐 끊김(`ConnectionResetError`/`ConnectionDoesNotExistError`) 원인 규명** — Windows 네이티브 **PostgreSQL 17**이 5432를 도커 컨테이너와 **동시 점유** → 연결이 오락가락 리셋되던 것
  - 해결: 도커 호스트 포트를 **5433**으로 이전(`docker-compose.yml`), `.env` `DATABASE_URL` 5433으로, `migrations/env.py`가 alembic.ini 하드코딩 대신 **`.env`의 DATABASE_URL을 단일 소스로** 쓰도록 수정
  - `database.py` 엔진에 `pool_pre_ping`/`pool_recycle` 추가(끊긴 커넥션 자동 복원)
- **빈 DB → `alembic upgrade head`로 테이블 8종 생성**, 프론트용 더미 유저(`00000000-…-001`) 시드
- **`setup.md` conda 기준 전면 정리** + ngrok 고정 도메인 팀 공유 가이드 / **GitHub CLI 설치**
- 서버 운영·트러블슈팅 문서 `backend/docs/server-ops.md` 신설 (DB 끊김/컨테이너 종료 진단법)

#### E2E 검증 + 소설 변환 실연결

- **백엔드 E2E 스모크 스크립트(`scripts/e2e_smoke.py`)** 작성 — 유저→세계관→캐릭터→세션→메시지→AI 스트리밍→채팅종료→소설변환 전 체인을 인프로세스(TestClient)로 검증, **9단계 전부 통과**
- **소설 변환 실연결(F-NV-02)** — `novels.py` 플레이스홀더 → `LLMRouter.generate_novel` 연결 (세계관 주입 + LLM 실패 시 폴백). 실제 소설 문체 변환 확인

#### 프롬프트 정리

- 런타임 프롬프트 3종(세계관/대화/초안)을 `core/personas.py`로 통합, 죽은 `model/prompts/system_prompts.py` 포인터화
- 이후 동완님이 personas.py를 리치 버전(character 모드·입력형식 규칙·novel_style)으로 보강 → llm_router도 새 시그니처에 맞게 정합 확인

#### 기획 / 문서

- 현황·시나리오 문서 정비: `PROJECT_STATUS.md` 최신화, **`사용자_시나리오.md`**(작가선택→세계관폼→채팅[AI가 대사/나레이션 자동구분]→채팅종료→소설변환, 사용자=주인공 고정) 확정, **`기능정의서.md`/`.html`**(발표용), **`문체모델_연동_설계.md`**, **`프롬프트_설계.md`**
- **강사님 스크럼 기록 `scrum.md`** 정리(6/1·6/2·6/4·6/5·6/8). 팀 결정 반영: **RAG = "세계관 일관성(장기 기억)"으로 재정의**(추리극 오해 기반 "캐릭터별 비밀정보 분리"는 채택 안 함), 타겟 2030 취미 창작러

### 이슈

- **Gemini 429 쿼터 소진** — 하루 테스트/시연 누적으로 무료 한도 초과. AI 생성이 폴백으로 떨어짐 → 새 키 또는 리셋 대기 필요
- **`/users/register` 깨짐** — passlib+bcrypt 버전 충돌(`password cannot be longer than 72 bytes`). 인증 후순위라 E2E에선 유저 직접 삽입으로 우회 (`bcrypt==4.0.1` 핀으로 해결 가능)
- **브랜치 사고** — 옛 로컬 `dev`(origin/dev보다 70커밋 뒤) 체크아웃으로 워킹트리가 옛 상태로 보임 + Vite가 mp4 잠금으로 체크아웃 막힘 → Vite 종료 후 `feature/jyj` 복귀, **작업 무손실**

### 다음 할 일

- **AI 오프닝**: AI 호출(비용) 대신 **세계관 setting 텍스트 기반 무료 템플릿**으로 (프론트가 표시, 백엔드 추가 호출 없음)
- **메모 → 프롬프트 주입(P0)**: 프론트(가은님) 메모가 현재 mock → 실제 전송 + 백엔드 컨텍스트 합치기 (합의 필요)
- **소설 footer 작가명**: Session에 `author_id`(persona) 저장 필요 — 현재 작가 선택이 백엔드에 미저장 (footer가 작가명 못 찾음)
- 전역 에러 핸들링 미들웨어 → **가연님** 담당
- 작가별 문체 소설 변환 주입(persona_id 연동), RAG(세계관 일관성) 검토

---

## 2026-06-05

### 작업 내역

#### 팀 PR 통합 및 검증

- `origin/dev` 머지로 팀원 작업 수신 (PR #11/#12/#13 → 이후 #14 ygh)
- 팀 PR 검증 후 머지: **#16**(worlds/characters → MongoDB 연동), **#18**(llm_router·llm_judge·personas·coaching·dialogues), **#19**(chats.py에 Redis 캐시 + MongoDB 영구저장·임베딩 결합), **#20**(README 최신화)
- 머지 검증 노하우 정립: `dev..feature` diff가 "내 작업을 삭제하는 것처럼 보이는 착시"는 옛 base에서 분기해서 생기는 것 → `git merge-tree --write-tree`로 **실제 머지 결과 트리**를 까서 보존/호환 확인
- #19로 대화 로그가 Mongo에 임베딩과 함께 적재되기 시작 (RAG 데이터 적재의 빠진 조각)

#### DB / 인프라

- **MongoDB Atlas 연결** (`.env`의 `MONGODB_URL`) — 로컬 Mongo 컨테이너 불필요
- DB 역할 정리: 정형(User/World/Character/Session/Novel) → **PostgreSQL**, 비정형(대화+임베딩) → **MongoDB**, 프롬프트 캐시 → **Redis**
- **팀 결정: PostgreSQL only로 통일** (강사님 스크럼 피드백 반영, 가연님이 연결구조 전면 수정 예정) → RAG 임베딩은 **pgvector**로 가야 함
- Docker Desktop WSL 엔진 미기동 → **Redis를 Upstash(클라우드)로 우회**, 도커 없이 해결

#### 서버 실행 환경

- conda(`nodevelture`, py3.11) 환경 확정, `python -m uvicorn`으로 환경 일치시켜 기동 (전역 py3.13 uvicorn 잘못 잡히던 문제 해결)
- `.env` 변경 시 서버 재시작 필수 확인 (`--reload`는 `.env` 미감시)

#### AI 모델 설계 검토

- 파인튜닝 베이스 모델 후보 정리(Qwen2.5-7B-Instruct 등) → 문체 모델 설계 검토
- 문체 모델 설계서 피드백 작성: PERSO 텍스트생성 불가(→Gemini로 정정), GPU 서빙 위치 명시 필요, mode 체계 불일치(collab/coach/compare vs 코드의 author/character), persona_id 철자(kimdohyeon), 창작 태스크 캐싱 주의

#### RAG 방향 정리

- RAG = **장기 기억(일관성)**용. 3단 기억 구조(최근 대화 Redis + 누적 요약 + RAG 검색)
- 적재는 #19로 시작됨, **검색을 chats.py `build_prompt`에 연결**하는 게 다음 스텝

### 이슈

- 워킹 트리가 옛 dev 상태로 되돌아간 사고(파일 삭제·chats.py 옛버전) → HEAD는 멀쩡, `git restore`로 복구. 원인은 잘못된 checkout
- `ygh_devlog.md` 빈 파일 = ygh PR이 dev에 머지되기 *전*의 dev를 받았던 타이밍 문제 → 재머지로 해결
- `REDIS_URL`에 `REDIS_URL=` 중복 입력 → Redis scheme 에러 → 제거 후 Upstash 연결 확인
- Docker Desktop WSL 엔진 미기동 (도커 우회로 진행)

### 다음 할 일

- 가연님 PostgreSQL-only 연결구조 변경 반영 후 통합
- RAG 검색을 chats.py `build_prompt`에 연결 (+ pgvector 검토)
- 문체 모델 설계서 회신 반영 (PERSO→Gemini, GPU 위치, mode 통일)
- 채팅 E2E 완주 (`POST messages` → `GET stream`)
- 잔여 정리: 죽은 스텁(`routes/chat`·`coaching`·`compare`), README의 PERSO 잔여 언급

---

## 2026-06-04

### 작업 내역

#### 환경 설정

- Python 3.13 호환 문제 발견 → Python 3.11로 venv 재생성
- conda 가상환경으로 팀 통일 (conda create -n nodevelture python=3.11)
- ngrok으로 로컬 서버 외부 공유 → 프론트엔드 팀원 연결 성공

#### 백엔드 구현

- Chat API 신규 구현 (`app/api/chats.py`)
  - `POST /api/chats/{chatId}/messages` — 사용자 메시지 수신
  - `GET /api/chats/{chatId}/stream` — SSE 스트리밍 (event: token / done)

- Gemini 2.5 Flash API 연결 완료 → 실제 AI 응답 동작 확인

- `personas.py` PERSO API 프롬프트 템플릿 구조로 전환

- `.env` 파일 생성, `GEMINI_API_KEY` 추가

- `.env.example` 실제 값 제거 (구조만 표기)

#### PR 관리

- PR #5 pytest 실패 원인 분석: docs 커밋에서 main.py 등 4개 파일 실수 삭제 → 복원 커밋
- PR #8 (Chat API + Gemini 연결) 머지
- PR #10 (DB 모델 수정 - 팀회의 결과 반영) 검토 및 머지 승인

#### 팀 회의 / 설계

- 사용자 시나리오 확정: 작가 선택 → 세계관 설정 → 작가모드/등장인물모드 채팅 → 소설 변환

- DB 모델 수정 사항 정리 (가연님 전달)
  - Character: user_id 추가, background/appearance → prompt 통합
  - User: email/password nullable
  - World: rules nullable

- DB/Redis 역할 분담 설계 확정
  - DB: 원본 저장소 (세계관, 사건, 대화로그, 호감도 등)
  - Redis: 프롬프트 조립용 임시 복사본 (최근 대화, 현재 상태, 캐릭터 캐시)
  - 5턴마다 Redis → DB 자동 동기화

#### PERSO API 확인

- 문서 검토 결과: 영상 번역/더빙 API로 텍스트 생성 불가
- 채팅 기능은 Gemini 유지, PERSO는 추후 TTS 용도로 검토

### 이슈

- Python 3.13에서 asyncpg, pydantic-core 빌드 실패 → 3.11로 해결
- PR #6 머지로 main.py MongoDB 버전 충돌 발생 → git restore로 해결
- Gemini 모델명 404 오류 (gemini-pro, gemini-1.5-flash) → list_models()로 확인 후 gemini-2.5-flash로 해결
- 브랜치 보호 규칙 미설정으로 팀원이 직접 머지 → GitHub Settings에서 규칙 설정 필요

### 다음 할 일

- 프롬프트 넣어서 채팅 답변 잘 나오는지 확인 (작가 4명 각각 테스트)
- `.env.example` GEMINI_API_KEY 항목 추가
- GitHub 브랜치 보호 규칙 설정 (dev 브랜치)

---

### 앞으로 해야 할 일 (전체 로드맵)

#### 이번 주 (1순위)

- [ ] 프롬프트 품질 테스트 및 개선 (백야/차로운/한여름/김도현 각각)
- [ ] 세계관 정보를 chat API에 연결 (world_context 프론트 → 백엔드)
- [ ] 전체 흐름 동작 확인 (작가 선택 → 세계관 설정 → 채팅 → 응답)
- [ ] 에러 핸들링 미들웨어 (전역 예외 처리)
- [ ] JWT 인증 구현 (로그인) ← 나중에

#### 다음 주 (2순위)

- [ ] Redis 세션 컨텍스트 캐시 구현
  - 최근 대화 N개 캐싱
  - 현재 세션 상태 저장
  - 캐릭터 정보 캐싱
- [ ] 프롬프트 조립 함수 작성 (세계관 + 캐릭터 + 사건요약 + 최근 대화)
- [ ] 5턴마다 Redis → DB 자동 동기화
- [ ] API Log 미들웨어 (토큰/비용 기록)
- [ ] 환경변수 스위칭 (Gemini ↔ PERSO 전환 구조)
- [ ] 프론트엔드 통합 테스트

#### 마지막 주 (3순위)

- [ ] Dockerfile 작성 (앱 컨테이너화)
- [ ] Render / Railway 배포
- [ ] README 실행 방법 업데이트
- [ ] 발표 자료 백엔드 파트 정리

---

## 2026-06-01

### 작업 내역

- 프로젝트 기획서 v1.1 검토 및 README 반영
  - 페르소나 이름 수정 (백야, 차로운, 한여름, 김도현)
  - 팀원 정보 업데이트
  - 캠프명 수정 (AI휴먼 캠프)

- GitHub 레포지토리 초기 세팅
  - 전체 폴더 구조 생성 (backend / frontend / model / data / docs)
  - `.gitignore`, `README.md` 작성
  - PR 템플릿 및 GitHub Actions CI (pytest) 추가
  - feature 브랜치 생성 및 원격 push (jyj, ygy, pge, ygh, kdy)
  - remote URL 레포 이름 변경 반영 (NodeVelture)

- docs/planning, docs/dev-logs 디렉터리 구조 확정

### 이슈

없음

### 다음 할 일

- 1주차 작업 분배 확인 및 각자 브랜치 작업 시작
- 페르소나 시스템 프롬프트 초안 작성
