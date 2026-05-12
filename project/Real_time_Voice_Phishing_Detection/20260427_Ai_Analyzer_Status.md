# 보이스피싱 탐지 앱 — 현황 요약

## 진행 현황

| 단계 | 내용 | 상태 |
|------|------|------|
| 데이터 수집 | 금감원 MP4 104개 | ✅ 완료 |
| STT 전처리 | Whisper small → 텍스트 변환 | ✅ 완료 |
| 데이터 증강 | GPT-4o-mini 359개 생성 | ✅ 완료 |
| 라벨링 | 키워드 빈도 기반 자동 라벨링 | ✅ 완료 |
| 멀티라벨 변환 | 복합 제거 → [기관사칭, 금전요구, 개인정보] | ✅ 완료 |
| 데이터 분할 | train 451 / val 56 / test 57 | ✅ 완료 |
| 파인튜닝 | KoELECTRA 멀티라벨 학습 | ✅ 완료 |
| ONNX 변환 | PyTorch → ONNX | ✅ 완료 |
| TFLite 변환 | ONNX → TFLite float32 (430MB) | ✅ 완료 |
| TFLite 추론 검증 | 테스트 문장 10개 추론 확인 | ✅ 완료 |
| int8 양자화 | 크기 축소 (목표 50~100MB) | 🔲 Docker에서 재시도 |
| Docker 환경 | Dockerfile / docker-compose.yml | 🔲 구성 중 |


---

## 현재 보유 파일

```
model_float32.tflite   430MB  ← 추론 동작 확인
model_float16.tflite   215MB  ← CPU ADD 미지원
model.onnx             원본
train_ml.json          451개
val_ml.json             56개
test_ml.json            57개
multilabel_all.json    564개
```

---

## 데이터 구성

```
금감원 원본 104개  +  GPT 증강 359개  +  윤리검증(정상) 101개
                    ↓ 멀티라벨 변환
              총 564개 → train/val/test 분할
```

| 카테고리 | 데이터 수 |
|----------|-----------|
| 기관사칭 포함 | 168개 |
| 금전요구 포함 | 128개 |
| 개인정보 포함 | 153개 |
| 정상 (전부 0) | 164개 |

---

## 라벨 구조

```python
[기관사칭, 금전요구, 개인정보]
[1, 0, 0]  # 기관사칭만
[1, 1, 0]  # 기관사칭 + 금전요구
[0, 0, 0]  # 정상
```

---

## 다음 작업

```
1. Docker → int8 양자화 재시도
2. stt.py on_transcribed → analyzer.analyze() 연결
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 1차 필터 | 슬라이딩 윈도우 (키워드, 창 20단어) |
| 분류 모델 | KoELECTRA (monologg/koelectra-base-v3-discriminator) |
| 배포 포맷 | TFLite (float32 → int8 목표) |


