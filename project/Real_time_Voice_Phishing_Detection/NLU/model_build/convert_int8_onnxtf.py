"""
ONNX → INT8 TFLite 변환 (onnx-tf 백엔드, Docker 전용)

onnx2tf 대신 onnx-tf(Microsoft/ONNX) 사용 → Transpose 버그 없음
실행: docker compose up tflite-int8  (docker-compose.yml에서 스크립트 교체 후)
결과: /app/output/model_int8_no_erf.tflite
"""
import os
import sys

import numpy as np
import onnx
import tensorflow as tf

ONNX_MERGED = "/app/input/model_merged.onnx"
SM_DIR  = "/tmp/onnx_tf_saved_model"
OUTPUT  = "/app/output/model_int8_no_erf.tflite"

# ── Step 1: ONNX → TF SavedModel (onnx-tf) ───────────────────────────
print("[1/3] onnx-tf: ONNX → SavedModel 변환 중...")
try:
    from onnx_tf.backend import prepare
except ImportError:
    print("onnx-tf 설치 중...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "onnx-tf", "-q"], check=True)
    from onnx_tf.backend import prepare

onnx_model = onnx.load(ONNX_MERGED)
tf_rep = prepare(onnx_model)
tf_rep.export_graph(SM_DIR)
print(f"  SavedModel 저장됨: {SM_DIR}")

# ── Step 2: SavedModel → INT8 TFLite (no-erf) ────────────────────────
print("\n[2/3] Dynamic range INT8 양자화 중...")
converter = tf.lite.TFLiteConverter.from_saved_model(SM_DIR)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
try:
    tflite = converter.convert()
    print("  성공: TFLITE_BUILTINS (FlexDelegate 불필요)")
except Exception as e:
    print(f"  TFLITE_BUILTINS 실패: {e}")
    print("  SELECT_TF_OPS 포함으로 재시도...")
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    tflite = converter.convert()

# ── Step 3: 결과 저장 ─────────────────────────────────────────────────
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, "wb") as f:
    f.write(tflite)
size_mb = os.path.getsize(OUTPUT) / 1024**2
print(f"\n[3/3] 완료: {OUTPUT}  ({size_mb:.1f} MB)")
