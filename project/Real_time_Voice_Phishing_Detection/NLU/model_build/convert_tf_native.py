"""
PyTorch v6 → TF SavedModel → dynamic range INT8 TFLite

ONNX 경유 없음. HuggingFace from_pt=True 로 PT 가중치를 TF로 직변환.
TFLiteConverter.DEFAULT → weight INT8, activation float32 (dynamic range)

예상 결과 크기: ~108 MB (v5 model_int8_no_erf.tflite 동급)
실행: docker compose up tflite-tf-native
결과: /app/output/model_int8_v6.tflite
"""
import glob
import os
import sys

os.environ["TF_USE_LEGACY_KERAS"] = "1"   # tf-keras 사용 (TF 2.15 호환)

import tensorflow as tf
from transformers import AutoConfig, AutoTokenizer, TFElectraForSequenceClassification

MODEL_DIR = "/app/model_dir"   # koelectra-finetuned-v6/best 마운트 경로
SM_DIR    = "/tmp/saved_model_tf_native"
OUTPUT    = "/app/output/model_int8_v6.tflite"
MAX_LEN   = 128

# gelu: 학습 때와 동일한 activation → 정확도 보존
# erf 사용하므로 SELECT_TF_OPS(FlexDelegate) 필요하지만 정확도가 맞음
HIDDEN_ACT = "gelu"

os.makedirs(SM_DIR, exist_ok=True)

# ── Step 1: PyTorch 가중치 → TF 모델 (HuggingFace 자동 변환) ─────────
print(f"[1/3] TFElectraForSequenceClassification 로드 중 (hidden_act={HIDDEN_ACT}, from_pt=True)...")
try:
    config = AutoConfig.from_pretrained(MODEL_DIR)
    config.hidden_act = HIDDEN_ACT   # erf 없는 GELU 근사식으로 교체
    tf_model  = TFElectraForSequenceClassification.from_pretrained(
        MODEL_DIR,
        from_pt=True,          # .safetensors → TF 가중치 자동 변환
        config=config,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    print(f"  로드 완료. num_labels={tf_model.config.num_labels}")
except Exception as e:
    print(f"ERROR (모델 로드): {e}")
    sys.exit(1)

# ── Step 2: 고정 shape 서빙 함수 trace → SavedModel ──────────────────
print("\n[2/3] SavedModel 저장 중 (shape [1, 128] 고정)...")

@tf.function(input_signature=[
    tf.TensorSpec([1, MAX_LEN], tf.int32, name="input_ids"),
    tf.TensorSpec([1, MAX_LEN], tf.int32, name="attention_mask"),
    tf.TensorSpec([1, MAX_LEN], tf.int32, name="token_type_ids"),
])
def serving_fn(input_ids, attention_mask, token_type_ids):
    outputs = tf_model(
        input_ids=input_ids,
        attention_mask=attention_mask,
        token_type_ids=token_type_ids,
        training=False,
    )
    return {"logits": outputs.logits}

try:
    tf.saved_model.save(
        tf_model,
        SM_DIR,
        signatures={"serving_default": serving_fn},
    )
    print(f"  SavedModel 저장: {SM_DIR}")
except Exception as e:
    print(f"ERROR (SavedModel 저장): {e}")
    sys.exit(1)

# ── Step 3: TFLiteConverter: dynamic range INT8 ───────────────────────
# weight → INT8, activation → float32 (dynamic dequant at runtime)
# 목표 크기: ~108 MB, FlexDelegate 불필요
print("\n[3/3] TFLiteConverter: dynamic range INT8 변환 중...")
try:
    converter = tf.lite.TFLiteConverter.from_saved_model(
        SM_DIR,
        signature_keys=["serving_default"],
    )
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    # gelu는 erf 사용 → SELECT_TF_OPS 필수 (Flutter FlexDelegate로 실행)
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    tflite = converter.convert()
    print("  (SELECT_TF_OPS 포함 — Flutter에 FlexDelegate 등록 필요)")
except Exception as e:
    print(f"ERROR (TFLiteConverter): {e}")
    sys.exit(1)

with open(OUTPUT, "wb") as f:
    f.write(tflite)
size_mb = len(tflite) / 1024**2
print(f"\n{'='*55}")
print(f"  완료: {OUTPUT}")
print(f"  크기: {size_mb:.1f} MB")
if size_mb < 150:
    print("  결과: 목표 크기 달성")
else:
    print("  주의: 예상보다 큼 — SELECT_TF_OPS 포함 여부 확인 필요")
print(f"{'='*55}")

# 입력 텐서 순서 확인 (Flutter 앱 인덱스 매핑용)
interp = tf.lite.Interpreter(OUTPUT)
interp.allocate_tensors()
print("\n입력 텐서 순서 (Flutter 앱에서 인덱스로 접근):")
for t in interp.get_input_details():
    print(f"  [{t['index']}] {t['name']}  shape={t['shape']}  dtype={t['dtype']}")
print("출력 텐서:")
for t in interp.get_output_details():
    print(f"  [{t['index']}] {t['name']}  shape={t['shape']}  dtype={t['dtype']}")
