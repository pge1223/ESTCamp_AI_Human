from google.colab import drive
drive.mount('/content/drive')

import os, sys

# 코드 파일 경로 (model.py, dataset.py 위치)
PROJECT_DIR = '/content/drive/MyDrive/RealTimeVoicePhishing'
sys.path.insert(0, PROJECT_DIR)

# 패키지 설치
os.system('pip install soundfile scikit-learn -q')

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from scipy.optimize import brentq
from scipy.interpolate import interp1d
from sklearn.metrics import roc_curve

from model import RawNet2
from dataset import ASVspoof2019LA

# 경로 설정
DATA_ROOT = '/content/LA'
SAVE_DIR  = '/content/drive/MyDrive/checkpoints'
os.makedirs(SAVE_DIR, exist_ok=True)

# 하이퍼파라미터
# TRAIN_SAMPLES 단계별 가이드:
#   300  → 빠른 동작 확인 (2분)
#   1000 → 소규모 검증    (5분)
#   3000 → 중간 검증      (15분)
#   None → 전체 25,380개 본 학습
TRAIN_SAMPLES   = None   # 전체 학습 (25,380개)
DEV_SAMPLES     = None   # 전체 평가
BATCH_SIZE      = 24
EPOCHS          = 20
NUM_WORKERS     = 0

DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
LR     = 1e-4
print(f'device: {DEVICE}  |  TRAIN_SAMPLES={TRAIN_SAMPLES}')

# 데이터 로더
train_loader = DataLoader(
    ASVspoof2019LA(DATA_ROOT, 'train', max_samples=TRAIN_SAMPLES),
    batch_size=BATCH_SIZE, shuffle=True, num_workers=NUM_WORKERS, pin_memory=True
)
dev_loader = DataLoader(
    ASVspoof2019LA(DATA_ROOT, 'dev', max_samples=DEV_SAMPLES),
    batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS, pin_memory=True
)

# 모델 / 옵티마이저 / 손실함수
model     = RawNet2().to(DEVICE)
optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=EPOCHS)
criterion = nn.CrossEntropyLoss()


def compute_eer(labels, scores):
    if len(set(labels)) < 2:
        print('[경고] dev 셋에 클래스가 하나뿐 - EER 계산 건너뜀')
        return 50.0
    try:
        fpr, tpr, _ = roc_curve(labels, scores, pos_label=1)
        eer = brentq(lambda x: 1.0 - x - interp1d(fpr, tpr)(x), 0.0, 1.0)
        return eer * 100
    except ValueError:
        print('[경고] EER 계산 실패 - 50.0 반환')
        return 50.0


def train_one_epoch(model, loader, optimizer, criterion, device):
    model.train()
    total_loss, correct, n = 0.0, 0, 0
    for wav, label in loader:
        wav, label = wav.to(device), label.to(device)
        optimizer.zero_grad()
        logits = model(wav)
        loss = criterion(logits, label)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * len(label)
        correct += (logits.argmax(1) == label).sum().item()
        n += len(label)
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


# 학습 루프
best_eer = 100.0

for epoch in range(1, EPOCHS + 1):
    loss, acc = train_one_epoch(model, train_loader, optimizer, criterion, DEVICE)
    eer = evaluate_eer(model, dev_loader, DEVICE)
    scheduler.step()
    print(f'Epoch {epoch:02d}/{EPOCHS} | loss: {loss:.4f} | acc: {acc:.4f} | dev EER: {eer:.2f}%')
    if eer < best_eer:
        best_eer = eer
        torch.save(model.state_dict(), os.path.join(SAVE_DIR, 'best_model.pth'))
        print(f'  best model saved (EER {best_eer:.2f}%)')

print(f'\n학습 완료. best EER: {best_eer:.2f}%')
print(f'저장 위치: {SAVE_DIR}/best_model.pth')
