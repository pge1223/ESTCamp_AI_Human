"""
ONNX → INT8 TFLite 변환 (pinto0309/onnx2tf:latest, 캘리브레이션 INT8)

onnx2tf 2.4.0의 -qt per-tensor -cind 옵션으로 진짜 INT8 변환
캘리브레이션 데이터: 테스트셋에서 토크나이즈한 실제 샘플 사용

실행: docker compose up tflite-int8-calibrate
결과: /app/output/model_int8_calibrated.tflite (~108 MB)
"""
import json
import os
import subprocess
import sys

import numpy as np

MODEL_DIR  = "/app/model_dir"       # HuggingFace 모델 (tokenizer 포함)
ONNX_PATH  = "/app/input/model_merged.onnx"
DATA_PATH  = "/app/data/test_ml.json"
CALIB_DIR  = "/tmp/calib_data"
OUT_DIR    = "/app/output"
OUTPUT     = "/app/output/model_int8_calibrated.tflite"
MAX_LENGTH = 128
N_CALIB    = 50   # 캘리브레이션 샘플 수

os.makedirs(CALIB_DIR, exist_ok=True)

# ── 토크나이저 로드 ───────────────────────────────────────────────────
print("[pre] tokenizer 로드 중...")
try:
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    print(f"  tokenizer 로드 완료: {MODEL_DIR}")
except Exception as e:
    print(f"  tokenizer 로드 실패 ({e}), 더미 데이터 사용")
    tokenizer = None

# ── 캘리브레이션 데이터 생성 ─────────────────────────────────────────
print(f"\n[pre] 캘리브레이션 데이터 생성 중 (N={N_CALIB})...")

if tokenizer and os.path.exists(DATA_PATH):
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    texts = [d.get("text", d.get("utterance", "")) for d in data[:N_CALIB]]
    enc = tokenizer(
        texts,
        max_length=MAX_LENGTH,
        padding="max_length",
        truncation=True,
        return_tensors="np",
    )
    input_ids      = enc["input_ids"].astype(np.int64)
    attention_mask = enc["attention_mask"].astype(np.int64)
    token_type_ids = enc.get("token_type_ids", np.zeros_like(enc["input_ids"])).astype(np.int64)
else:
    print("  더미 데이터 사용 (tokenizer 또는 data 없음)")
    input_ids      = np.ones((N_CALIB, MAX_LENGTH), dtype=np.int64)
    attention_mask = np.ones((N_CALIB, MAX_LENGTH), dtype=np.int64)
    token_type_ids = np.zeros((N_CALIB, MAX_LENGTH), dtype=np.int64)

calib_ids  = os.path.join(CALIB_DIR, "input_ids.npy")
calib_mask = os.path.join(CALIB_DIR, "attention_mask.npy")
calib_type = os.path.join(CALIB_DIR, "token_type_ids.npy")
np.save(calib_ids,  input_ids)
np.save(calib_mask, attention_mask)
np.save(calib_type, token_type_ids)
print(f"  캘리브레이션 데이터 저장: {input_ids.shape}")

# ── onnx2tf INT8 변환 ──────────────────────────────────────────────────
print("\n[1/1] onnx2tf 2.4.0: INT8 변환 중 (수 분 소요)...")
cmd = [
    "onnx2tf",
    "-i", ONNX_PATH,
    "-o", OUT_DIR,
    "-ois", "input_ids:1,128", "attention_mask:1,128", "token_type_ids:1,128",
    "-qt", "per-tensor",
    "-iqd", "int8",
    "-oqd", "int8",
    "-cind", "input_ids",      calib_ids,  "[[0,30522]]",
    "-cind", "attention_mask", calib_mask, "[[0,1]]",
    "-cind", "token_type_ids", calib_type, "[[0,1]]",
    "-n",
]
print("  CMD:", " ".join(cmd))
ret = subprocess.run(cmd)

if ret.returncode != 0:
    print(f"\n변환 실패 (exit {ret.returncode})")
    sys.exit(1)

# 결과 파일 탐색 및 이름 변경
import glob
tflites = sorted(glob.glob(f"{OUT_DIR}/**/*.tflite", recursive=True))
if tflites:
    for f in tflites:
        mb = os.path.getsize(f) / 1024**2
        print(f"  {f}: {mb:.1f} MB")
else:
    print("변환 결과 tflite 파일 없음")
