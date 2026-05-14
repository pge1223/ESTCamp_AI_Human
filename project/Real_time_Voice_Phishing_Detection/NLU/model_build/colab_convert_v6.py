"""
Colab 전용: v6 KoELECTRA → INT8 TFLite 변환

【업로드 필요 파일 (Google Drive)】
  MyDrive/VoicePhishingData/models/koelectra-v6/
    config.json
    model.safetensors
    tokenizer.json
    tokenizer_config.json
  → 합계 약 110MB (model_merged.onnx 432MB 업로드 불필요)

【Colab 셀 실행 순서】

  # ── 셀 1: 패키지 설치 ──────────────────────────────────────────────
  !pip install transformers onnx onnxruntime onnx2tf tensorflow -q

  # ── 셀 2: Drive 마운트 ──────────────────────────────────────────────
  from google.colab import drive
  drive.mount('/content/drive')

  # ── 셀 3: 변환 실행 ─────────────────────────────────────────────────
  DRIVE = "/content/drive/MyDrive/VoicePhishingData"
  exec(open(f"{DRIVE}/colab_convert_v6.py").read())

  # 또는:
  # !python "{DRIVE}/colab_convert_v6.py" \
  #   --model_dir "{DRIVE}/models/koelectra-v6" \
  #   --out_dir   "{DRIVE}/models/tflite"
"""
import argparse
import os
import sys
import tempfile
from pathlib import Path

# ── 경로 기본값 ────────────────────────────────────────────────────────
DRIVE      = "/content/drive/MyDrive/VoicePhishingData"
MODEL_DIR  = f"{DRIVE}/models/koelectra-v6"
OUT_DIR    = f"{DRIVE}/models/tflite"
MAX_LENGTH = 128


def main(model_dir: str = MODEL_DIR, out_dir: str = OUT_DIR) -> None:
    import numpy as np
    import onnx
    import onnx2tf
    import tensorflow as tf
    import torch
    from onnx import shape_inference as onnx_si
    from transformers import AutoTokenizer, ElectraForSequenceClassification

    model_dir = Path(model_dir)
    out_dir   = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    onnx_dir    = out_dir / "onnx_tmp"
    sm_dir      = str(out_dir / "saved_model_v6")
    onnx_raw    = onnx_dir / "model.onnx"
    onnx_static = onnx_dir / "model_static.onnx"
    output      = out_dir / "model_int8_v6.tflite"
    onnx_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"  모델 경로: {model_dir}")
    print(f"  출력 경로: {out_dir}")
    print("=" * 60)

    # ── Step 1: PyTorch → ONNX ────────────────────────────────────────
    print("\n[1/4] PyTorch → ONNX 변환 중...")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir))
    model = ElectraForSequenceClassification.from_pretrained(
        str(model_dir),
        attn_implementation="eager",   # SDPA 비활성화 → ONNX 호환
    )
    model.eval()

    enc = tokenizer(
        "안녕하세요 검사입니다 계좌이체 필요합니다",
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding="max_length",
    )

    with torch.no_grad():
        torch.onnx.export(
            model,
            args=(enc["input_ids"], enc["attention_mask"], enc["token_type_ids"]),
            f=str(onnx_raw),
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
    print(f"  ONNX 저장: {onnx_raw}  ({onnx_raw.stat().st_size/1e6:.1f} MB)")

    # ── Step 2: ONNX shape 고정 ───────────────────────────────────────
    print("\n[2/4] ONNX 정적 shape 고정 중...")
    m = onnx.load(str(onnx_raw))
    INPUT_SHAPES = {"input_ids": [1, 128], "attention_mask": [1, 128], "token_type_ids": [1, 128]}
    for inp in m.graph.input:
        if inp.name in INPUT_SHAPES:
            dims = inp.type.tensor_type.shape.dim
            for i, val in enumerate(INPUT_SHAPES[inp.name]):
                dims[i].ClearField("dim_param")
                dims[i].dim_value = val
    m = onnx_si.infer_shapes(m)
    onnx.save(m, str(onnx_static))
    print(f"  저장: {onnx_static}")

    # ── Step 3: onnx2tf: ONNX → TF SavedModel ────────────────────────
    print("\n[3/4] onnx2tf: ONNX → TF SavedModel 변환 중 (수 분 소요)...")
    onnx2tf.convert(
        input_onnx_file_path=str(onnx_static),
        output_folder_path=sm_dir,
        non_verbose=True,
    )
    # SavedModel 경로 확인
    import glob
    pb_files = glob.glob(f"{sm_dir}/**/saved_model.pb", recursive=True)
    sm_path  = sm_dir if os.path.exists(f"{sm_dir}/saved_model.pb") \
               else (os.path.dirname(pb_files[0]) if pb_files else None)
    if sm_path is None:
        print("ERROR: SavedModel 생성 실패. 파일 목록:")
        for root, _, files in os.walk(sm_dir):
            for f in files:
                print(f"  {os.path.join(root, f)}")
        sys.exit(1)
    print(f"  SavedModel: {sm_path}")

    # ── Step 4: TFLiteConverter: dynamic range INT8 ───────────────────
    print("\n[4/4] TFLiteConverter: INT8 변환 중...")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_path)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    tflite = converter.convert()

    output.write_bytes(tflite)
    size_mb = len(tflite) / 1024**2
    print(f"\n{'='*60}")
    print(f"  완료: {output}")
    print(f"  크기: {size_mb:.1f} MB")
    if size_mb > 130:
        print("  ⚠️  목표(100-130MB)보다 큼 — full int8 정적 양자화를 검토하세요")
    print(f"{'='*60}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model_dir", default=MODEL_DIR)
    ap.add_argument("--out_dir",   default=OUT_DIR)
    ap.parse_args()
    args = ap.parse_args()
    main(args.model_dir, args.out_dir)
