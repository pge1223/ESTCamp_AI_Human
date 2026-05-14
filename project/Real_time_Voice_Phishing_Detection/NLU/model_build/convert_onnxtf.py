"""
ONNX → TF SavedModel (onnx-tf 1.10) → INT8 TFLite

onnx2tf 우회 전략:
  - onnx2tf 1.26.x : 5D Transpose 버그 → 실패
  - onnx2tf 2.4.x  : flatbuffer_direct → INT8 플래그 무시
  - onnx-tf 1.10   : op-by-op TF 매핑, NCHW→NHWC 변환 없음 → SavedModel 정상 생성
  → TFLiteConverter dynamic-range INT8 (weights→INT8, activations→float32)

실행: docker compose up tflite-onnxtf
결과: /app/output/model_int8_v6.tflite  (~100-130 MB)
"""
import glob
import os
import sys

import numpy as np
import onnx
import tensorflow as tf
from onnx import shape_inference as onnx_si

ONNX_PATH    = "/app/input/model_merged.onnx"
STATIC_PATH  = "/tmp/model_static.onnx"
SM_DIR       = "/tmp/saved_model_onnxtf"
OUTPUT       = "/app/output/model_int8_v6.tflite"
INPUT_SHAPES = {
    "input_ids":      [1, 128],
    "attention_mask": [1, 128],
    "token_type_ids": [1, 128],
}

os.makedirs(SM_DIR, exist_ok=True)

# ── Step 0: ONNX 정적 shape 고정 + shape inference ────────────────────
print("[pre] ONNX 정적 shape 고정 중...")
model = onnx.load(ONNX_PATH)
for inp in model.graph.input:
    if inp.name in INPUT_SHAPES:
        dims = inp.type.tensor_type.shape.dim
        for i, val in enumerate(INPUT_SHAPES[inp.name]):
            dims[i].ClearField("dim_param")
            dims[i].dim_value = val
model = onnx_si.infer_shapes(model)
onnx.save(model, STATIC_PATH)
print(f"  저장: {STATIC_PATH}")

# ── Step 1: onnx-tf: ONNX → TF SavedModel ────────────────────────────
print("\n[1/2] onnx-tf: ONNX → TF SavedModel 변환 중 (수 분 소요)...")
try:
    from onnx_tf.backend import prepare
except ImportError:
    print("ERROR: onnx-tf 미설치 — Docker 이미지 확인")
    sys.exit(1)

tf_rep = prepare(onnx.load(STATIC_PATH))
tf_rep.export_graph(SM_DIR)

pb_files = glob.glob(f"{SM_DIR}/**/saved_model.pb", recursive=True)
if not pb_files and not os.path.exists(f"{SM_DIR}/saved_model.pb"):
    print("ERROR: saved_model.pb 생성 안됨. 파일 목록:")
    for root, _, files in os.walk(SM_DIR):
        for f in files:
            print(f"  {os.path.join(root, f)}")
    sys.exit(1)

sm_path = SM_DIR if os.path.exists(f"{SM_DIR}/saved_model.pb") else os.path.dirname(pb_files[0])
print(f"  SavedModel: {sm_path}")

# ── Step 2: TFLiteConverter: dynamic range INT8 양자화 ────────────────
print("\n[2/2] TFLiteConverter: INT8 dynamic-range 변환 중...")
converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS,
    tf.lite.OpsSet.SELECT_TF_OPS,   # erf 등 Flex op 허용
]
converter.target_spec.supported_types = []  # float32 activations (dynamic range)

try:
    tflite = converter.convert()
except Exception as e:
    print(f"TFLiteConverter 실패: {e}")
    sys.exit(1)

with open(OUTPUT, "wb") as f:
    f.write(tflite)
size_mb = len(tflite) / 1024**2
print(f"\n완료: {OUTPUT}  ({size_mb:.1f} MB)")
