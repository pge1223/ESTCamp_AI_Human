#!/bin/bash
set -e

mkdir -p /tmp/calib

python3 - <<'PYEOF'
import numpy as np
np.save('/tmp/calib/ids.npy',  np.ones((20, 128), dtype=np.int64))
np.save('/tmp/calib/mask.npy', np.ones((20, 128), dtype=np.int64))
np.save('/tmp/calib/type.npy', np.zeros((20, 128), dtype=np.int64))
print("캘리브레이션 데이터 생성 완료 (20x128)")
PYEOF

echo "[INT8 변환 시작]"
onnx2tf \
  -i /app/input/model_merged.onnx \
  -o /app/output/int8_calib \
  -ois input_ids:1,128 attention_mask:1,128 token_type_ids:1,128 \
  -qt per-tensor \
  -iqd int8 \
  -oqd int8 \
  -cind input_ids      /tmp/calib/ids.npy  0.0 1.0 \
  -cind attention_mask /tmp/calib/mask.npy 0.0 1.0 \
  -cind token_type_ids /tmp/calib/type.npy 0.0 1.0 \
  -n

echo "[결과]"
ls -lh /app/output/int8_calib/*.tflite 2>/dev/null || echo "tflite 파일 없음"
