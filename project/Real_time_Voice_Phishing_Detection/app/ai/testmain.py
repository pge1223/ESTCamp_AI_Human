# 가짜/진짜 구분 추론 코드 (레퍼런스)
import sys
sys.path.insert(0, '/content/drive/MyDrive/RealTimeVoicePhishing')
import torch, soundfile as sf, numpy as np
from model import RawNet2
from pydub import AudioSegment

FIXED_LEN = 64600
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

model = RawNet2().to(DEVICE)
model.load_state_dict(torch.load(
    '/content/drive/MyDrive/checkpoints/korean_model.pth',
    map_location=DEVICE
))
model.eval()


def convert_to_wav(path):
    if path.endswith('.m4a'):
        wav_path = path.replace('.m4a', '.wav')
        AudioSegment.from_file(path, format='m4a') \
            .set_frame_rate(16000).set_channels(1) \
            .export(wav_path, format='wav')
        return wav_path
    return path


def is_silent(wav, threshold=0.01, min_speech_ratio=0.15):
    """
    무음 여부 판단
    threshold        : RMS 이 값 미만이면 무음 프레임
    min_speech_ratio : 전체 중 음성 프레임 비율이 이 값 미만이면 무음
    """
    frame_size = 1600  # 100ms @ 16kHz
    frames = [wav[i:i+frame_size]
              for i in range(0, len(wav) - frame_size, frame_size)]
    if not frames:
        return True
    speech_count = sum(
        1 for f in frames if np.sqrt(np.mean(f ** 2)) > threshold
    )
    return (speech_count / len(frames)) < min_speech_ratio


def predict(wav_path):
    wav_path = convert_to_wav(wav_path)
    wav, sr = sf.read(wav_path, dtype='float32')
    if wav.ndim == 2:
        wav = wav.mean(axis=1)
    if sr != 16000:
        import librosa
        wav = librosa.resample(wav, orig_sr=sr, target_sr=16000)
    if len(wav) >= FIXED_LEN:
        wav = wav[:FIXED_LEN]
    else:
        wav = np.pad(wav, (0, FIXED_LEN - len(wav)))

    # 무음이면 모델 실행하지 않음
    if is_silent(wav):
        print('판별불가 (무음)')
        return 'silent'

    t = torch.FloatTensor(wav).unsqueeze(0).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        prob = torch.softmax(model(t), dim=1)[0, 1].item()

    label = '가짜 (AI 목소리)' if prob > 0.4 else '진짜 (사람 목소리)'
    print(f'{label} | 가짜 확률: {prob:.2%}')
    return label
