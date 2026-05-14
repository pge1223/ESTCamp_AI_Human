"""
ONNX → INT8 TFLite 변환 — Google Colab 전용 (Docker 불필요)

Google Colab에서 순서대로 셀 실행:

  # 셀 1 — 패키지 설치
  !pip install onnx onnx2tf tensorflow -q

  # 셀 2 — Drive 마운트
  from google.colab import drive
  drive.mount('/content/drive')

  # 셀 3 — 실행
  DRIVE = "/content/drive/MyDrive/VoicePhishingData"
  !python {DRIVE}/convert_colab.py --onnx {DRIVE}/models/onnx/model.onnx --out {DRIVE}/models/tflite/

  # 셀 4 — 결과 확인
  import os
  for f in os.listdir(f"{DRIVE}/models/tflite/"):
      size = os.path.getsize(f"{DRIVE}/models/tflite/{f}") / 1024**2
      print(f"{f}: {size:.1f} MB")
"""
import argparse
import os
from pathlib import Path


def convert(onnx_path: str, out_dir: str) -> None:
    import numpy as np
    import onnx
    import onnx2tf
    import tensorflow as tf

    onnx_path = Path(onnx_path)
    out_dir   = Path(out_dir)
    sm_dir    = str(out_dir / "saved_model")

    if not onnx_path.exists():
        raise FileNotFoundError(f"ONNX 파일 없음: {onnx_path}\n먼저 convert.py 실행 후 Drive에 업로드하세요.")

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: ONNX → SavedModel (onnx2tf) ──────────────────────────
    print("[1/3] onnx2tf: ONNX → SavedModel 변환 중...")
    onnx2tf.convert(
        input_onnx_file_path=str(onnx_path),
        output_folder_path=sm_dir,
        keep_ncw_or_nchw_input_shapes=True,
        non_verbose=True,
    )
    print(f"  SavedModel 저장됨: {sm_dir}")

    # ── Step 2: SavedModel → Dynamic-Range INT8 TFLite ───────────────
    print("\n[2/3] TFLite INT8 양자화 중...")
    converter = tf.lite.TFLiteConverter.from_saved_model(sm_dir)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.target_spec.supported_ops = [
        tf.lite.OpsSet.TFLITE_BUILTINS,
        tf.lite.OpsSet.SELECT_TF_OPS,
    ]
    tflite_model = converter.convert()

    out_path = out_dir / "model_int8.tflite"
    out_path.write_bytes(tflite_model)
    size_mb = out_path.stat().st_size / 1024**2
    print(f"\n[3/3] 완료: {out_path}  ({size_mb:.1f} MB)")
    if size_mb > 50:
        print(f"  ⚠️  목표(50MB)보다 큼 — full-int8 정적 양자화를 시도하세요.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", required=True, help="model.onnx 경로")
    ap.add_argument("--out",  required=True, help="출력 디렉토리")
    args = ap.parse_args()
    convert(args.onnx, args.out)
