"""
KoELECTRA 파인튜닝 모델 변환 스크립트

[이 스크립트]  PyTorch → ONNX 변환 + 추론 검증
[Colab 단계]   ONNX → TFLite int8 양자화

TensorFlow가 Windows Python 3.14를 미지원하므로
TFLite 변환 + 양자화는 Google Colab에서 진행합니다.
"""
import sys
from pathlib import Path

import numpy as np
import onnx
import torch
from transformers import AutoTokenizer, ElectraForSequenceClassification

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE       = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))
from config import DATA_VERSION
MODEL_DIR  = BASE / f"models/koelectra-finetuned-{DATA_VERSION}/best"
OUTPUT_DIR = BASE / "models/onnx"
MAX_LENGTH = 128

LABEL_COLS    = ["기관사칭", "금전요구", "개인정보"]
THRESHOLD     = 0.5
TEST_SENTENCE = "저는 서울중앙지검 수사관입니다. 안전계좌로 즉시 송금해 주세요."


def mb(path: Path) -> str:
    return f"{path.stat().st_size / 1024 / 1024:.1f} MB"


def main() -> None:
    if not MODEL_DIR.exists():
        print(f"모델 없음: {MODEL_DIR}\n먼저 train.py를 실행하세요.")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = OUTPUT_DIR / "model.onnx"

    # ── Step 1: ONNX 변환 ────────────────────────────────────────────
    print("[1/2] PyTorch → ONNX 변환 중...")
    tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
    model = ElectraForSequenceClassification.from_pretrained(str(MODEL_DIR))
    model.eval()

    enc = tokenizer(
        TEST_SENTENCE,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding="max_length",
    )

    with torch.no_grad():
        torch.onnx.export(
            model,
            args=(enc["input_ids"], enc["attention_mask"], enc["token_type_ids"]),
            f=str(onnx_path),
            input_names=["input_ids", "attention_mask", "token_type_ids"],
            output_names=["logits"],
            dynamic_axes={
                "input_ids":      {0: "batch"},
                "attention_mask": {0: "batch"},
                "token_type_ids": {0: "batch"},
                "logits":         {0: "batch"},
            },
            opset_version=14,
            do_constant_folding=True,
        )

    onnx.checker.check_model(str(onnx_path))
    print(f"  저장: {onnx_path}  ({mb(onnx_path)})")

    # ── Step 2: 추론 검증 ────────────────────────────────────────────
    print("\n[2/2] ONNX 추론 검증 중...")
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path))
    input_names = {inp.name for inp in session.get_inputs()}
    feed = {
        k: v.numpy().astype(np.int64)
        for k, v in enc.items()
        if k in input_names
    }
    logits = session.run(["logits"], feed)[0]
    probs    = 1 / (1 + np.exp(-logits[0]))
    detected = [col for col, p in zip(LABEL_COLS, probs) if p >= THRESHOLD]
    scores_str = ", ".join(f"{col}:{p:.3f}" for col, p in zip(LABEL_COLS, probs))
    print(f"  입력: \"{TEST_SENTENCE}\"")
    print(f"  점수: {scores_str}")
    print(f"  판정: {detected if detected else ['정상']}  (예상: [기관사칭, 금전요구])")

    # ── 결과 요약 ─────────────────────────────────────────────────────
    print(f"""
{'='*60}
  ONNX 변환 완료
{'='*60}
  model.onnx : {mb(onnx_path)}

  ── 다음 단계: Docker TFLite 변환 ──
  프로젝트 루트에서 실행:

    docker compose up tflite-convert

  결과: voicephishing_detection_model/models/tflite/*.tflite
  예상 크기: ~216MB (float16)
{'='*60}
""")


if __name__ == "__main__":
    main()
