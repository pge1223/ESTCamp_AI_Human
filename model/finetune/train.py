"""
모방학습(Imitation Learning) 파인튜닝
목표 모델: Qwen2.5-1.5B 또는 Phi-3-mini (경량)
데이터:  data/processed/ 의 장르별 정제 텍스트
"""
import argparse


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-1.5B")
    parser.add_argument("--data_dir", default="data/processed")
    parser.add_argument("--persona_id", required=True)
    parser.add_argument("--output_dir", default="model/checkpoints")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=4)
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"파인튜닝 시작: {args.persona_id} / {args.model}")
    # TODO: transformers Trainer 구성


if __name__ == "__main__":
    main()
