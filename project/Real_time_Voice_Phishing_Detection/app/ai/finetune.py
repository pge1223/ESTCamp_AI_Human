from google.colab import drive
drive.mount('/content/drive')

import os, sys, random

PROJECT_DIR = '/content/drive/MyDrive/RealTimeVoicePhishing'
sys.path.insert(0, PROJECT_DIR)

os.system('pip install soundfile scikit-learn -q')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from sklearn.metrics import roc_curve

from model import RawNet2
from korean_dataset import KoreanDeepVoiceDataset

# 경로 설정
GENUINE_DIR = '/content/drive/MyDrive/data/korean/genuine'
FAKE_DIR    = '/content/drive/MyDrive/data/korean/fake'
PRETRAINED  = '/content/drive/MyDrive/checkpoints/best_model.pth'
SAVE_DIR    = '/content/drive/MyDrive/checkpoints'
os.makedirs(SAVE_DIR, exist_ok=True)

# 하이퍼파라미터
MAX_SAMPLES = 11000
BATCH_SIZE  = 16
EPOCHS      = 25
NUM_WORKERS = 0
LR          = 1e-5

# Clova TTS holdout 화자 — dev 전용, train에 절대 포함되지 않음
HOLDOUT_SPEAKERS = {'nkyunglee', 'njooahn'}

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f'device: {DEVICE}')  

# 전체 샘플 수집 (augmentation 없이)
_base = KoreanDeepVoiceDataset(
    genuine_dir=GENUINE_DIR,
    fake_dir=FAKE_DIR,
    max_samples=MAX_SAMPLES,
    is_train=False,
)
all_samples = _base.samples

# Speaker-based split
# - Clova holdout 화자(fake) → dev 고정
# - 나머지 (repeat_TTS 포함) → 80/20 랜덤 split
holdout, rest = [], []
for path, label in all_samples:
    speaker = os.path.basename(path).split('_')[0]
    if label == 1 and speaker in HOLDOUT_SPEAKERS:
        holdout.append((path, label))
    else:
        rest.append((path, label))

random.shuffle(rest)
n_dev         = int(len(rest) * 0.2)
train_samples = rest[n_dev:]
dev_samples   = holdout + rest[:n_dev]

# train: augmentation O / dev: augmentation X (고정된 기준으로 EER 측정)
train_set = KoreanDeepVoiceDataset(None, None, samples=train_samples, is_train=True)
dev_set   = KoreanDeepVoiceDataset(None, None, samples=dev_samples,   is_train=False)

print(f'train={len(train_set)}, dev={len(dev_set)} '
      f'(holdout {len(holdout)}개 + random {n_dev}개)')

train_loader = DataLoader(train_set, batch_size=BATCH_SIZE, shuffle=True,  num_workers=NUM_WORKERS, pin_memory=True)
dev_loader   = DataLoader(dev_set,   batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True)

# 사전학습 모델 로드
model = RawNet2().to(DEVICE)
if os.path.exists(PRETRAINED):
    model.load_state_dict(torch.load(PRETRAINED, map_location=DEVICE))
    print(f'사전학습 가중치 로드 완료: {PRETRAINED}')
else:
    print('[경고] 사전학습 가중치 없음 - 처음부터 학습합니다')

optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
criterion = nn.CrossEntropyLoss()


def compute_eer(labels, scores):
    if len(set(labels)) < 2:
        return 50.0
    try:
        fpr, tpr, _ = roc_curve(labels, scores, pos_label=1)
        eer = brentq(lambda x: 1.0 - x - interp1d(fpr, tpr)(x), 0.0, 1.0)
        return eer * 100
    except ValueError:
        return 50.0


def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, correct, n = 0.0, 0, 0
    for wav, label in loader:
        wav, label = wav.to(device), label.to(device)
        optimizer.zero_grad()
        logits = model(wav)
        loss   = criterion(logits, label)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(label)
        correct    += (logits.argmax(1) == label).sum().item()
        n          += len(label)
    return total_loss / n, correct / n


def evaluate_eer(model, loader, device):
    model.eval()
    all_labels, all_scores = [], []
    with torch.no_grad():
        for wav, label in loader:
            logits = model(wav.to(device))
            scores = torch.softmax(logits, 1)[:, 1]
            all_labels.extend(label.numpy())
            all_scores.extend(scores.cpu().numpy())
    return compute_eer(np.array(all_labels), np.array(all_scores))


# 파인튜닝 루프
best_eer = 100.0

for epoch in range(1, EPOCHS + 1):
    loss, acc = train_one_epoch(model, train_loader, optimizer, criterion, DEVICE)
    eer       = evaluate_eer(model, dev_loader, DEVICE)
    scheduler.step()
    print(f'Epoch {epoch:02d}/{EPOCHS} | loss: {loss:.4f} | acc: {acc:.4f} | dev EER: {eer:.2f}%')
    if eer < best_eer:
        best_eer = eer
        torch.save(model.state_dict(), os.path.join(SAVE_DIR, 'korean_model.pth'))
        print(f'  best model saved (EER {best_eer:.2f}%)')

print(f'\n파인튜닝 완료. best EER: {best_eer:.2f}%')
print(f'저장 위치: {SAVE_DIR}/korean_model.pth')
