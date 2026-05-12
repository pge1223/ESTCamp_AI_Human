import subprocess
import tempfile
import os


def convert_to_pcm(raw_audio: bytes, sample_rate: int = 16000) -> bytes:
    """FFmpeg으로 오디오를 PCM 16kHz mono 16-bit로 변환 (MP3/M4A/WAV/MP4 등)"""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
        tmp.write(raw_audio)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["ffmpeg", "-loglevel", "quiet", "-i", tmp_path,
             "-f", "s16le", "-ar", str(sample_rate), "-ac", "1", "pipe:1"],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")
        return result.stdout
    finally:
        os.unlink(tmp_path)
