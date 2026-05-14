"""
ONNX → INT8 TFLite 변환 (pinto0309/onnx2tf:latest 이미지 전용)

onnx2tf 2.4.0 + TF 2.19  →  dynamic range INT8
실행: docker compose up tflite-int8-pinto
결과: /app/output/model_int8_no_erf.tflite
"""
import glob
import os
import subprocess
import sys

import tensorflow as tf

ONNX_PATH  = "/app/input/model_merged.onnx"
OUT_DIR    = "/app/output"
SM_DIR     = "/tmp/sm_pinto"
OUTPUT     = "/app/output/model_int8_no_erf.tflite"

os.makedirs(SM_DIR, exist_ok=True)

# ── Step 1: ONNX → SavedModel (onnx2tf 2.4.0 flatbuffer_direct + -easm) ─
print("[1/2] onnx2tf 2.4.0: ONNX → SavedModel 변환 중...")
ret = subprocess.run([
    "onnx2tf",
    "-i", ONNX_PATH,
    "-o", SM_DIR,
    "-ois", "input_ids:1,128", "attention_mask:1,128", "token_type_ids:1,128",
    "-easm",       # SavedModel도 함께 출력
    "-n",          # non-verbose
], capture_output=False)

if ret.returncode != 0:
    print(f"onnx2tf 실패 (exit {ret.returncode})")
    sys.exit(1)

# SavedModel 경로 탐색
pb_files = glob.glob(f"{SM_DIR}/**/saved_model.pb", recursive=True)
if not pb_files:
    # onnx2tf 2.x는 -o 경로에 바로 저장
    if os.path.exists(f"{SM_DIR}/saved_model.pb"):
        sm_path = SM_DIR
    else:
        print("SavedModel not found. 파일 목록:")
        for root, _, files in os.walk(SM_DIR):
            for f in files:
                print(f"  {os.path.join(root, f)}")
        sys.exit(1)
else:
    sm_path = os.path.dirname(pb_files[0])
print(f"  SavedModel: {sm_path}")

# ── Step 2: SavedModel → Dynamic Range INT8 TFLite ────────────────────
print("\n[2/2] TFLiteConverter: dynamic range INT8 양자화 중...")
converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
    tf.lite.OpsSet.SELECT_TF_OPS,
]
tflite = converter.convert()

with open(OUTPUT, "wb") as f:
    f.write(tflite)
size_mb = os.path.getsize(OUTPUT) / 1024**2
print(f"\n완료: {OUTPUT}  ({size_mb:.1f} MB)")
