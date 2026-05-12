import subprocess
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import numpy as np

# faster_whisper.audio가 모듈 임포트 시점에 'av'를 로드하지만,
# numpy 배열을 직접 넘기면 av의 decode_audio는 실제로 호출되지 않음.
# Windows에서 av DLL 오류를 방지하기 위해 빈 stub으로 선점.
if "av" not in sys.modules:
    sys.modules["av"] = types.ModuleType("av")

from faster_whisper import WhisperModel

SAMPLE_RATE = 16000  # Whisper 요구 사양


@dataclass
class Segment:
    start: float
    end: float
    text: str

    def __repr__(self):
        return f"[{self.start:.1f}s-{self.end:.1f}s] {self.text}"


def _mp4_to_numpy(audio_path: str) -> np.ndarray:
    """imageio-ffmpeg으로 MP4 → float32 PCM numpy 배열 변환 (av 라이브러리 불필요)."""
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe,
        "-i", audio_path,
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",        # mono
        "-f", "f32le",     # float32 little-endian raw PCM
        "-",               # stdout으로 출력
    ]
    result = subprocess.run(cmd, capture_output=True, check=True)
    return np.frombuffer(result.stdout, dtype=np.float32)


class WhisperSTT:
    def __init__(self, model_size: str = "small"):
        print(f"  Whisper '{model_size}' 모델 로딩 중...")
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, audio_path: str) -> list[Segment]:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {audio_path}")

        audio_np = _mp4_to_numpy(str(path))
        segments_iter, _ = self.model.transcribe(audio_np, language="ko")

        segments = []
        for seg in segments_iter:
            # �(대체문자)는 Whisper가 불명확한 오디오를 표시할 때 사용 — 제거
            text = seg.text.strip().replace("�", "")
            if text:
                segments.append(Segment(start=seg.start, end=seg.end, text=text))
        return segments
