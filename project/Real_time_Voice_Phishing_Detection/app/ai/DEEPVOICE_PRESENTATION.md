# 딥보이스 탐지 모델 개발 과정 발표 자료

---

## 1. 역할 및 목표

| 항목 | 내용 |
|------|------|
| 담당 역할 | 딥보이스(AI 합성 음성) 탐지 모델 개발 |
| 핵심 목표 | 실시간 보이스피싱 통화에서 TTS(AI 목소리)와 실제 사람 목소리를 구분 |
| 배포 환경 | 온디바이스 Android APK (서버 없음, TFLite 모델) |
| 핵심 지표 | EER (Equal Error Rate) — 낮을수록 좋음 |

---

## 2. 모델 구조

### RawNet2
- **원시 파형(raw waveform)을 직접 입력**받는 딥보이스 탐지 모델
- 입력: `(1, 64600)` — 16kHz 기준 약 4초 음성
- 출력: `[진짜 확률, 가짜 확률]`
- 구조: SincNet 필터뱅크 → 잔차 블록(1D CNN) → GRU → FC
- ASVspoof 2019 사전학습 가중치 로드 후 **한국어 데이터로 파인튜닝**

### 배포 파이프라인
```
korean_model.pth (PyTorch)
    ↓ torch.onnx.export
rawnet2.onnx
    ↓ onnx2tf
korean_model.tflite  ← 앱에서 사용
```

---

## 3. 학습 데이터 구성 변화

### 3-1. 처음 시작 (v1)
| 분류 | 데이터 | 수량 |
|------|--------|------|
| Fake | Clova TTS (50개 보이스피싱 텍스트 × 다양한 화자/속도/피치) | ~1,008개 |
| Genuine | 일반 한국어 음성 | ~1,008개 |

> **문제:** Clova TTS 특유의 패턴만 학습 → 다른 TTS(Qwen3, DeeVid 등)는 탐지 못함

---

### 3-2. 데이터 추가 (v2)
| 추가 데이터 | 이유 |
|------------|------|
| `genuine/real_calls/` — 실제 전화 통화 녹음 | 실제 전화 환경 음성 학습 |
| `genuine/news/` — 뉴스 음성 | 다양한 진짜 음성 확보 |
| Qwen3-TTS 300개 (train 240 + test 60) | 고품질 TTS 탐지 추가 |
| speaker_TTS 25개 | 특정 화자 TTS 탐지 |
| DeeVid TTS | 영상 합성 기반 TTS 탐지 |

> **결과:** 다양한 TTS 종류 탐지 가능, 전화 환경 음성 학습

---

### 3-3. 최종 데이터 구성
```
genuine: 11,000개
├── real_calls (전화 녹음)  ← 항상 전부 포함
├── news (뉴스 음성)        ← 항상 전부 포함
└── 기타 한국어 음성

fake: 11,000개
├── Clova TTS (~10,000개)
├── Qwen3-TTS (240개)      ← 항상 전부 포함
├── speaker_TTS (25개)     ← 항상 전부 포함
└── DeeVid TTS

총합: 22,000개
train: 17,229개 / dev: 4,771개
```

---

## 4. Augmentation 전략 변화

### 처음 → 최종 비교

| 기법 | 처음 | 최종 | 추가 이유 |
|------|------|------|-----------|
| Speed perturbation | ❌ | ✅ 20% | 속도 변형에 강건하게 |
| Volume 조절 | ❌ | ✅ 80% | 볼륨 차이 대응 |
| Phone channel | ❌ | ✅ fake 75% / genuine 40% | 전화 코덱 압축 시뮬레이션 |
| Background noise | ❌ | ✅ fake 35% / genuine 25% | 실전 잡음 환경 대응 |
| Reverb | ❌ | ✅ 20% | 스피커 재녹음 시뮬레이션 |
| **MP3 압축** | ❌ | ✅ 30% | **MP3 코덱 환경 대응** |

> **핵심 원칙:** train에만 augmentation 적용, dev는 클린 로드 → EER 측정 일관성 유지

---

## 5. 성능 지표 (EER) 변화

| Epoch | Loss | Acc | dev EER | 비고 |
|-------|------|-----|---------|------|
| 01/20 | 0.4297 | 86.76% | 5.86% | 학습 시작 |
| 02/20 | 0.1848 | 92.88% | 4.10% | |
| 03/20 | 0.1457 | 94.40% | 2.67% | |
| 04/20 | 0.1195 | 95.44% | 2.19% | |
| 05/20 | 0.1030 | 96.31% | 1.81% | |
| **최종** | — | — | **1.03%** | **best checkpoint** |

> EER 1.03% = 가짜를 진짜로 놓치는 비율과 진짜를 가짜로 잘못 잡는 비율이 균형을 이루는 지점이 1.03%

---

## 6. 주요 시행착오와 해결 과정

### ❌ 문제 1: Dev Set 오염 → EER 신뢰 불가
- **상황:** EER이 epoch마다 들쑥날쑥, 신뢰할 수 없는 수치
- **원인:** augmentation이 train/dev 구분 없이 적용 → 매 epoch마다 다른 입력
- **해결:** `is_train` 플래그 추가, dev는 항상 클린 로드

```python
if self.is_train:
    wav = _augment(wav, label)
```

---

### ❌ 문제 2: 같은 화자 데이터 리키지 → EER 0%처럼 부풀려짐
- **상황:** 같은 화자 음성이 train/dev 양쪽에 들어가면 EER이 비정상적으로 낮아짐
- **원인:** 데이터 분리를 랜덤으로만 하면 같은 화자가 양쪽에 섞임
- **해결:** holdout 화자(`nkyunglee`, `njooahn`) dev 전용 완전 격리

```
전체 샘플
├── holdout 화자 → dev 고정 (464개)
└── 나머지 → 80/20 랜덤 분리
    ├── 80% → train
    └── 20% + holdout → dev
```

---

### ❌ 문제 3: 스피커 재녹음 시나리오 탐지 실패
- **상황:** TTS를 스피커로 출력 → 휴대폰으로 재녹음 → 모델이 진짜로 판별
- **원인:** 재녹음 시 실내 잔향이 TTS 아티팩트를 덮어버림
- **해결:** Reverb augmentation 추가 (잔향 시뮬레이션)

---

### ❌ 문제 4: Qwen3-TTS 탐지 실패
- **상황:** 고품질 Qwen3-TTS가 진짜로 판별됨
- **원인:** 기존 Clova TTS와 분포가 달라 학습 데이터에 없는 패턴
- **해결:** Qwen3-TTS 300개 생성 후 학습 데이터 추가, 6개 카테고리로 다양화

| 카테고리 | 설명 |
|----------|------|
| clean | 원본 |
| phone | 전화채널 시뮬레이션 |
| compress | MP3 압축 |
| reverb | 잔향 효과 |
| emotion | 감정/억양 변형 |
| phone_compress | phone + compress 복합 |

---

### ❌ 문제 5: PTH vs TFLite 결과 불일치
- **상황:** PTH 모델 98% 가짜 → TFLite 모델 진짜로 판별
- **원인:** TFLite 추론 시 phone_channel 시뮬레이션 누락
- **해결:** 추론 코드에 `phone_channel()` 추가

```python
def phone_channel(wav):
    down = scipy.signal.resample_poly(wav, 1, 2)  # 16kHz → 8kHz
    up   = scipy.signal.resample_poly(down, 2, 1)  # 8kHz → 16kHz
    return up
```

---

### ❌ 문제 6: MP3 파일 탐지 저하
- **상황:** DeeVid TTS MP3 파일이 가짜로 잘 안 잡힘
- **원인:** 학습은 WAV로, 테스트는 MP3 → MP3 코덱이 TTS 아티팩트 손상
- **해결:** MP3 압축 augmentation 추가 (30% 확률)

---

## 7. 현재 한계 및 향후 방향

| 한계 | 설명 |
|------|------|
| 4초 입력 고정 | RawNet2 모델 구조상 변경 불가, 슬라이딩 윈도우로 대응 |
| 학습 안 된 TTS | 새로운 TTS 엔진 나오면 재학습 필요 |
| MP3 탐지율 | MP3 augmentation 재학습으로 개선 예정 |

| 향후 방향 | 내용 |
|-----------|------|
| MP3 augmentation 재학습 | DeeVid 등 MP3 환경 탐지율 향상 |
| 실제 통화 데이터 추가 | real_calls 폴더 데이터 확충 |
| 앱 통합 | TFLite 모델을 Flutter 앱에 슬라이딩 윈도우 방식으로 통합 |

---

## 8. 요약

```
ASVspoof 사전학습 모델
    ↓ 한국어 Clova TTS 1,008개로 파인튜닝
    → Clova TTS만 탐지 가능 (EER ~6%)

    ↓ Qwen3-TTS, DeeVid, speaker_TTS 추가
    → 다양한 TTS 탐지 가능

    ↓ Augmentation 강화 (phone, reverb, noise)
    → 전화 환경, 재녹음 시나리오 대응

    ↓ 데이터 22,000개 + holdout 분리 + dev 클린 로드
    → EER 1.03% 달성

    ↓ PTH → TFLite 변환
    → 온디바이스 안드로이드 앱 배포
```
