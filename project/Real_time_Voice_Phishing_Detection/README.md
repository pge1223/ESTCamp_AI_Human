# 실시간 보이스피싱 탐지 앱 — VoiceGuard

> 고령자를 주요 대상으로 한 실시간 보이스피싱 탐지 Android 앱

---

## 1. 주제 및 목적

보이스피싱 피해의 주된 대상은 디지털 기기에 익숙하지 않은 고령자입니다. 본 프로젝트는 통화 중 음성을 실시간으로 분석해 보이스피싱 위험을 자동 감지하고, 시각적·청각적 경고를 통해 피해를 예방하는 Android 앱입니다.

- 별도의 서버 전송 없이 **온디바이스**에서 모든 분석 수행 (개인정보 보호)
- 통화 중 자동 탐지 → 경고 팝업 → 가족 알림까지 연결되는 완결된 안전망 제공
- 고령자 접근성을 고려한 직관적 UI 설계 (큰 글자, 색상 단계, 진동 경고)

---

## 2. UI 설계

Flutter(Dart) 기반 라이트 테마 UI. 위험도를 직관적으로 파악할 수 있도록 색상 단계와 애니메이션을 중심으로 설계했습니다.

### 주요 화면

| 화면 | 설명 |
|------|------|
| **홈 화면** | 오늘 탐지 건수, 위험·주의·안전 통화 통계, 주간 차트를 대시보드 형식으로 표시 |
| **통화 화면** | 실시간 위험도 인디케이터 + STT 자막 + 카테고리 칩 + 딥보이스 탐지 버튼 |
| **이력 화면** | 과거 통화 기록 및 분석 결과 목록 |
| **통계 화면** | 기간별 통화 분석 통계 |
| **설정 화면** | 알림·민감도·가족 연락처 설정 |

### 위험도 색상 단계

| 단계 | 위험도 | 색상 |
|------|--------|------|
| 안전 | 0 ~ 10% | 초록 |
| 주의 | 11 ~ 30% | 노랑 |
| 경고 | 31 ~ 60% | 주황 |
| 위험 | 61% 이상 | 빨강 |

- 통화 화면 위험도 바: `TweenAnimationBuilder` (600ms easeOut) 로 부드러운 애니메이션
- 위험도 70% 초과 시 전체화면 경고 팝업 1회 표시
- **위험도 단조 증가**: 한 번 올라간 위험도는 통화 중 내려가지 않음 (`_lockedRisk`)

---

## 3. 주요 기능

### 3-1. STT (음성 인식)

- Android `SpeechRecognizer` API (`speech_to_text` 패키지) 사용
- partial 결과(인식 중)와 final 결과(확정) 모두 실시간 처리
- STT `error_busy` 발생 시 지수 백오프로 자동 재시작
- STT 중단 감지 watchdog 타이머로 연속 인식 유지

### 3-2. NLU (자연어 기반 보이스피싱 분석)

슬라이딩 윈도우 키워드 필터 + KoELECTRA TFLite 모델 2단계 파이프라인.

```
STT 텍스트
  ↓ 키워드 필터 (고위험 15점 / 저위험 7점 / URL 30점)
    ↳ 15점 미만 → 위험도 최대 30% 캡
  ↓ 15점 이상이면
KoELECTRA TFLite 추론 (~80ms, 온디바이스)
  ↓
위험도 % 출력 (기관사칭 / 금전요구 / 개인정보 3개 카테고리)
```

복합 탐지 보정 (`maxProb`):

```
위험도 = max(probs) + (0.5 이상 라벨 수 - 1) × 5%
```

> NLU 상세는 [4. 담당 파트](#4-담당-파트--nlu) 참고

### 3-3. 딥보이스 탐지 (`app/ai/`)

AI 합성음성(딥페이크) 여부를 탐지하는 독립 모듈.

- 모델: **RawNet2** (TFLite 변환, `korean_model.tflite`)
- 입력: 네이티브 `PcmCapturePlugin`으로 캡처한 16kHz PCM 원시 음성
- 출력: genuine(실제 음성) / spoof(합성 음성) 확률
- 탐지 임계값: 0.5 이상 시 딥보이스 경고
- RMS VAD(음성 활성 감지)로 묵음 구간 필터링, W2 veto로 오탐 억제
- 학습: `app/ai/train.py`, `app/ai/model.py` (RawNet2 구조 정의)

---

## 4. 담당 파트 — NLU

**담당자**: 이재인 (pge)
**작업 위치**: `NLU/`

### 4-1. 모델 개요

| 항목 | 내용 |
|------|------|
| 베이스 모델 | `monologg/koelectra-base-v3-discriminator` |
| 분류 방식 | 멀티라벨 (Multi-label Classification) |
| 출력 레이블 | `[기관사칭, 금전요구, 개인정보]` 3개 독립 판단 |
| 손실 함수 | BCEWithLogitsLoss |
| 추론 임계값 | Sigmoid ≥ 0.5 |
| 배포 형식 | TFLite int8 양자화 (`model_int8_no_erf.tflite`) |

### 4-2. 학습 데이터 구성 (v5 기준)

| 구분 | 출처 | 수량 |
|------|------|-----:|
| 피싱 ① | 금감원 보이스피싱 MP4 104편 → Whisper STT → GPT-4o-mini 증강 | 1,441개 |
| 피싱 ② | KBS 공개 보이스피싱 시나리오 → GPT-4o-mini 증강 | 69개 |
| 피싱 ③ | 탐문형 집중 증강 (v5 신규) | 500개 |
| 정상 ① | AI Hub 감성 음성합성 데이터 (일상 대화체·친절체) | 13,922개 |
| 정상 ② | AI Hub 콜센터 질의응답 (K쇼핑·금융 콜센터) | 6,500개 |
| **합계** | | **22,432개** |

분할: Train 70% / Val 10% / Test 20%

### 4-3. v5 성능 평가

#### 학습셋 테스트 결과

| 카테고리 | Precision | Recall | F1 |
|----------|----------:|-------:|---:|
| 기관사칭 | 0.99 | 1.00 | **0.99** |
| 금전요구 | 0.89 | 0.90 | **0.90** |
| 개인정보 | 0.89 | 0.95 | **0.92** |
| **macro avg** | **0.92** | **0.95** | **0.94** |

> F1 macro = **0.94** — 목표 0.87 초과 달성

#### 혼합 테스트셋 결과

| 테스트셋 | 샘플 수 | Recall | Precision | F1 | 오탐 |
|----------|--------:|-------:|----------:|---:|-----:|
| mixed_test_03 (탐문형 검증) | 1,057 | 94.7% | 100.0% | **97.3%** | 0건 |
| mixed_test_v4 (일반 혼합) | 4,390 | 69.0% | 99.5% | **81.5%** | 1건 |

> mixed_test_v4 Recall 69.0%는 키워드 필터 미통과 FN이 원인 (KoELECTRA 미실행). KoELECTRA 트리거된 샘플 기준으로는 Precision·Recall 모두 99.5%.

### 4-4. 버전 이력

| 버전 | 주요 변경 |
|------|----------|
| v1 | KoBERT 단일 클래스 분류 (초기 후보, 이후 대체) |
| v2 | KoELECTRA 멀티라벨 전환 |
| v3 | 정상 TTS 데이터 13,922개 추가 |
| v4 | 정상 콜센터 데이터 추가, 전체 22,432개 |
| **v5** | 탐문형 피싱 500개 집중 보강 — v4 미탐 해결 |
| v6 | Hard Negative 정상 데이터 1,500개 추가 (오탐 감소 목적, 평가 진행 중) |

> 상세 내용: [`NLU/docs/model_report_v5.md`](NLU/docs/model_report_v5.md), [`NLU/docs/model_report_v6.md`](NLU/docs/model_report_v6.md)

### 4-5. 모델 학습 환경

Google Colab (GPU) 환경에서 학습 및 변환.

| 작업 | 노트북 |
|------|--------|
| KoELECTRA 파인튜닝 | `NLU/model_build/train_colab.py` (Colab 실행) |
| 피싱 데이터 증강 | `phishing_augment.ipynb` |
| Hard Negative 증강 | `normal_hardneg_augment.ipynb` |
| TFLite 변환 (float32 / int8) | `NLU/model_build/convert_int8_docker.py` (Docker) |

---

## 5. 실행 환경

| 항목 | 버전 |
|------|------|
| Flutter SDK | 3.x 이상 |
| Dart SDK | ^3.11.5 |
| Android | API 26 (Android 8.0) 이상 |
| Python | 3.11 / uv |
| 테스트 기기 | Android 실기기 권장 (에뮬레이터는 float16 미지원) |

### 모델 파일 배치 (필수)

용량 문제로 git에 포함되지 않습니다. 아래 파일을 `client/assets/`에 복사하세요.

```
client/assets/
├── model_int8_no_erf.tflite   ← KoELECTRA 피싱 탐지 (int8 양자화)
├── vocab.txt                  ← KoELECTRA 토크나이저 어휘
└── korean_model.tflite        ← RawNet2 딥보이스 탐지
```

### 실행

```bash
cd client
flutter pub get
flutter run
```

---

## 6. 출처

**KBS 보이스피싱 시나리오**
> KBS 뉴스. (2023, 9월 6일). [탐사K] 보이스피싱 전화, 들어봤더니. KBS. https://news.kbs.co.kr/news/pc/view/view.do?ncd=7632888

**AI Hub 감성 음성합성 데이터** (정상 TTS)
> 한국지능정보사회진흥원. (2021). 감성 및 발화스타일 동시 고려 음성 합성 데이터 [데이터셋]. AI Hub. https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=71349

**AI Hub 콜센터 질의응답** (K쇼핑·금융 콜센터)
> 한국지능정보사회진흥원. (2020). 콜센터 질의응답 데이터 [데이터셋]. AI Hub. https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=98

**금감원 보이스피싱 영상** (MP4 104편)
> 금융감독원. (2024). 보이스피싱 사례집. 금융감독원 보이스피싱지킴이. https://www.fss.or.kr/fss/bbs/B0000203/list.do?menuNo=200686
