# 보이스피싱 실시간 탐지 앱

## 프로젝트 개요
통화 중 음성을 실시간 분석해 보이스피싱 위험도를 탐지하는 Android 앱.
Python(AI 파이프라인) + Kotlin(Android 앱) 구성.

## AI 파이프라인 구조
```
통화 음성 (실시간)
  ↓ Android SpeechRecognizer (STT)
텍스트
  ↓ 슬라이딩 윈도우 (키워드 1차 필터, <10ms, 창 크기 100단어)
    - 키워드 매칭: 15점/건
    - URL 패턴 감지: 30점/건 (숫자 포함 도메인, www 언급)
  ↓ 15점 이상이면
KoELECTRA TFLite (문맥 판단, ~80ms, 온디바이스)
  ↓ 위험 판정이면
위험도 % 출력 + 경고
```

> ⚠️ LLM은 학습 데이터 라벨링 단계에서만 사용. 배포 앱에서는 동작하지 않음.
> ⚠️ 최종 배포 모델은 KoELECTRA TFLite. KoBERT는 초기 후보였으나 대체됨.

## 확정된 기술 스택

### Python (AI 파이프라인)
- Python 3.11 / uv 환경
- STT 전처리 (학습용): OpenAI Whisper small
- 형태소 분석: KoNLPy (Okt)
- 1차 필터: 슬라이딩 윈도우 (키워드 빈도 기반)
- 문맥 판단 모델: KoELECTRA (monologg/koelectra-base-v3-discriminator)
- 학습 프레임워크: PyTorch + HuggingFace Transformers
- 경량화: ONNX → TFLite 변환 (목표 크기 20MB 이하)

### Android 앱 (Flutter/Dart)
- Flutter + Dart (크로스플랫폼, 현재 Android 타겟)
- 음성 인식: Android SpeechRecognizer API (`speech_to_text` 패키지)
- AI 추론: `tflite_flutter ^0.12.1` (KoELECTRA TFLite, 온디바이스)
  - 입력 텐서 순서: [0]=attention_mask, [1]=input_ids, [2]=token_type_ids
  - int64 텐서: `Int64List.fromList().buffer.asUint8List()` 로 raw bytes 전달
- 알림: FCM (Firebase, 가족 알림 서비스)
- 최소 SDK: Android 8.0 (API 26)

## 학습 데이터 구성 (최종)

### 데이터 출처
- 금융감독원 보이스피싱 MP4 104개 → Whisper STT → 키워드 기반 라벨링
- GPT-4o-mini 증강 데이터 (기관사칭 / 금전요구 / 개인정보)
- AI Hub 텍스트 윤리검증 데이터 (정상 클래스)

### 라벨 구조 — 멀티라벨 (확정)
> ⚠️ 기존 5개 단일 클래스(기관사칭/금전요구/개인정보/복합/정상) → 멀티라벨로 변경
> 복합 클래스 제거. 각 카테고리를 독립적으로 판단.

```python
# 라벨 형식: [기관사칭, 금전요구, 개인정보]
[1, 0, 0]  # 기관사칭만
[0, 1, 0]  # 금전요구만
[0, 0, 1]  # 개인정보만
[1, 1, 0]  # 기관사칭 + 금전요구 동시
[1, 0, 1]  # 기관사칭 + 개인정보 동시
[0, 0, 0]  # 정상
```

카테고리별 데이터 분포:
- 기관사칭 포함: 168개
- 금전요구 포함: 128개
- 개인정보 포함: 153개
- 정상 (전부 0): 164개

### 모델 출력 구조
```python
# 손실함수: BCEWithLogitsLoss (멀티라벨용)
# 출력: 3개 노드 (각각 Sigmoid)
# 추론 시 임계값: 0.5 이상이면 해당 카테고리 감지
output = sigmoid(logits)  # [0.92, 0.88, 0.05]
# → 기관사칭: 92%, 금전요구: 88%, 개인정보: 5%
```

### 위험도 집계 로직 (확정)

단순 max가 아닌 복합 탐지 보정 적용 (`PhishingResult.maxProb`):

```
base = max(probs)
active = probs 중 0.5 이상인 라벨 수
위험도 = base + (active - 1) * 0.05   ← 복합 라벨 1개 추가당 +5%
```

| 상황 | probs | 위험도 |
|------|-------|--------|
| 단일 탐지 | [0.88, 0.02, 0.05] | 88% |
| 2개 복합  | [0.88, 0.79, 0.05] | 93% (+5%) |
| 3개 복합  | [0.88, 0.79, 0.94] | 99% (+10%) |

> +5% 수치는 실기기 테스트 후 조정 가능. `phishing_analyzer_service.dart` `maxProb` getter에서 관리.

### 위험도 레벨 기준 (UI)

| warningLevel | riskPercent | 색상 | 표시 |
|---|---|---|---|
| 0 | 0~10% | 초록 | 안전 |
| 1 | 11~30% | 노랑 | 주의 |
| 2 | 31~60% | 주황 | 경고 |
| 3 | 61%+   | 빨강 | 위험 |

- 경고창 팝업: `riskPercent >= 70` 시 1회
- `_lockedRisk`: 모델 추론(triggered=true)으로 확정된 최고 위험도는 통화 중 내려가지 않음

### 데이터 파일 (최종)
- multilabel_all.json: 564개 (전체)
- train_ml.json: 451개
- val_ml.json:    56개
- test_ml.json:   57개

**v3 학습 데이터** (`data/v3/`) — v2 + 정상 샘플 대량 추가
- normal_tts.json:        13,922개 (친절체+대화체 TTS 정상 샘플)
- normal_callcenter.json:  2,500개 (K쇼핑 콜센터 정상 샘플)
- 목적: 정상 클래스 다양성 강화 → 오탐률 감소

### 1차 필터 키워드 현황 (`pipeline/filter.py`)

| 카테고리 | 주요 키워드 | 최근 추가 |
|----------|------------|----------|
| 기관사칭 | 검찰, 검사, 수사관, 지검, 경찰청 … | 수사과, 사무관, 조사관, 수사팀, 공문, 사건조회 |
| 금전요구 | 계좌이체, 안전계좌, 공탁금, 송금 … | — |
| 개인정보 | 주민번호, OTP, 카드번호, 인증번호 … | 실명인증, 실명확인, 본인확인 |
| 기술적위협 | 팀뷰어, 원격제어, 악성코드, 링크 … | 주소창, 인터넷주소 |
| 심리적압박 | 구속영장, 범죄연루, 소환장 … | — |
| URL피싱 | (정규식) `www` 단독 언급 또는 숫자 포함 도메인 (`ykiscs24.kr` 등) | 신규 추가 |

### 라벨링 방식
1. 기관사칭/금전요구/개인정보/정상 → 규칙 기반 직접 변환
2. 복합 → GPT-4o-mini로 [기관사칭, 금전요구, 개인정보] 조합 판단

## 핵심 기능
1. 통화 중 음성 실시간 STT 변환
2. AI 기반 문맥 분석 → 보이스피싱 위험도 (0~100%)
3. 위험도에 따라 버튼 테두리 초록→노랑→빨강 변화 + 글로우 효과
4. 기관사칭 / 금전요구 / 개인정보 카테고리별 감지
5. AI 음성(딥페이크) 탐지
6. 가족 알림 서비스 (위험도 61%+ 시 FCM 푸시)
7. 전화 자동 감지 및 앱 자동 실행

## UI

### 현재 구현 상태 (`call_screen.dart`)
- 위험도 인디케이터 박스: 상단 레이블(안전/주의/경고/위험) + 위험도 % + LinearProgressIndicator
- 프로그레스바: `TweenAnimationBuilder` (600ms easeOut) 로 값 변화 시 부드럽게 애니메이션
- 카테고리 칩: 감지된 라벨 (`기관사칭` / `금전요구` / `개인정보`) — 한번 뜨면 통화 중 유지
- 실시간 텍스트 박스: 확정 텍스트(흰색) + 인식 중 부분(회색 이탤릭)
- STT partial 결과로 키워드 스캔 → 위험도 즉각 상승 반응 (단, 내려가지 않음, 최대 30% 캡)

### 목표 UI (미구현)
- 카테고리별 감지 횟수 표시
- 고령자 접근성: 최소 글자 크기 16sp, 진동 경고

## 성능 목표
- 슬라이딩 윈도우: 10ms 이하
- KoELECTRA TFLite 추론: 80ms 이하
- 모델 파일 크기: 20MB 이하 (TFLite 변환 후)
- F1-Score: 87% 이상
- 오탐률: 10% 이하

## 핵심 제약사항
- 음성 데이터 외부 서버 전송 금지 (온디바이스, 가족 알림 제외)
- 통화 음성 디바이스 저장 금지
- Android 8.0 (API 26) 이상 지원
- 통화 캡처: 스피커폰 방식 (MVP), 추후 접근성 서비스 검토
- 가족 알림: Firebase 백엔드 필요 (FCM)
- 서버: 가족 알림용 최소 백엔드만 (나머지 완전 온디바이스)

## 개발 환경
- Python 3.11 / uv
- Docker (Dockerfile, docker-compose.yml, requirements.txt 구성 완료)
- VSCode + Claude Code

## Docker 환경
```bash
docker build -t vp-detector .
docker-compose up -d
docker exec -it vp-detector bash
```

requirements.txt 핵심 버전:
- numpy>=2.0
- onnx==1.15.0
- protobuf<6.0dev,>=5.26.1
- onnx2tf
- tensorflow

## TFLite 변환 현황
- model_float32.tflite: 430MB (추론 동작 확인됨)
- model_float16.tflite: 215MB (CPU ADD 미지원)
- model_int8_no_erf.tflite: **현재 사용 중** (erf 연산 제거 버전, 실기기 추론 확인)
- 목표: int8 양자화로 50~100MB 이하

## 미사용 데이터 (2차 목표용)
- 감정분류 대화 음성 데이터 (14GB, AI Hub)
  → 용도: 이상탐지 AutoEncoder 정상 패턴 학습용
  → 사용 시점: 2차 목표 이상탐지 추가 시
  → 처리 방법: Whisper small로 텍스트 변환 후 사용

## 다음 작업 순서
1. ~~train.py — KoELECTRA 멀티라벨 파인튜닝~~ (완료)
2. ~~evaluate.py — 카테고리별 F1-Score 확인~~ (완료)
3. ~~convert.py — TFLite int8 변환~~ (model_int8_no_erf.tflite 완료)
4. ~~Flutter 앱 기본 구조 + STT 연동~~ (완료)
5. ~~TFLite 연동 (tflite_flutter, allocateTensors, Int64List)~~ (완료)
6. UI 개선 — 카테고리 감지 횟수, 고령자 접근성, 통화 종료 결과 화면
7. 딥페이크 탐지 통합 (통화 시작 시 자동 3초 체크 + 수동 버튼)
8. 가족 알림 서비스 (FCM 연동)
9. 전화 자동 감지 및 앱 자동 실행
