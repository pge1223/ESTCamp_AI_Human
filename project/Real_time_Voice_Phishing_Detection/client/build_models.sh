#!/usr/bin/env bash
# 모델별 APK 빌드 스크립트
# 사용법: bash build_models.sh
set -e

cd "$(dirname "$0")"

OUTPUT_DIR="build/app/outputs/flutter-apk"

# 원본 pubspec.yaml 백업
cp pubspec.yaml pubspec.yaml.bak

build_apk() {
  local FILE="$1"
  local LABEL="$2"

  echo ""
  echo "==============================="
  echo "빌드: $LABEL ($FILE)"
  echo "==============================="

  # pubspec.yaml의 모델 에셋 라인 교체 (주석 포함 기존 모델 라인 → 새 모델)
  py -3 -c  "
import re, sys
content = open('pubspec.yaml', encoding='utf-8').read()
content = re.sub(
    r'(    # .*model.*\n)*    - assets/model_[^\n]+',
    '    - assets/$FILE',
    content
)
open('pubspec.yaml', 'w', encoding='utf-8').write(content)
"

  flutter build apk --debug \
    --dart-define=MODEL_FILE="$FILE" \
    --dart-define=MODEL_LABEL="$LABEL"

  cp "$OUTPUT_DIR/app-debug.apk" "$OUTPUT_DIR/app-debug-${LABEL}.apk"
  echo "완료: app-debug-${LABEL}.apk"
}

build_apk "model_float32.tflite"              "float32"
build_apk "model_float16.tflite"              "float16"
build_apk "model_dynamic_range_quant.tflite"  "int8"

# pubspec.yaml 복원
cp pubspec.yaml.bak pubspec.yaml
rm pubspec.yaml.bak

echo ""
echo "=== 빌드 완료 ==="
ls -lh "$OUTPUT_DIR"/app-debug-*.apk
