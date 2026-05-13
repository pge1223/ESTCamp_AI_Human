# 딥보이스 탐지 모델 — 발표 슬라이드 초안
> 1슬라이드 ≈ 1분 | 개조식 | 총 10장

---

## [Slide 1] 주제 발굴 배경
**"왜 AI 목소리 탐지가 필요한가?"**

- 2024년 보이스피싱 피해액 **8,545억 원** (경찰청)
- 최근 범죄 수법 변화: 직접 통화 → **TTS(AI 합성 음성)** 활용
- AI 목소리는 사람이 듣기엔 구분 어려움
  - Clova, Qwen3, DeeVid 등 고품질 TTS 무료 공개
- **→ 통화 중 실시간으로 AI 목소리를 자동 탐지하는 기술 필요**

---

## [Slide 2] 나의 역할
**딥보이스 탐지 모델 개발 및 온디바이스 배포**

- 팀 전체 역할 분담
  - 딥보이스 탐지 (본인)
  - 보이스피싱 텍스트 분석 (KoELECTRA)
  - Flutter 앱 개발, 서버
- 본인 담당
  - RawNet2 모델 한국어 파인튜닝
  - 학습 데이터 수집 및 augmentation 설계
  - PTH → TFLite 변환 (온디바이스 배포)

---

## [Slide 3] 모델 선택 근거
**왜 RawNet2인가?**

- 기존 접근법: MFCC/스펙트로그램 등 특징 추출 후 분류
  - 전처리 과정에서 TTS 아티팩트 손실 가능성
- **RawNet2**: 원시 파형(raw waveform)을 직접 입력
  - TTS 특유의 미세한 패턴을 그대로 학습
  - ASVspoof 2019 대회 우수 성능 검증 모델
  - 입력: `(1, 64600)` — 16kHz × 4초
  - 출력: `[진짜 확률, 가짜 확률]`
- ASVspoof 사전학습 가중치 → **한국어 데이터 파인튜닝**

---

## [Slide 4] 1차 학습 — 기초 데이터
**처음엔 Clova TTS만 탐지 가능했음**

- 학습 데이터
  - Fake: Clova TTS ~1,008개 (50개 피싱 텍스트 × 다양한 화자/속도)
  - Genuine: 한국어 일반 음성 ~1,008개
- 결과 (EER 기준)

| 테스트 대상 | 탐지 여부 |
|------------|---------|
| Clova TTS | ✅ 탐지됨 |
| Qwen3 TTS | ❌ 진짜로 판별 |
| 스피커 재녹음 TTS | ❌ 진짜로 판별 |

- **→ 특정 TTS만 학습하면 다른 TTS는 못 잡는 문제 확인**

---

## [Slide 5] 데이터 고도화 과정
**어떤 음성을 못 잡는지 분석 → 데이터 추가**

- **Qwen3-TTS 탐지 실패** → 300개 생성 추가 (6개 환경 카테고리)

| 카테고리 | 설명 |
|----------|------|
| clean | 원본 |
| phone | 전화채널 시뮬레이션 |
| compress | MP3 압축 |
| reverb | 잔향 (재녹음 시뮬레이션) |
| emotion | 감정/억양 변형 |
| phone_compress | phone + compress 복합 |

- **실제 전화 녹음 추가** → `real_calls/`, `news/` 폴더 구성
- **DeeVid, speaker_TTS** 추가
- **최종: Fake 11,000개+ / Genuine 11,000개+ (총 22,000개+)**

---

## [Slide 6] Augmentation 전략
**다양한 실전 환경을 데이터로 시뮬레이션**

| 기법 | 확률 | 목적 |
|------|------|------|
| Speed perturbation ±5% | 20% | 말하는 속도 변화 대응 |
| Volume 조절 (0.7~1.3배) | 80% | 볼륨 차이 대응 |
| Phone channel (16kHz→8kHz→16kHz) | Fake 75% / Real 40% | 전화 코덱 압축 시뮬레이션 |
| Background noise (SNR 18~30dB) | Fake 35% / Real 25% | 실전 잡음 환경 |
| Reverb (딜레이 2~5개) | 20% | 스피커 재녹음 시뮬레이션 |
| **MP3 압축 시뮬레이션** | **30%** | **MP3 환경 탐지 대응** |

- **핵심 원칙**: train에만 적용, dev는 클린 로드 → EER 측정 일관성 유지

---

## [Slide 7] 성능 지표 변화 (EER)
**Equal Error Rate: 낮을수록 좋음**

| 단계 | EER | 주요 변경사항 |
|------|-----|-------------|
| Epoch 1 | 5.86% | 학습 시작 |
| Epoch 2 | 4.10% | |
| Epoch 3 | 2.67% | |
| Epoch 4 | 2.19% | |
| Epoch 5 | 1.81% | |
| **최종** | **1.03%** | **best checkpoint** |

- Accuracy: **96.31%** (Epoch 5 기준)
- EER 1.03% 의미
  - 가짜를 진짜로 놓치는 비율(FRR)과 진짜를 가짜로 잘못 잡는 비율(FAR)이 균형을 이루는 지점이 **1.03%**
  - ASVspoof 2019 Top 시스템 수준에 근접

---

## [Slide 8] 주요 시행착오
**실험하면서 발견한 문제들**

- **Dev Set 오염** → EER이 매 epoch 들쑥날쑥
  - 원인: augmentation이 dev에도 적용됨
  - 해결: `is_train` 플래그로 분리

- **화자 데이터 리키지** → EER 비정상적으로 낮게 측정
  - 원인: 같은 화자가 train/dev 양쪽에 존재
  - 해결: holdout 화자 2명을 dev 전용으로 완전 격리

- **PTH → TFLite 결과 불일치**
  - 원인: TFLite 추론 시 phone_channel 시뮬레이션 누락
  - 해결: 추론 코드에 `phone_channel()` 함수 추가

- **m4a 파일 학습 행**
  - 원인: audioread 백엔드 극도로 느림
  - 해결: 학습 전 m4a → wav 일괄 변환

---

## [Slide 9] 온디바이스 배포
**서버 없이 앱에서 직접 실행**

- 배포 방식: Android APK (Flutter) + TFLite
- 변환 과정
```
korean_model.pth → rawnet2.onnx → korean_model.tflite
```
- 주요 이슈 해결
  - channels-first (PyTorch) → channels-last (TFLite) shape 변환
  - 입력: `(1,1,64600)` → `(1,64600,1)`
- 추론 방식
  - **슬라이딩 윈도우**: 4초 단위, 0.5초 간격으로 반복 분석
  - **무음 구간 건너뜀**: RMS 에너지 기반 VAD
  - **20초 분석 후 최종 판단** 1회 출력

---

## [Slide 10] 결론 및 향후 과제

### 달성한 것
- RawNet2 한국어 파인튜닝 → **EER 1.03%**
- Clova / Qwen3 / DeeVid / speaker_TTS 탐지 가능
- 전화 환경, 재녹음, MP3 등 다양한 실전 시나리오 대응
- TFLite 변환 완료, 온디바이스 배포 가능 상태

### 남은 과제
- MP3 augmentation 재학습 → DeeVid MP3 탐지율 향상
- 새로운 TTS 엔진 등장 시 추가 학습 필요
- Flutter 앱과 실시간 통합 (슬라이딩 윈도우 Dart 구현)

---

> **기술 문서 별도 첨부**: `DEEPVOICE_PRESENTATION.md` (상세 시행착오, 코드 포함)