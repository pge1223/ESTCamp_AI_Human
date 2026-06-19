# 2026-06-11

## 오늘 한 일

- `backend/app/services/tts.py` 신규 (F-AV-02)
  - ElevenLabs eleven_multilingual_v2 모델 연동
  - 작가별 음성 ID 매핑 (백야/차로운/한여름/김도현)
  - 계정 2개로 API 키 분리 (ELEVENLABS_API_KEY_1 / ELEVENLABS_API_KEY_2)
  - narration 50자 내외 2문장 추출 로직 (`extract_first_sentence()`)

- `backend/app/api/v1/endpoints/chats.py` 수정 (F-AV-02)
  - `stream_response()`에 TTS 변환 로직 추가
  - reply 이벤트 먼저 전달 후 TTS 변환 시작
  - 변환 완료 시 `event:audio`로 base64 음성 데이터 전달
  - TTS 실패 시 음성 없이 정상 진행

- `backend/app/api/v1/endpoints/authors.py` 수정 (F-AS-05)
  - 작가 리액션 정적 데이터 추가 (first_input / unexpected / good_scene / stuck / chapter_done)
  - `GET /authors/{author_id}/reactions` 전체 리액션 세트 반환
  - `GET /authors/{author_id}/reactions/{trigger}` 특정 상황 리액션 반환

## 이슈 / 막힌 점

- OpenAI TTS → ElevenLabs로 전환 과정에서 여러 문제 발생
  - ElevenLabs 무료 플랜은 라이브러리 음성 API 미지원 (402 Payment Required)
  - Voice Design으로 직접 만든 음성으로 교체하여 해결
  - 계정 2개로 API 키 분리하여 4명 작가 각각 할당
- `tts.py`에서 `persona_id` 선언 순서 오류 → 수정 완료

## 내일 할 일

- 프롬프트 일괄 설계 — 세계관 태그분류, 일관성 검수, 창작 유도/막힘, 조연 다중반응

---

# 2025-06-10

## 오늘 한 일

- `backend/app/services/tts.py` 신규 (F-AV-02)
  - OpenAI tts-1 모델 연동
  - 작가별 음성 매핑 (백야→onyx / 차로운→echo / 한여름→nova / 김도현→fable)
  - narration 첫 문장 추출 로직 (`extract_first_sentence()`)

- `backend/app/api/v1/endpoints/chats.py` 수정 (F-AV-02)
  - `stream_response()`에 TTS 변환 로직 추가
  - `parse_ai_response()` 후 narration 첫 문장 → TTS 변환 → base64 인코딩
  - reply 이벤트에 `audio` 필드 추가 — 텍스트와 음성 동시 전달
  - TTS 실패 시 음성 없이 정상 진행 (에러 핸들링)

- `backend/app/api/v1/endpoints/authors.py` 수정 (F-AS-05)
  - 작가 리액션 정적 데이터 추가 (5가지 상황: first_input / unexpected / good_scene / stuck / chapter_done)
  - `GET /authors/{author_id}/reactions` 전체 리액션 세트 반환
  - `GET /authors/{author_id}/reactions/{trigger}` 특정 상황 리액션 반환

## 이슈 / 막힌 점

- `chats.py` 수정본을 `dialogues.py`에 잘못 덮어씌우는 실수 발생
  - `git checkout origin/dev -- backend/app/api/v1/endpoints/dialogues.py` 로 복구
  - 이후 `chats.py` 올바르게 적용 후 재푸시

## 내일 할 일

- F-PR-02 사용자 취향 → 말투 조정 프롬프트 (PR-01 스키마 확정 후)

---

# 2025-06-09

## 오늘 한 일

- `data/world_tags.json` 신규 — 세계관 멀티라벨 마스터 태그 사전 (154개, 11개 카테고리)

- `backend/app/services/world_tag_classifier.py` 신규 (F-WD-06)
  - 1차 키워드 필터로 후보 압축 (120개 → 평균 30~40개) → LLM closed-set 분류
  - 결과 `World.tags` DB 저장, 사용자 편집 가능한 하이브리드 구조
  - `classify_world_tags()` + `context_block` 프롬프트/RAG 주입용 블록 반환

- `backend/app/prompts/__init__.py` 4개 상수 추가/교체
  - `CONSISTENCY_SYSTEM` 교체 (F-QC-01) — 모순 판단 기준 명확화, severity 기준 구체화, suggestion 필드 추가
  - `SUGGEST_NEXT_SYSTEM` 추가 (F-AS-02) — 창작 유도 선택지 3개
  - `STUCK_HELP_SYSTEM` 추가 (F-AS-03) — 막힘 도움 힌트 + 격려 톤
  - `MULTI_NPC_SYSTEM` + `build_multi_npc_prompt()` 추가 (F-CH-09) — 조연 다중 동시 반응, narration + responses[] 구조

- `backend/app/services/evaluate.py` — `EVAL_SYSTEM` 교체 (F-EV-03/06)
  - 항목별 5점 척도 기준 명시 → 채점 일관성 향상
  - `style_distinct` 루브릭 강화 — "다른 3명과 혼동 불가" 기준
  - `style_weakness` 필드 추가 → 문체 튜닝 피드백 루프용

- `backend/scripts/evidence_report.py` 덮어쓰기 (F-EV-06)
  - 시나리오 1개 → 3개 (추리/호러/로맨스), 3회 평균으로 신뢰도 향상
  - `BASELINE_SYSTEM` 강화 — 현실적인 ChatGPT 사용자 수준
  - 결과 JSON 자동 저장 → 발표 자료로 바로 활용 가능

- `backend/app/core/personas.py` — `get_author_prompt(mode="author")` 문구 수정
  - "한 문단 완성" → narration/dialogue JSON 구조 정합

## 이슈 / 막힌 점

- `world_tag_classifier.py`의 `_TAG_FILE` 경로가 실행 위치에 따라 달라질 수 있음 — 가연님과 경로 확인 필요
- `evidence_report.py` 시나리오 3개 × 3회 = 총 18회 LLM 호출 — 실행 시 비용/시간 고려 필요 (약 2~3분 소요 예상)

## 내일 할 일

- 페르소나·문체 프롬프트 튜닝 (F-EV-04) — 회의 후 진행
- `google.generativeai` → `google.genai` 패키지 교체
- 가연님 백엔드 연동 후 world_tag_classifier E2E 테스트
- evidence_report.py 실제 실행 후 결과 검토

---

# 2025-06-08

## 오늘 한 일

- 페르소나 프롬프트 E2E 테스트 완료
  - 서버 로컬 실행 (`uvicorn`) + Swagger UI 동작 확인
  - `test_personas.py` 작성 — 4명 장르 비교 + 가드레일 테스트
  - 백야/차로운/한여름/김도현 전원 페르소나 톤 검증 완료
  - 가드레일 3케이스 전원 통과 (장르 이탈, 페르소나 파괴 시도)

- `backend/app/core/personas.py` 프롬프트 3종 통합
  - `build_world_prompt(persona_id)` 신규 구현
    - 주연/조연/엑스트라 구분 조언, 작가별 시각 반영, 친근한 톤
  - `get_author_prompt()` 보강
    - `mode="character"` 추가 — 세계관 속 등장인물로 대화
    - 입력 형식 규칙 3종 적용: `"대사"` / `'속마음'` / `*서술*`
    - 성격(character_personality) 기반 동적 반응, 고정 예시 제거
  - `build_novel_system(persona_id, world_context)` 신규 구현
    - 작가별 문체 주입 (novel_style)
    - 대사/속마음/서술 구분 규칙 포함
    - 초안 완성 후 세계관 추가 제안 블록 (중요도 높음/보통만 제안)
  - `_AUTHOR_PERSONALITY` 내부 딕셔너리 추가 — 성격/worldview_focus/novel_style 작가별 분리
  - 기존 `PERSONA_PROMPTS` / `get_author_prompt(mode="author")` 동작 유지

- 프롬프트 설계 문서(`docs/프롬프트_설계.md`) 검토 및 반영
  - `build_novel_system()`에 `persona_id` 파라미터 추가 (팀 합의)
  - `model/prompts/` 는 학습/실험 전용으로 분리 확인

## 이슈 / 막힌 점

- `google.generativeai` deprecated 경고 발생
  - `FutureWarning: All support for the google.generativeai package has ended`
  - `google.genai` 패키지로 교체 필요 — 데모 이후 작업 예정
- 가드레일 테스트 1차 시도 시 캐시 충돌로 응답 없음
  - 동일 session_id 재사용으로 Redis 히트 → 세션 ID 분리로 해결

## 내일 할 일

- `google.generativeai` → `google.genai` 패키지 교체
- 1-2 character 모드 E2E 테스트
- LLM-as-Judge 평가 루프 연동
- 소설 초안 변환 E2E 테스트 (`build_novel_system` 실제 호출)

---

# 2025-06-05

## 오늘 한 일

- `llm_router.py` 구현 완료
  - Gemini 2.5 Flash 실제 호출 연결 (협업/코칭/비교/소설변환 4개 모드)
  - PRIMARY → FALLBACK(gemini-1.5-flash) 자동 전환 로직
  - Redis 캐시 연동 (namespace별 분리)
  - `ContextManager` 연결 — RAG + 요약본 자동 주입

- `core/personas.py` 풀 프롬프트 버전으로 교체
  - 기존 단순 설명 → WORLD RULE + CHARACTER RULE + GUARD RAIL + FEW-SHOT 구조
  - `get_author_prompt()` 작가/등장인물 모드 분기 추가

- `api/v1/endpoints/dialogues.py` LLMRouter 실제 연결
  - 사용자 발화 저장 → RAG 검색 → Gemini 스트리밍 → AI 응답 MongoDB 저장
  - end-to-end 파이프라인 완성

- `schemas/coaching.py` 페르소나 ID 오타 수정
  - `baegil` → `baekya`, `charoi` → `charoun` 등 4개 전부 수정

- `model/evaluation/llm_judge.py` 구현 완료
  - Gemini 기반 LLM-as-Judge 단일/배치 평가 파이프라인
  - JSON 파싱 방어 (`re.sub` 방식), score 범위 검증(1~5), few-shot 채점 예시 추가
  - `datetime.utcnow()` deprecated → `datetime.now(timezone.utc)` 수정

- `model/prompts/system_prompts.py` 완성
  - 페르소나별 few-shot 예시 코드 내장 (작가당 5개, 모드별 분리)
  - 인메모리 캐시로 중복 프롬프트 조립 방지
  - `build_system_prompt(persona_id, mode, world_context)` 인터페이스 확정

- `services/context_manager.py` 신규 구현
  - 10턴마다 Gemini로 자동 요약 생성 → Redis 저장 (TTL 1시간)
  - 최근 10턴 히스토리 캐시 (TTL 10분)
  - `get_context()` — 요약 + 히스토리 + RAG 한번에 조합해서 반환

## 이슈 / 막힌 점

- `llm_router.py`의 `CacheService.get/set` 시그니처(namespace 인자 방식)가 기존 `cache.py` 구현과 맞는지 가연님 확인 필요
- `llm_judge.py`가 `backend/` 외부(`model/`)에 위치해 `app.core.config` import 시 CLI 실행할 때 sys.path 수동 설정 필요 — 추후 패키지 구조 정리 예정
- PERSO API 공식 문서가 외부 공개 안 됨 — API 키 수령 후 엔드포인트 확인 필요 (`perso_client.py` 주석 처리 중)

## 내일 할 일

- A/B 실험 스크립트 작성 (PERSO 단독 vs Gemini 하이브리드 비교)
- 테스트 시나리오 10~20개 작성 (일상/장르특화/엣지케이스/위험)
- `perso_personas.py` PERSO API 등록 테스트 (API 키 수령 시)
- `ContextManager` 단위 테스트 작성
