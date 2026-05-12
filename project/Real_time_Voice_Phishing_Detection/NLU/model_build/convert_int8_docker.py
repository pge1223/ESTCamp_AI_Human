"""
ONNX → INT8 TFLite 변환 (Docker 전용)

onnx2tf의 flatbuffer 직렬화 버그를 우회:
  1. ONNX → TF SavedModel  (onnx2tf, /tmp 경유)
  2. SavedModel → INT8 TFLite  (tf.lite.TFLiteConverter, dynamic range quantization)

실행: docker compose up tflite-int8
"""
import os
import shutil
import subprocess
import sys

ONNX_SRC   = "/app/input/model.onnx"
ONNX_TMP   = "/tmp/model.onnx"
SAVED_DIR  = "/tmp/tf_saved_model"
OUTPUT     = "/app/output/model_int8.tflite"

# ── Step 1: ONNX → TF SavedModel ──────────────────────────────────────
print("[1/2] ONNX → TF SavedModel 변환 중...")

# /app/input 이 read-only라 onnxsim 실패 방지 — /tmp 에 복사
# external data 방식이라 .onnx + .onnx.data 둘 다 복사 필요
shutil.copy(ONNX_SRC, ONNX_TMP)
shutil.copy("/app/input/model.onnx.data", "/tmp/model.onnx.data")

result = subprocess.run(
    ["onnx2tf", "-i", ONNX_TMP, "-o", SAVED_DIR, "-ntfd"],
    capture_output=True, text=True,
)
print(result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout)
if result.stderr:
    print("[STDERR]", result.stderr[-1000:])

saved_model_pb = os.path.join(SAVED_DIR, "saved_model.pb")
if not os.path.exists(saved_model_pb):
    print(f"SavedModel 생성 실패: {saved_model_pb} 없음")
    sys.exit(1)

print(f"SavedModel 생성 완료: {SAVED_DIR}")

# ── Step 2: SavedModel → INT8 TFLite (dynamic range quantization) ─────
print("\n[2/2] SavedModel → INT8 TFLite 변환 중 (dynamic range)...")

import tensorflow as tf

converter = tf.lite.TFLiteConverter.from_saved_model(SAVED_DIR)
converter.optimizations = [tf.lite.Optimize.DEFAULT]   # 가중치 INT8, 활성화 float32

tflite_model = converter.convert()

with open(OUTPUT, "wb") as f:
    f.write(tflite_model)

size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
print(f"\n완료: {OUTPUT}  ({size_mb:.1f} MB)")
print("(예상: ~107MB — float32 430MB의 1/4)")
