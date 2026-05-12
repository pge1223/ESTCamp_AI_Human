"""
model_float16.tflite 추론 테스트
멀티라벨: 기관사칭 / 금전요구 / 개인정보 (sigmoid + threshold 0.5)

실행: docker compose up tflite-test
"""
import sys
from pathlib import Path

import numpy as np

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    import tensorflow as tf
    Interpreter = tf.lite.Interpreter

from transformers import AutoTokenizer

BASE          = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(BASE))
from config import DATA_VERSION
TFLITE_PATH   = BASE / "models/tflite/model_float32.tflite"
TOKENIZER_DIR = BASE / f"models/koelectra-finetuned-{DATA_VERSION}/best"
MAX_LENGTH    = 128
THRESHOLD     = 0.5
LABEL_COLS    = ["기관사칭", "금전요구", "개인정보"]

TEST_SENTENCES = [
    ("피싱", "저는 금융감독원 수사관 김철수입니다. 귀하의 계좌가 범죄에 연루되어 조사가 필요합니다."),
    ("피싱", "서울중앙지검입니다. 귀하 명의로 대포통장이 개설되어 긴급 소환장이 발부되었습니다."),
    ("피싱", "지금 바로 안전계좌로 3천만원을 이체하지 않으면 자산이 동결됩니다."),
    ("피싱", "공탁금 500만원을 오늘 중으로 입금하셔야 사건이 종결됩니다."),
    ("피싱", "본인 확인을 위해 주민등록번호 뒷자리와 OTP 번호를 말씀해 주세요."),
    ("피싱", "통장을 저희 직원에게 양도해주시면 조사 후 돌려드리겠습니다."),
    ("피싱", "저는 서울중앙지검 수사관입니다. 안전계좌로 즉시 송금해 주세요."),
    ("피싱", "경찰청입니다. 귀하 명의 계좌가 범죄에 사용됐으니 주민번호와 카드번호를 확인해 주세요."),
    ("정상", "엄마 나 오늘 저녁에 좀 늦을 것 같아. 밥 먼저 먹고 있어."),
    ("정상", "여보세요, 내일 회의 시간이 오후 3시로 변경됐다고 팀장님이 전달해달라고 하셨어요."),
]


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x.astype(np.float32)))


def main() -> None:
    if not TFLITE_PATH.exists():
        print(f"TFLite 모델 없음: {TFLITE_PATH}")
        return

    print(f"TFLite 로딩: {TFLITE_PATH.name}")
    interpreter = Interpreter(model_path=str(TFLITE_PATH))
    interpreter.allocate_tensors()
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"토크나이저 로딩: {TOKENIZER_DIR}")
    tokenizer = AutoTokenizer.from_pretrained(str(TOKENIZER_DIR))

    # 입력 텐서 이름 출력 (디버그)
    print("\n[입력 텐서]")
    for d in input_details:
        print(f"  index={d['index']}  name={d['name']}  dtype={d['dtype']}  shape={d['shape']}")

    W = 40
    print(f"\n{'='*75}")
    print(f"  {'실제':4s} | {'문장':{W}s} | 기관사칭 | 금전요구 | 개인정보 | 판정")
    print(f"{'='*75}")

    for label, sentence in TEST_SENTENCES:
        enc = tokenizer(
            sentence,
            return_tensors="np",
            truncation=True,
            max_length=MAX_LENGTH,
            padding="max_length",
        )

        # 텐서 이름으로 매핑 (e.g. "serving_default_input_ids:0" ← "input_ids")
        for detail in input_details:
            raw = detail["name"]
            for key in enc:
                if key in raw:
                    interpreter.set_tensor(detail["index"], enc[key].astype(np.int64))
                    break

        interpreter.invoke()

        logits = interpreter.get_tensor(output_details[0]["index"])[0]
        probs  = sigmoid(logits)
        detected = [col for col, p in zip(LABEL_COLS, probs) if p >= THRESHOLD]
        result   = " + ".join(detected) if detected else "정상"

        short = (sentence[:W - 2] + "..") if len(sentence) > W else sentence
        print(
            f"  {label:4s} | {short:{W}s}"
            f" |  {probs[0]:.3f}   |  {probs[1]:.3f}   |  {probs[2]:.3f}   | {result}"
        )

    print(f"{'='*75}")


if __name__ == "__main__":
    main()
