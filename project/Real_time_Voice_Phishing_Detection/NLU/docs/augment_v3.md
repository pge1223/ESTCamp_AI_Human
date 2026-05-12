# augment_v3.py — 보이스피싱 데이터 증강 가이드

## 목적

기존 v2 학습 데이터는 출처와 라벨 방식이 혼재되어 있었음.
v3는 원본 데이터부터 다시 **멀티라벨로 통일**해서 증강.

## 원본 데이터

| 파일 | 개수 | 설명 |
|------|------|------|
| `data/raw/transcripts.json` | 104개 | 금융감독원 보이스피싱 MP4 → Whisper STT. 라벨은 "보이스피싱" 단일 |
| `data/raw/kbs_voicephishing_dataset.json` | 5개 시나리오 | 검1선/검2선/검3선/법무팀/수금 패턴. 이미 멀티라벨 |

## 증강 흐름

```
1단계: transcripts.json 104개
       → GPT-4o-mini로 멀티라벨 분류
       → [기관사칭, 금전요구, 개인정보] 조합 판별
       → data/v3/_transcripts_classified.json 중간 저장

2단계: 분류된 transcripts + kbs 5개 시나리오를 시드로
       → 카테고리 조합별 쿼터 맞춰 증강
       → data/v3/phishing_augmented_data.json 출력
```

## 출력 쿼터 (총 2,310개)

| 카테고리 조합 | 목표 |
|--------------|------|
| 기관사칭만 | 200개 |
| 금전요구만 | 200개 |
| 개인정보만 | 200개 |
| 기관사칭 + 금전요구 | 200개 |
| 기관사칭 + 개인정보 | 200개 |
| 금전요구 + 개인정보 | 200개 |
| 전부 [1,1,1] | 310개 |

## 출력 파일

```
data/v3/
  phishing_augmented_data.json     ← 최종 피싱 증강 데이터 (2,310개)
  _transcripts_classified.json     ← 1단계 중간 산출물 (재실행 시 재사용)
```

출력 포맷:
```json
[
  {"text": "...", "label": [1, 0, 0], "source": "transcripts_aug"},
  {"text": "...", "label": [1, 1, 1], "source": "kbs_aug"},
  ...
]
```

## 실행 방법

### 로컬
```bash
uv run python model_build/augment_v3.py
```

### Colab
```python
!pip install openai tqdm

# BASE 경로 수정 필요 (augment_v3.py 상단)
# BASE = Path("/content/drive/MyDrive/ai_analyzer")  # 예시

%run model_build/augment_v3.py
```

API Key는 환경변수로 설정하거나 실행 시 입력:
```bash
export OPENAI_API_KEY=sk-...
```

## 중단/재실행

- **50개마다 자동 저장** → 중단돼도 데이터 손실 없음
- **재실행하면 이어서 진행** → 이미 채워진 쿼터는 스킵
- `_transcripts_classified.json` 존재하면 1단계 GPT 분류 재사용

## 비용 추정 (GPT-4o-mini 기준)

| 단계 | API 호출 수 | 예상 비용 |
|------|------------|---------|
| 1단계 분류 (104개) | 104회 | ~$0.1 |
| 2단계 증강 (2,310개, 배치 10개) | 231회 | ~$2~3 |
| **합계** | **~335회** | **~$3~4** |

## 다음 단계

증강 완료 후 train.py의 SOURCE_FILES에 추가:

```python
# model_build/train.py
SOURCE_FILES: list[Path] = [
    DATA_DIR / "phishing_augmented_data.json",
    DATA_DIR / "normal_tts.json",
    DATA_DIR / "normal_callcenter.json",
]
```

`prepare_splits()`가 각 파일을 자동으로 train/val/test 분할.

## 2차 증강 (나중에)

1차 학습 후 카테고리별 F1이 낮은 쪽이 있으면 해당 카테고리 위주로 추가 증강.
`QUOTA` 딕셔너리에서 해당 조합 개수만 늘리고 재실행하면 됨.
