# RawNet2 한국어 딥보이스 탐지 모델 — 개발 기록

## 1. 프로젝트 개요

**목표:** 실시간 보이스피싱 탐지를 위해, 전화 통화 중 AI 생성(TTS) 음성과 실제 사람 음성을 구분  
**모델:** RawNet2 (raw waveform anti-spoofing, ~70MB)  
**핵심 지표:** EER (Equal Error Rate) — 낮을수록 좋음  
**환경:** Google Colab (GPU), Google Drive 데이터 저장

---

## 2. 모델 아키텍처

- **RawNet2**: 원시 파형(raw waveform)을 직접 입력받는 딥보이스 탐지 모델
- 입력: `(batch, 1, 64600)` — 16kHz 기준 약 4초
- 출력: `(batch, 2)` — [진짜 확률, 가짜 확률]
- SincNet 필터뱅크 + 잔차 블록(1D Conv) + GRU + FC
- 사전학습 가중치(`best_model.pth`) 로드 후 한국어 데이터로 파인튜닝

---

## 3. 데이터 구성

### 3-1. Genuine (진짜 음성)
| 폴더 | 내용 | 비고 |
|------|------|------|
| `genuine/real_calls/` | 실제 전화 통화 녹음 | 항상 전부 포함 |
| `genuine/news/` | 뉴스 음성 | 항상 전부 포함 |
| `genuine/` (기타) | 일반 한국어 음성 | max_samples 제한 |

### 3-2. Fake (가짜 TTS)
| 출처 | 수량 | 비고 |
|------|------|------|
| Clova TTS | ~1008개 | 50개 피싱 텍스트 × 다양한 화자/속도/피치 |
| Qwen3-TTS | 240개 | 6개 카테고리 × 40개 train |
| 기타 TTS | 다수 | max_samples 제한 |

### 3-3. Qwen3-TTS 6개 카테고리 (각 40개 train / 10개 test)
| 카테고리 | 처리 방식 |
|----------|-----------|
| `clean` | 원본 그대로 |
| `phone` | 전화채널 시뮬레이션 (16kHz→8kHz→16kHz) |
| `compress` | MP3 압축 시뮬레이션 |
| `reverb` | 잔향 효과 (스피커 재녹음 시뮬레이션) |
| `emotion` | 감정/억양 instruct 적용 |
| `phone_compress` | phone + compress 복합 |

---

## 4. 학습 파이프라인

### 4-1. 데이터 분리 전략 (Speaker-based Split)
- **문제:** 같은 화자 음성이 train/dev 양쪽에 들어가면 EER 0%처럼 부풀려짐 (데이터 리키지)
- **해결:** Clova holdout 화자 (`nkyunglee`, `njooahn`)를 dev 전용으로 완전 격리

```
전체 샘플
├── holdout 화자 (nkyunglee, njooahn) → dev 고정
└── 나머지 → 80/20 랜덤 분리
    ├── 80% → train
    └── 20% + holdout → dev
```

### 4-2. Augmentation 전략
| 기법 | 확률 | 세부사항 |
|------|------|----------|
| Speed perturbation | 20% | ±5%, `librosa.effects.time_stretch` |
| Volume | 80% | 0.7 ~ 1.3배 |
| Phone channel | fake: 75% / genuine: 40% | 16kHz→8kHz→16kHz |
| Background noise | fake: 35% / genuine: 25% | SNR 18~30dB |
| Reverb | 20% | 2~5개 딜레이, 잔향 시뮬레이션 |

- **train에만 augmentation 적용** (`is_train=True/False` 플래그)
- **dev는 항상 클린 로드** → EER 측정 기준 일관성 유지

### 4-3. 하이퍼파라미터
```
MAX_SAMPLES = 11000   (클래스당)
BATCH_SIZE  = 16
EPOCHS      = 20
LR          = 1e-5
optimizer   = Adam (weight_decay=1e-4)
scheduler   = CosineAnnealingLR
loss        = CrossEntropyLoss
```

### 4-4. Qwen3-TTS 확정 포함 로직
- `fake_dir/qwen_tts/train/` 폴더는 `max_samples` 제한과 무관하게 전부 포함
- genuine의 `real_calls`, `news` 보장 방식과 동일한 패턴

---

## 5. 시행착오 기록

### ❌ 시행착오 1: `dict.encode('utf-8')` 에러 (Clova TTS)
- **상황:** Clova TTS API 호출 시 `data.encode('utf-8')` 에러 발생
- **원인:** `data`가 dict인데 dict에는 `.encode()` 메서드 없음
- **해결:** `requests.post(url, data=data)` 로 직접 전달

---

### ❌ 시행착오 2: Speed Perturbation 피치 변경 문제
- **상황:** `F.interpolate(scale_factor=factor)`로 속도 변환 시 피치도 같이 변함
- **원인:** interpolate는 단순 리샘플링 → 속도+피치 동시 변경
- **해결:** `librosa.effects.time_stretch(wav_np, rate=factor)` 사용 → 피치 유지하며 속도만 변환

---

### ❌ 시행착오 3: Dev Set Augmentation 오염
- **상황:** EER이 epoch마다 들쑥날쑥, 신뢰할 수 없는 수치
- **원인:** `_augment()`가 train/dev 구분 없이 적용됨 → 매 epoch마다 다른 입력
- **해결:** `is_train` 플래그 추가, dev는 항상 클린 로드

---

### ❌ 시행착오 4: Holdout 화자 수 부족 (105개 → 462개)
- **상황:** holdout 화자(`nkyunglee`, `njooahn`)가 dev에 105개밖에 안 들어감
- **원인:** `MAX_SAMPLES=5000`으로 제한 시 shuffle 후 잘려서 holdout 파일 일부 누락
- **해결 1:** `MAX_SAMPLES=11000`으로 증가
- **해결 2:** holdout 화자 TTS 추가 생성 (240개 추가)

---

### ❌ 시행착오 5: 스피커 재녹음 시나리오 탐지 실패
- **상황:** TTS를 컴퓨터 스피커로 출력 → 휴대폰으로 재녹음 → 모델이 진짜로 판별 (24.80%)
- **원인:** 재녹음 시 실내 잔향이 TTS 아티팩트를 덮어버림
- **해결:** `_add_reverb()` 함수 추가, 20% 확률로 잔향 시뮬레이션

```python
def _add_reverb(wav):
    for _ in range(random.randint(2, 5)):
        delay = random.randint(400, 3000)  # 25~187ms @ 16kHz
        decay = random.uniform(0.1, 0.4)
        if delay < wav.shape[-1]:
            result[:, delay:] += wav[:, :-delay] * decay
```

---

### ❌ 시행착오 6: Qwen3-TTS 탐지 실패
- **상황:** Qwen3-TTS 생성 음성이 진짜로 판별됨
- **원인:** 고품질 TTS라 기존 학습 데이터(Clova TTS)와 분포가 다름
- **해결:** Qwen3-TTS 300개(train 240 + test 60) 생성 후 학습 데이터 추가

---

### ❌ 시행착오 7: Threshold 조정
- **상황:** 가짜를 진짜로 놓치는 False Negative가 많음
- **변경:** `prob > 0.5` → `prob > 0.4` (더 공격적으로 가짜 판별)
- **트레이드오프:** False Positive(진짜를 가짜로) 증가, False Negative 감소

---

### ❌ 시행착오 8: TFLite 변환 — onnx-tf 실패
- **상황:** `pip install onnx-tf` 시 `tensorflow-addons` 의존성 충돌
- **원인:** TF 2.13+ 에서 tensorflow-addons 지원 중단
- **해결:** `onnx2tf` (onnx-tf 후속 패키지) 사용

---

### ❌ 시행착오 9: TFLite 추론 shape 불일치
- **상황:** `ValueError: Dimension mismatch. Got 1 but expected 64600`
- **원인:** onnx2tf가 PyTorch channels-first `(1,1,64600)` → TF channels-last `(1,64600,1)` 로 자동 변환
- **해결:** 추론 시 입력 shape을 `(1, 64600, 1)` 로 변경

---

## 6. 모델 변환 (pth → tflite)

```
korean_model.pth (PyTorch)
    ↓ torch.onnx.export (opset 11)
rawnet2.onnx
    ↓ onnx2tf.convert
rawnet2_tf/ (TF SavedModel + .tflite 자동 생성)
    ↓ shutil.copy
korean_model.tflite  ← 최종 배포용
```

- **finetune.py 맨 아래에 변환 코드 추가** → 학습 완료 시 pth + tflite 동시 저장
- TFLite 추론 시 전처리: `wav.reshape(1, 64600, 1)` (channels-last)

---

## 7. 현재 학습 결과 (진행 중)

```
genuine=11000, fake=11000 (qwen3=240, other=10760), total=22000
train=17231, dev=4769 (holdout 462개 + random 4307개)
사전학습: best_model.pth 로드

Epoch 01/20 | loss: 0.4297 | acc: 0.8676 | dev EER: 5.86%
Epoch 02/20 | loss: 0.1848 | acc: 0.9288 | dev EER: 4.10%
Epoch 03/20 | loss: 0.1457 | acc: 0.9440 | dev EER: 2.67%
Epoch 04/20 | loss: 0.1195 | acc: 0.9544 | dev EER: 2.19%
Epoch 05/20 | loss: 0.1030 | acc: 0.9631 | dev EER: 1.81%  ← 현재
```

---

## 8. 파일 구조

```
RealTimeVoicePhishing/
├── model.py                  # RawNet2 모델 정의
├── korean_dataset.py         # 데이터셋 + augmentation
├── finetune.py               # 파인튜닝 + TFLite 자동 변환
└── testmain.py               # 추론 테스트 (pth 버전)

checkpoints/
├── best_model.pth            # ASVspoof 사전학습 가중치
├── korean_model.pth          # 파인튜닝 최적 가중치
└── korean_model.tflite       # 배포용 TFLite 모델
```

---

## 9. 다음 단계

- [ ] 20 epoch 완료 후 최종 EER 확인
- [ ] 스피커 재녹음 시나리오 재테스트 (new korean_model.pth)
- [ ] Qwen3-TTS 탐지율 확인
- [ ] 앱에 TFLite 모델 통합
