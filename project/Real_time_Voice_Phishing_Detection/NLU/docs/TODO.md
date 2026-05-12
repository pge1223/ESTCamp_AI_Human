# TODO

> 마지막 업데이트: 2026-04-29

---

## 당장 할 것

- [x] **train.py — train_test_split 추가**
  - `SOURCE_FILES`에 원본 파일 추가 시 자동으로 train/val/test 분리
  - 예: `normal_tts.json` → `train_normal_tts.json`, `val_normal_tts.json`, `test_normal_tts.json`
  - `prepare_splits()` → `split_and_save()` 로 구현, 이미 존재하면 스킵

---

## 나중에 할 것

- [ ] **모델 재학습 (train.py)**
  - 학습 데이터: callcenter + normal_tts + phishing 통합
  - BCEWithLogitsLoss 멀티라벨 파인튜닝

---

## 완료

- [x] train.py — train_test_split 추가 (2026-04-29)
