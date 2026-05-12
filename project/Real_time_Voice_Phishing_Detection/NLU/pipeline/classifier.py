import sys
from dataclasses import dataclass
from pathlib import Path

import torch
from transformers import AutoTokenizer, ElectraForSequenceClassification

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_VERSION

MODEL_DIR  = Path(__file__).parent.parent / f"models/koelectra-finetuned-{DATA_VERSION}/best"
MAX_LENGTH = 128
THRESHOLD  = 0.5

LABEL_COLS = ["기관사칭", "금전요구", "개인정보"]


@dataclass
class ClassificationResult:
    scores: dict[str, float]   # {"기관사칭": 0.92, "금전요구": 0.88, "개인정보": 0.05}
    risk_score: float           # 0.0 ~ 1.0 (카테고리 최대값)
    detected: list[str]         # 임계값 초과 카테고리 목록

    def is_phishing(self) -> bool:
        return len(self.detected) > 0

    def risk_percent(self) -> int:
        return int(self.risk_score * 100)


class KoELECTRAClassifier:
    """
    멀티라벨 KoELECTRA 분류기.
    기관사칭 / 금전요구 / 개인정보를 독립적으로 판단.
    """

    def __init__(self, model_dir: str | Path | None = None, device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        path = Path(model_dir) if model_dir else MODEL_DIR

        if not path.exists():
            raise FileNotFoundError(
                f"모델 없음: {path}\n먼저 train.py를 실행하세요."
            )

        print(f"  KoELECTRA 멀티라벨 모델 로딩... ({self.device})")
        self.tokenizer = AutoTokenizer.from_pretrained(str(path))
        self.model = ElectraForSequenceClassification.from_pretrained(str(path))
        self.model.to(self.device)
        self.model.eval()

    @torch.inference_mode()
    def classify(self, text: str) -> ClassificationResult:
        enc = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        ).to(self.device)

        logits = self.model(**enc).logits[0]
        probs  = torch.sigmoid(logits).cpu().tolist()

        scores   = {col: round(p, 4) for col, p in zip(LABEL_COLS, probs)}
        detected = [col for col, p in scores.items() if p >= THRESHOLD]
        risk     = max(probs)

        return ClassificationResult(
            scores=scores,
            risk_score=risk,
            detected=detected,
        )

    @torch.inference_mode()
    def classify_batch(self, texts: list[str]) -> list[ClassificationResult]:
        enc = self.tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
            padding=True,
        ).to(self.device)

        logits_batch = self.model(**enc).logits
        probs_batch  = torch.sigmoid(logits_batch).cpu().tolist()

        results = []
        for probs in probs_batch:
            scores   = {col: round(p, 4) for col, p in zip(LABEL_COLS, probs)}
            detected = [col for col, p in scores.items() if p >= THRESHOLD]
            results.append(ClassificationResult(
                scores=scores,
                risk_score=max(probs),
                detected=detected,
            ))
        return results
