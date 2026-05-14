#!/bin/bash
# ONNX 동적 양자화 → onnx2tf 2.4.0 → INT8 TFLite
# 실행: docker compose up tflite-int8-onnxrt
set -e

ONNX_F32="/app/input/model_merged.onnx"
ONNX_WORK="/tmp/model_src.onnx"
ONNX_INT8="/tmp/model_int8.onnx"
OUT_DIR="/app/output/int8_onnxrt"

mkdir -p "$OUT_DIR"

# onnxruntime 양자화는 입력 경로에 쓰기 권한 필요 → writable 위치로 복사
echo "[pre] ONNX 복사 중 (432 MB, 잠시 기다려주세요)..."
cp "$ONNX_F32" "$ONNX_WORK"
echo "  복사 완료"

# ── Step 1: ONNX 동적 양자화 (weights → INT8) ─────────────────────────
echo "[1/2] onnxruntime 동적 양자화 중..."
python3 - <<'PYEOF'
import os
from onnxruntime.quantization import quantize_dynamic, QuantType

quantize_dynamic(
    model_input="/tmp/model_src.onnx",
    model_output="/tmp/model_int8.onnx",
    weight_type=QuantType.QInt8,
    op_types_to_quantize=["MatMul", "Gemm", "Gather", "EmbedLayerNormalization"],
    per_channel=False,
    reduce_range=False,
    use_external_data_format=True,   # 외부 데이터 파일로 저장 (메모리 절약)
)
size_mb = os.path.getsize("/tmp/model_int8.onnx") / 1024**2
print(f"  INT8 ONNX 저장: /tmp/model_int8.onnx ({size_mb:.1f} MB)")
PYEOF

# ── Step 2: INT8 ONNX → TFLite (onnx2tf 2.4.0) ───────────────────────
echo "[2/2] onnx2tf: INT8 ONNX → TFLite 변환 중..."
onnx2tf \
  -i /tmp/model_int8.onnx \
  -o "$OUT_DIR" \
  -ois input_ids:1,128 attention_mask:1,128 token_type_ids:1,128 \
  -n

echo "[결과]"
ls -lh "$OUT_DIR"/*.tflite 2>/dev/null || echo "tflite 파일 없음"
