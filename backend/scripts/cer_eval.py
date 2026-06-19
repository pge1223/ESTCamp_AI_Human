"""CER 측정 — 작가 TTS 음성을 Whisper로 되받아쓰기해 원문과 글자 단위 비교.

정량 평가표의 'CER(작가 TTS 낭독)' 행을 채운다. (한국어 주지표, 목표 ≤0.10)
  CER 0.06 = 글자 6%만 틀림 = 발음 또렷.

전제:
  - pip install openai-whisper jiwer   (+ ffmpeg 설치 필요)
  - ElevenLabs 키가 동작해야 함(없거나 IP차단 시 TTS가 빈 결과 → 건너뜀).
  - Whisper 모델: 기본 'base'(빠름/CPU). 정확도↑면 WHISPER_MODEL=large-v3 (느림/GPU 권장).

실행: backend 폴더에서
    python -m scripts.cer_eval
    WHISPER_MODEL=large-v3 python -m scripts.cer_eval
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import os
import asyncio
import tempfile

from app.services import tts

# 낭독 테스트 문장(원문 = 정답지). 발음 까다로운 표현 섞음.
SAMPLES = [
    "비 오는 오후, 창가에 앉아 식어버린 커피를 바라보았다.",
    "그는 천천히 고개를 들어 나를 바라보았다.",
    "진열장에는 마지막 단팥빵 하나가 덩그러니 남아 있었다.",
    "낯선 발걸음 소리가 빵집 문을 열고 들어왔다.",
]
AUTHOR_ID = int(os.getenv("EVAL_AUTHOR_ID", "4"))  # 4=김도현
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")


async def main():
    try:
        import whisper
        from jiwer import cer, wer
    except ImportError:
        print("설치 필요: pip install openai-whisper jiwer   (+ ffmpeg)")
        return

    print(f"Whisper 모델 로드: {WHISPER_MODEL} (느리면 base 권장) ...")
    model = whisper.load_model(WHISPER_MODEL)

    cers = []
    for i, text in enumerate(SAMPLES, 1):
        audio = await tts.synthesize(text, author_id=AUTHOR_ID)
        if not audio:
            print(f"  [{i}] TTS 빈 결과(키 없음/IP 차단?) — 건너뜀")
            continue
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio)
            path = f.name
        try:
            heard = (model.transcribe(path, language="ko")["text"] or "").strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        c = cer(text, heard)
        w = wer(text, heard)
        cers.append(c)
        print(f"  [{i}] CER={c:.3f}  WER={w:.3f}")
        print(f"       원문: {text}")
        print(f"       들림: {heard}")

    print()
    if cers:
        avg = sum(cers) / len(cers)
        print(f"=== 평균 CER = {avg:.3f}  (n={len(cers)}, 목표 ≤0.10) "
              f"→ {'✅ 충족' if avg <= 0.10 else '⚠️ 초과'} ===")
    else:
        print("측정 0건 — ElevenLabs 키/네트워크 확인(IP 차단 시 로컬에서 시도).")


if __name__ == "__main__":
    asyncio.run(main())
