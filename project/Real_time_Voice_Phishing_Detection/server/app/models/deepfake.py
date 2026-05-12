import random


class DeepfakeModel:
    """RawNet2 placeholder — best_model.pth 연결 전까지 더미 사용"""

    def predict(self, pcm_bytes: bytes) -> dict:
        is_fake = random.random() < 0.2
        return {
            "is_fake": is_fake,
            "confidence": round(random.uniform(0.7, 0.99), 3),
        }
