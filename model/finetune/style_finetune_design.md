# 문체 파인튜닝 모델 설계서 수정본

## 모델 선정 근거

### [x] 베이스 모델 후보 2~3개 + 최종 선택

* 후보 A: `Qwen/Qwen2.5-7B-Instruct`

  * 최종 선택 모델
* 후보 B: `meta-llama/Meta-Llama-3.1-8B-Instruct`
* 후보 C: `Qwen/Qwen2.5-3B-Instruct`

  * 경량 / 저지연 대안

### [x] 선택 근거

최종 모델은 `Qwen/Qwen2.5-7B-Instruct`로 선정한다.

CoAuthor는 단순 질의응답 서비스가 아니라, 장르별 작가 페르소나와 함께 소설을 쓰는 창작 플랫폼이다. 따라서 한국어 문장 리듬, 감정 표현, 말투 제어, 장르별 분위기 유지가 중요하다.

`Qwen2.5-7B-Instruct`는 7B급 인스트럭트 모델이기 때문에 페르소나 프롬프트와 instruction tuning을 적용하기에 적절하다. 또한 3B 모델보다 문체 표현력과 페르소나 유지력이 높을 것으로 기대된다.

라이선스는 실제 적용 전 Hugging Face 모델 카드와 원 라이선스 문서를 팀 차원에서 재확인한다. 특히 상업적 활용 가능 여부, 배포 가능 여부, 파생 모델 공개 조건을 확인한 뒤 사용한다.

파라미터 크기 측면에서도 7B는 현실적인 선택이다. RTX 4090 24GB 또는 A10 24GB급 GPU에서 QLoRA 학습과 vLLM 서빙을 실험할 수 있다. 3B 모델은 비용과 latency 측면에서 유리하지만, 최종 품질이 낮을 수 있어 대안 모델로 둔다.

### [x] 비교 기준

리더보드 점수보다 우리 서비스 태스크 중심 평가를 우선한다.

비교 방식은 다음과 같다.

1. 고정 평가셋 100~300개를 만든다.
2. 동일 입력에 대해 네 개 페르소나 출력을 생성한다.
3. 후보 모델별 출력 결과를 비교한다.
4. `model/evaluation/llm_judge.py`로 자동 평가한다.
5. 팀원이 샘플 출력을 직접 보고 정성 평가한다.

평가 기준은 다음과 같다.

* 페르소나 일관성: 5점 척도, 평균 4.0 이상 목표
* 장르 구분도: 페르소나 간 출력 유사도 0.6 미만 목표
* 문장 자연스러움
* 반복률
* 응답 길이 안정성
* 사용자와 함께 쓰는 느낌

---

## 데이터

### [x] 말뭉치 출처 + 라이선스

학습 데이터는 내부 실험용과 배포 가능 데이터로 분리한다.

1. 내부 실험용 데이터

* 현재 보유한 구매도서 기반 한국어 말뭉치
* 원천 TSV 및 라벨링 JSON
* 단, 저작권과 재배포 이슈가 있을 수 있으므로 비공개 프로토타입 실험에만 사용한다.
* 상용 배포 모델 학습에는 사용하지 않는 것을 원칙으로 한다.

2. 공개 / 배포 가능 데이터

* Project Gutenberg 저작권 만료 문학 텍스트
* 공유마당 등 공개 라이선스 한국어 텍스트
* 저작권 만료 또는 파인튜닝 허용 라이선스가 명확한 데이터만 사용한다.

최종 발표 및 배포 가능 모델은 공개 라이선스 데이터 중심으로 학습한다.

### [x] 전처리·포맷

권장 포맷은 instruction/chat tuning 형식이다.

단순 원문 학습이 아니라, 페르소나와 제품 모드를 명시한 형태로 구성한다.

현재 제품 코드 기준 mode는 다음 두 가지로 통일한다.

* `author`: 작가와 함께 글을 쓰는 모드
* `character`: 등장인물과 대화하거나 캐릭터를 구체화하는 모드

예시 포맷:

```json
{
  "persona_id": "baekya",
  "mode": "author",
  "messages": [
    {
      "role": "system",
      "content": "너는 백야라는 호러/미스터리 작가다. 짧은 문장, 침묵, 여백을 중시한다."
    },
    {
      "role": "user",
      "content": "비 오는 밤, 버스 정류장에 혼자 남았다. 이어서 써줘."
    },
    {
      "role": "assistant",
      "content": "버스는 오지 않았다. 대신, 정류장 유리벽에 안쪽에서 손자국이 번졌다."
    }
  ]
}
```

사용할 `persona_id`는 코드 기준에 맞춰 다음과 같이 통일한다.

* `baekya`
* `charoun`
* `hanyeoreum`
* `kimdohyeon`

### [x] 규모

3주 프로젝트 기준 1차 학습 규모는 현실적으로 다음 정도를 목표로 한다.

* persona당 1,000~3,000 turn
* 전체 약 4,000~12,000 turn

이 규모는 완전한 상용 품질보다 데모에서 문체 차이와 페르소나 특성을 보여주는 것을 목표로 한다.

이후 확장 단계에서는 다음을 목표로 한다.

* persona당 5,000~10,000 turn
* 전체 약 20,000~40,000 turn

---

## 파인튜닝 방법

### [x] 기법

권장 방식은 QLoRA이다.

Full fine-tuning은 3주 프로젝트에서 비용, 시간, GPU 메모리 부담이 크다. LoRA도 가능하지만, 7B 모델을 단일 24GB GPU에서 빠르게 여러 번 실험하기 위해서는 QLoRA가 더 적합하다.

선정 이유는 다음과 같다.

* GPU 메모리 절약
* 반복 실험 속도 확보
* 7B 모델을 24GB GPU에서 실험 가능
* persona별 adapter 분리 가능
* 실패해도 빠르게 재학습 가능

### [x] 하드웨어

현재 팀 보유 GPU가 확정되지 않았으므로, 1차 기준은 RunPod 등 클라우드 GPU 대여로 잡는다.

권장 학습 환경:

* RTX 4090 24GB 1장
* A10 24GB 1장
* 가능하면 L40S / A100 사용 시 학습 시간 단축 가능

예상 학습 시간:

* 4,000~12,000 turn 기준: 수 시간~반나절
* 20,000 turn 이상: 반나절~1일 이상

실제 학습 시간은 다음 요소에 따라 달라진다.

* max sequence length
* batch size
* gradient accumulation
* epoch 수
* 데이터 토큰 수

초기 권장 설정:

* max sequence length: 1024
* epoch: 1~3
* LoRA rank: r=8 또는 r=16
* 학습 방식: QLoRA 4bit

### [x] 장르/작가별 처리 방식

권장 구조는 단일 베이스 모델 + persona별 LoRA adapter이다.

구조:

```text
Qwen/Qwen2.5-7B-Instruct
 ├─ baekya LoRA adapter
 ├─ charoun LoRA adapter
 ├─ hanyeoreum LoRA adapter
 └─ kimdohyeon LoRA adapter
```

장점:

* 페르소나 간 문체 간섭을 줄일 수 있다.
* 같은 입력에 대해 네 페르소나 출력을 만들기 쉽다.
* Router에서 `persona_id` 기준으로 adapter를 선택할 수 있다.
* 특정 페르소나만 재학습하거나 교체하기 쉽다.

---

## 평가

### [x] 문체 일관성 / 작가 구분도 측정 방법

자동 평가는 `model/evaluation/llm_judge.py`를 활용한다.

평가 항목은 다음과 같다.

1. 문체 일관성

* 각 페르소나의 말투, 문장 길이, 장르적 분위기를 잘 지키는지 평가
* 5점 척도
* 목표: 평균 4.0 이상

2. 장르 구분도

* 같은 입력에 대해 네 페르소나 출력이 충분히 다르게 나오는지 확인
* sentence embedding 기반 코사인 유사도 사용
* 목표: 페르소나 간 유사도 0.6 미만

3. 반복률

* 같은 단어, 문장, 표현의 반복 여부 측정

4. 응답 안정성

* 빈 응답
* 지나치게 짧은 응답
* 지나치게 긴 응답
* 페르소나 이탈
* 시스템 프롬프트 위반 여부 확인

휴먼 평가는 최소 10명 이상을 대상으로 진행한다.

질문 예시:

* 이 작가와 함께 글을 쓰고 싶다는 느낌이 드는가?
* 페르소나가 캐릭터답게 느껴지는가?
* 문장이 자연스러운가?
* 네 작가의 차이가 명확하게 느껴지는가?

### [x] 기존 Gemini 대비 비교

PERSO API는 텍스트 생성용으로 사용하지 않고, 비교 및 운영 기준은 Gemini로 통일한다.

비교 방식:

1. 고정 입력 100~300개 준비
2. Gemini 출력 생성
3. 자체 QLoRA 모델 출력 생성
4. 모델명을 가리고 블라인드 평가
5. `llm_judge.py`로 페르소나 일관성, 장르 구분도, 자연스러움 비교
6. 발표용 "한 입력 → 4개 페르소나 출력" 장면 선정

운영 전략:

* 발표 및 데모 안정성은 Gemini를 메인으로 확보한다.
* 자체 모델은 단순 이어쓰기, 짧은 장면 생성, 일부 author 모드에 제한적으로 투입한다.
* Judge 점수가 기준 미달이면 자체 모델 트래픽 비율을 낮추고 Gemini로 폴백한다.

---

## RAG와 파인튜닝 관계

### [x] RAG 역할

오늘 스크럼 내용에 맞춰 RAG를 함께 사용한다.

RAG는 다음 용도로 사용한다.

* 페르소나 카드 검색
* 장르별 문체 규칙 검색
* 캐릭터 설정 유지
* 이전 대화 기억 유지
* 사용자 작품 세계관 / 등장인물 정보 검색
* 작가별 금지사항 및 말투 규칙 보강

즉, RAG는 "무엇을 기억하고 지켜야 하는가"를 담당한다.

### [x] 파인튜닝 역할

파인튜닝은 다음 용도로 사용한다.

* 문장 리듬 학습
* 페르소나별 말투 학습
* 장르별 분위기 학습
* 짧은 이어쓰기 품질 향상
* Gemini보다 더 일관된 특정 작가 톤 제공

즉, 파인튜닝은 "어떤 문체로 말하고 쓸 것인가"를 담당한다.

### [x] 임베딩 저장소

팀 결정에 맞춰 RAG 임베딩 저장소는 Postgres + pgvector로 통일한다.

구조 예시:

```text
Postgres
 ├─ conversations
 ├─ messages
 ├─ personas
 ├─ character_profiles
 ├─ world_settings
 └─ rag_embeddings (pgvector)
```

RAG 흐름:

```text
사용자 입력
 → persona_id / mode 확인
 → pgvector에서 관련 페르소나·캐릭터·이전 대화 검색
 → 검색 결과를 system/context에 삽입
 → Gemini 또는 자체 모델 호출
```

정리하면 다음과 같다.

```text
RAG = 기억 / 설정 / 일관성
Fine-tuning = 문체 / 리듬 / 페르소나 톤
Gemini = 안정적인 메인 생성 엔진
자체 모델 = 문체 특화 보조 엔진
```

---

## 접목: 백엔드 연동

### [x] 서빙 방식

최종 권장 방식은 vLLM이다.

이유는 다음과 같다.

* FastAPI와 연동하기 좋다.
* OpenAI-compatible API 형태로 붙이기 쉽다.
* SSE streaming 응답을 지원하기 좋다.
* 동시 요청 처리와 throughput이 Ollama보다 유리하다.
* LLMRouter에서 Gemini와 자체 모델을 같은 인터페이스로 다루기 쉽다.

개발 / 로컬 데모용으로는 Ollama도 가능하지만, 최종 연동 기준은 vLLM으로 둔다.

GPU 서버는 RunPod 등 클라우드 GPU 인스턴스를 기준으로 한다.

데모 구조:

```text
Frontend
 → FastAPI Backend
 → LLMRouter
 → Gemini API 또는 RunPod vLLM Server
```

vLLM 서버 예시:

```text
https://<runpod-endpoint>/v1/chat/completions
```

백엔드는 환경변수로 vLLM endpoint를 관리한다.

```env
CUSTOM_LLM_BASE_URL=https://<runpod-endpoint>/v1
CUSTOM_LLM_API_KEY=<optional>
CUSTOM_LLM_MODEL=qwen2.5-7b-coauthor
```

### [x] 호출 인터페이스

백엔드 인터페이스는 현재 코드 구조에 맞춰 `author / character` mode를 사용한다.

요청 예시:

```json
{
  "persona_id": "baekya",
  "mode": "author",
  "messages": [
    {
      "role": "user",
      "content": "비 오는 밤, 버스 정류장에 혼자 남았다. 이어서 써줘."
    }
  ],
  "temperature": 0.8,
  "max_tokens": 512,
  "stream": true
}
```

응답 예시:

```json
{
  "engine": "custom_vllm",
  "model": "qwen2.5-7b-coauthor",
  "persona_id": "baekya",
  "mode": "author",
  "content": "버스는 오지 않았다. 대신, 정류장 유리벽에 안쪽에서 손자국이 번졌다.",
  "fallback": false,
  "latency_ms": 3200
}
```

Router 내부 처리:

```text
1. persona_id 확인
2. mode(author / character) 확인
3. RAG context 조회(pgvector)
4. system prompt 구성
5. 모델 선택
   - 기본: Gemini
   - 조건 충족 시: 자체 vLLM 모델
6. 스트리밍 응답 반환
7. 필요 시 평가 로그 저장
```

### [x] 예상 latency / 비용

목표 latency:

* P95 < 5,000ms

자체 모델 사용 조건:

* 짧은 이어쓰기
* author 모드
* max_tokens 256~512
* GPU 서버 정상 상태
* Judge 기준 충족

초기 운영 비율:

* Gemini: 70~90%
* 자체 QLoRA 모델: 10~30%

발표 안정성을 위해 Gemini를 메인으로 두고, 자체 모델은 제한적으로 사용한다.

캐싱 전략은 다음과 같이 수정한다.

* 라이브 이어쓰기 / 실시간 채팅: 캐시 OFF
* 이유: 창작 태스크에서는 재시도 시 같은 글이 반복되면 사용자 경험이 떨어짐
* 장르 비교 / 발표용 고정 시나리오: 캐시 ON
* 이유: 데모 안정성과 비용 절감을 위해 동일 입력 결과 재사용 가능

### [x] 폴백 전략

PERSO API는 폴백 엔진에서 제외하고 Gemini를 메인/폴백 기준으로 사용한다.

기본 전략:

```text
1순위: Gemini
2순위: 자체 QLoRA + vLLM
3순위: Gemini 재시도 또는 저가 LLM
```

실제 운영에서는 다음과 같이 처리한다.

* 기본 생성: Gemini
* 자체 모델 실험 구간: author 모드 일부 요청만 vLLM으로 라우팅
* 자체 모델 실패 시 즉시 Gemini로 폴백

폴백 조건:

* vLLM 서버 timeout
* GPU 서버 응답 없음
* latency 5초 초과
* 빈 응답
* 페르소나 이탈
* 금칙어 / 시스템 프롬프트 위반
* Judge 점수 기준 미달

Router 예시:

```text
if custom_model_timeout:
    use_gemini()

if judge_score < threshold:
    use_gemini()
```

---

## 일정

### [x] 3주 안에 어디까지

#### 1주차: 6/2 ~ 6/8

목표:

* 페르소나 카드 4종 확정
* system prompt 초안 작성
* 고정 평가셋 100~300개 구축
* `model/evaluation/llm_judge.py` 연결
* Gemini 기반 데모 구현
* RAG용 persona / character / world setting 데이터 구조 정리

산출물:

* persona card
* system prompt
* eval dataset
* Gemini 기반 라이브 채팅
* pgvector 설계 초안

#### 2주차: 6/9 ~ 6/15

목표:

* Qwen2.5-7B-Instruct 기반 QLoRA 1차 실험
* persona별 LoRA adapter 4개 생성
* RunPod 등 GPU 서버에서 vLLM 테스트
* 백엔드에서 vLLM endpoint 연결 테스트
* RAG context를 Gemini 프롬프트에 삽입

산출물:

* baekya adapter
* charoun adapter
* hanyeoreum adapter
* kimdohyeon adapter
* vLLM endpoint
* pgvector 기반 RAG 1차 연결
* 내부 평가 리포트 1차

#### 3주차: 6/16 ~ 6/19

목표:

* 발표용 장르 비교 시나리오 완성
* "한 입력 → 4개 페르소나 출력" 데모 구현
* Gemini vs 자체 QLoRA 모델 블라인드 비교
* timeout / fallback / cache 정책 적용
* 발표에서는 Gemini를 메인 엔진으로 두고, 자체 모델은 차별화 파트로 합류

산출물:

* 시연 가능한 CoAuthor 데모
* Judge 평가 결과
* Gemini 대비 자체 모델 비교표
* RAG + 파인튜닝 역할 분리 설명
* 발표용 입력/출력 샘플

최종 전략:

3주 안에 자체 모델을 완전한 메인 엔진으로 만들기보다는, Gemini 기반 안정 데모를 우선 완성한다. 자체 파인튜닝 모델은 author 모드의 짧은 이어쓰기와 장르 비교 일부에 제한적으로 연결하여 "문체 특화 자체 모델을 실험했다"는 차별화 근거로 활용한다.
