# Real-time Voice Phishing Detection

실시간 보이스피싱 탐지 Android 앱

## 프로젝트 구조

```
Real_time_Voice_Phishing_Detection/
├── client/                         # Flutter Android 앱
│   ├── lib/
│   │   ├── screens/
│   │   │   └── call_screen.dart    # 통화 화면 (STT + 위험도 표시)
│   │   ├── services/
│   │   │   ├── phishing_analyzer_service.dart  # KoELECTRA TFLite 피싱 분석
│   │   │   └── deepfake_detector_service.dart  # RawNet2 딥보이스 탐지
│   │   └── main.dart
│   ├── android/
│   │   └── app/src/main/kotlin/com/voiceguard/app/
│   │       ├── MainActivity.kt         # Flutter 엔진 등록
│   │       └── PcmCapturePlugin.kt     # 네이티브 16kHz PCM 마이크 캡처
│   └── assets/
│       ├── vocab.txt                   # KoELECTRA 토크나이저 어휘
│       ├── model_int8_no_erf.tflite    # ⚠️ 별도 다운로드 필요
│       └── korean_model.tflite         # ⚠️ 별도 다운로드 필요
└── server/                         # FastAPI 서버 (선택)
```

## 주요 기능

- **실시간 STT**: Android SpeechRecognizer로 통화 중 음성을 텍스트로 변환
- **피싱 분석**: KoELECTRA 멀티라벨 TFLite 모델로 보이스피싱 위험도 실시간 계산
- **딥보이스 탐지**: RawNet2 TFLite 모델로 AI 합성음성 탐지 (수동 실행)
- **복합 탐지 보정**: 여러 피싱 카테고리 동시 탐지 시 위험도 가중 합산
- **위험도 단조 증가**: 한 번 올라간 위험도는 내려가지 않음 (`_lockedRisk`)

## 실행 환경

| 항목 | 버전 |
|------|------|
| Flutter SDK | 3.x 이상 |
| Dart SDK | ^3.11.5 |
| Android SDK | API 21 이상 (minSdkVersion 21) |
| 테스트 기기 | Android 실기기 권장 (에뮬레이터 float16 미지원) |

## 설치 및 실행 방법

### 1. 레포지토리 클론

```bash
git clone https://github.com/kimyh81/test1.git
cd test1
```

### 2. TFLite 모델 파일 배치 (필수)

모델 파일은 용량 문제로 git에 포함되지 않습니다. 아래 두 파일을 `client/assets/` 폴더에 직접 복사하세요.

```
client/assets/
├── model_int8_no_erf.tflite    ← KoELECTRA 피싱 탐지 모델 (int8 양자화)
└── korean_model.tflite         ← RawNet2 딥보이스 탐지 모델
```

> 모델 파일은 별도 공유 경로(팀 내부)를 통해 받으세요.

### 3. Flutter 의존성 설치

```bash
cd client
flutter pub get
```

### 4. Android 기기 연결 후 실행

```bash
flutter run
```

> USB 디버깅이 활성화된 Android 실기기를 연결하세요.

## 권한

앱 실행 시 아래 권한이 필요합니다.

- `RECORD_AUDIO` - 마이크 (STT + PCM 캡처)
- `INTERNET` - STT 서비스

## 아키텍처

```
통화 시작
    │
    ▼
SpeechRecognizer (STT)
    │  partial + final 결과 모두 실시간 전달
    ▼
_onSpeechResult()
    │
    ├─ 키워드 필터 (임계값 15점 미만 → 위험도 max 30%)
    │
    └─ KoELECTRA TFLite 추론 (임계값 이상 → 모델 실행)
           │
           └─ maxProb 계산 (복합 탐지 시 +5%/label 보정)
                  │
                  └─ _lockedRisk 갱신 → UI 위험도 표시

[딥보이스 탐지 - 수동]
버튼 클릭 → PcmCapturePlugin (16kHz PCM 4초 캡처)
    └─ RawNet2 TFLite → genuine/spoof 확률 → UI 표시
```

## 브랜치

| 브랜치 | 설명 |
|--------|------|
| `main` | 안정 버전 |
| `feature/pge-ai-analyzer` | 현재 개발 브랜치 (KoELECTRA + RawNet2 통합) |

## 주요 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-05-08 | 딥보이스 탐지기 연동, 부분 STT 실시간 분석, maxProb 복합 보정 |
| 2026-05-07 | `_lockedRisk` 위험도 유지 로직, Endian 버그 수정, 키워드 필터 동기화 |
