import os
import random
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset
import soundfile as sf
import librosa

FIXED_LEN  = 64600  # 16kHz 기준 약 4초
PHONE_SR   = 8000
ORIGIN_SR  = 16000


def _collect_audio(root_dir):
    paths = []
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            if f.lower().endswith(('.wav', '.m4a')):
                paths.append(os.path.join(dirpath, f))
    return paths


def _collect_wavs(root_dir):
    return _collect_audio(root_dir)


def _phone_channel(wav: torch.Tensor) -> torch.Tensor:
    wav = wav.unsqueeze(0)
    down = F.interpolate(wav, scale_factor=PHONE_SR / ORIGIN_SR, mode='linear', align_corners=False)
    up   = F.interpolate(down, size=wav.shape[-1], mode='linear', align_corners=False)
    return up.squeeze(0)


def _add_reverb(wav: torch.Tensor) -> torch.Tensor:
    result = wav.clone()
    for _ in range(random.randint(2, 5)):
        delay = random.randint(400, 3000)   # 25ms ~ 187ms @ 16kHz
        decay = random.uniform(0.1, 0.4)
        if delay < wav.shape[-1]:
            result[:, delay:] = result[:, delay:] + wav[:, :-delay] * decay
    return result.clamp(-1.0, 1.0)


def _augment(wav: torch.Tensor, label: int) -> torch.Tensor:
    """
    label:
      0 = genuine / real
      1 = fake / TTS

    핵심:
    - REAL에도 전화/노이즈/볼륨 변형을 줌
    - FAKE에는 전화환경 변형을 더 강하게 줌
    - reverb: 스피커 재녹음 시뮬레이션 (genuine/fake 둘 다)
    """

    # 1. speed perturbation ±5%
    if random.random() < 0.2:
        factor = random.uniform(0.95, 1.05)
        wav_np = wav.squeeze(0).numpy()
        wav_np = librosa.effects.time_stretch(wav_np, rate=factor)

        if len(wav_np) > FIXED_LEN:
            wav_np = wav_np[:FIXED_LEN]
        else:
            wav_np = np.pad(wav_np, (0, FIXED_LEN - len(wav_np)))

        wav = torch.FloatTensor(wav_np).unsqueeze(0)

    # 2. volume
    if random.random() < 0.8:
        wav = wav * random.uniform(0.7, 1.3)

    # 3. phone channel
    # REAL도 전화환경이 있지만,
    # FAKE는 "TTS도 전화환경으로 들어올 수 있음"을 더 강하게 학습
    if label == 1:
        phone_prob = 0.45   # FAKE: 전화환경 TTS를 많이 보여줌
    else:
        phone_prob = 0.40   # REAL: 사람 전화음성도 유지

    if random.random() < phone_prob:
        wav = _phone_channel(wav)

    # 4. background noise
    # FAKE도 실전에서는 잡음/압축을 거칠 수 있으므로 약간 더 적용
    if label == 1:
        noise_prob = 0.35
    else:
        noise_prob = 0.25

    if random.random() < noise_prob:
        snr_db = random.uniform(18, 30)
        signal_rms = wav.pow(2).mean().sqrt().clamp(min=1e-8)
        noise_rms = signal_rms / (10 ** (snr_db / 20))
        wav = wav + torch.randn_like(wav) * noise_rms

    # 5. reverb — 스피커 재녹음 시뮬레이션 (genuine/fake 둘 다)
    if random.random() < 0.2:
        wav = _add_reverb(wav)

    # 6. MP3 압축 시뮬레이션 — 속도 문제로 비활성화 (오프라인 변환 방식으로 대체)
    # if random.random() < 0.3:
    #     wav_np = wav.squeeze(0).numpy()
    #     wav_np = np.clip(wav_np, -1.0, 1.0)
    #     audio  = AudioSegment(
    #         (wav_np * 32767).astype(np.int16).tobytes(),
    #         frame_rate=ORIGIN_SR, sample_width=2, channels=1
    #     )
    #     buf = io.BytesIO()
    #     audio.export(buf, format="mp3", bitrate="64k")
    #     buf.seek(0)
    #     mp3_audio = AudioSegment.from_mp3(buf)
    #     mp3_audio = mp3_audio.set_frame_rate(ORIGIN_SR).set_channels(1)
    #     wav_np = np.array(mp3_audio.get_array_of_samples()).astype(np.float32) / 32768.0
    #     if len(wav_np) > FIXED_LEN:
    #         wav_np = wav_np[:FIXED_LEN]
    #     else:
    #         wav_np = np.pad(wav_np, (0, FIXED_LEN - len(wav_np)))
    #     wav = torch.FloatTensor(wav_np).unsqueeze(0)

    return wav.clamp(-1.0, 1.0)
    

class KoreanDeepVoiceDataset(Dataset):
    def __init__(self, genuine_dir, fake_dir, max_samples=None, seed=42,
                 is_train=True, samples=None):
        """
        genuine_dir : 진짜 한국어 음성 루트
        fake_dir    : 가짜 한국어 음성 루트
        max_samples : 클래스당 최대 샘플 수 (None 이면 전체)
        is_train    : True → augmentation 적용 / False → 클린 로드만 (dev 전용)
        samples     : 외부에서 미리 분리한 [(path, label), ...] 리스트
        """
        self.is_train = is_train

        if samples is not None:
            self.samples = samples
            print(f'[KoreanDataset] pre-split | total={len(self.samples)} | is_train={is_train}')
            return

        # Genuine 수집 — real_calls, news, repeat_calls, hard_real_false_alarm은 항상 포함
        real_calls_dir        = os.path.join(genuine_dir, 'real_calls')
        news_dir              = os.path.join(genuine_dir, 'news')
        genuine_repeat_dir    = os.path.join(genuine_dir, 'repeat_calls')
        hard_real_dir         = os.path.join(genuine_dir, 'hard_real_false_alarm')
        real_calls     = _collect_wavs(real_calls_dir)      if os.path.exists(real_calls_dir)      else []
        news           = _collect_wavs(news_dir)            if os.path.exists(news_dir)            else []
        genuine_repeat = _collect_audio(genuine_repeat_dir) if os.path.exists(genuine_repeat_dir)  else []
        hard_real      = _collect_audio(hard_real_dir)      if os.path.exists(hard_real_dir)       else []
        guaranteed    = real_calls + news + genuine_repeat + hard_real
        all_genuine = _collect_audio(genuine_dir)
        other_genuine = [p for p in all_genuine if p not in set(guaranteed)]

        # Fake 수집 — Qwen3-TTS, speaker_TTS, clova_tts_mp3sim, repeat_TTS는 항상 포함 (max_samples 제한 밖)
        qwen_train_dir   = os.path.join(fake_dir, 'qwen_tts', 'train')
        speaker_tts_dir  = os.path.join(fake_dir, 'speaker_TTS')
        mp3sim_dir       = os.path.join(fake_dir, 'clova_tts_mp3sim')
        fake_repeat_dir  = os.path.join(fake_dir, 'repeat_TTS')
        qwen_paths       = _collect_audio(qwen_train_dir)  if os.path.exists(qwen_train_dir)  else []
        speaker_paths    = _collect_audio(speaker_tts_dir) if os.path.exists(speaker_tts_dir) else []
        mp3sim_paths     = _collect_audio(mp3sim_dir)      if os.path.exists(mp3sim_dir)      else []
        fake_repeat      = _collect_audio(fake_repeat_dir) if os.path.exists(fake_repeat_dir) else []
        guaranteed_fake  = qwen_paths + speaker_paths + mp3sim_paths + fake_repeat
        all_fake         = _collect_audio(fake_dir)
        other_fake       = [p for p in all_fake if p not in set(guaranteed_fake)]

        random.seed(seed)
        random.shuffle(other_genuine)
        random.shuffle(other_fake)

        if max_samples is not None:
            fill          = max_samples - len(guaranteed)
            other_genuine = other_genuine[:max(fill, 0)]
            fill_fake     = max_samples - len(guaranteed_fake)
            other_fake    = other_fake[:max(fill_fake, 0)]

        genuine_paths = guaranteed + other_genuine
        fake_paths    = guaranteed_fake + other_fake

        self.samples = (
            [(p, 0) for p in genuine_paths] +
            [(p, 1) for p in fake_paths]
        )
        random.shuffle(self.samples)

        print(f'[KoreanDataset] genuine={len(genuine_paths)}, fake={len(fake_paths)}'
              f' (qwen3={len(qwen_paths)}, speaker={len(speaker_paths)}, other={len(other_fake)}), total={len(self.samples)}')

    def _load_wav(self, path):
        if path.lower().endswith('.m4a'):
            wav, sr = librosa.load(path, sr=ORIGIN_SR, mono=True)
        else:
            wav, sr = sf.read(path, dtype='float32')
            if wav.ndim == 2:
                wav = wav.mean(axis=1)
            if sr != ORIGIN_SR:
                wav = librosa.resample(wav, orig_sr=sr, target_sr=ORIGIN_SR)
        if len(wav) >= FIXED_LEN:
            wav = wav[:FIXED_LEN]
        else:
            wav = np.pad(wav, (0, FIXED_LEN - len(wav)))
        return torch.FloatTensor(wav).unsqueeze(0)  # (1, T)

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path, label = self.samples[idx]
        wav = self._load_wav(path)

        if self.is_train:
            wav = _augment(wav, label)

        return wav, label