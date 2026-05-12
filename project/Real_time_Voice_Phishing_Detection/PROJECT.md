# 프로젝트 구조 및 실행 가이드

---

## 주요 기술 선택 이유

| 기술 | 선택 이유 |
|------|----------|
| **WebSocket** | 실시간 오디오 스트리밍은 연결을 끊지 않고 지속적으로 데이터를 주고받아야 함. HTTP는 요청-응답 구조라 매 청크마다 연결 오버헤드 발생 → WebSocket으로 단일 연결 유지 |
| **FastAPI** | Python 비동기 프레임워크 중 WebSocket 지원이 간결하고 성능이 우수. Pydantic 기반 자동 스키마 검증 포함 |
| **faster-whisper** | OpenAI Whisper 대비 최대 4배 빠른 추론 속도. 실시간 STT에 적합한 경량화 버전 (CTranslate2 기반) |
| **onnxruntime** | 딥보이스 모델(RawNet2)을 ONNX 포맷으로 변환하면 PyTorch 없이도 추론 가능 → 서버 의존성 경량화 |
| **ThreadPoolExecutor** | STT·딥보이스 모델은 CPU 연산 집약적. FastAPI의 async 이벤트 루프를 블로킹하지 않도록 별도 스레드에서 실행 |
| **GPT-4o-mini** | 위험 탐지 시 사용자에게 구체적인 설명 제공. 경고 레벨 1 이상일 때만 호출하여 API 비용 최소화. 키 없으면 기본 메시지로 fallback |
| **Flutter** | Android / iOS / Windows 단일 코드베이스로 커버. 데모(Windows)와 실배포(Android/iOS) 동시 지원 |

---

## 파일 구조

```
voice-ai/
├── SCRUM.md                          # 스크럼 현황 및 모델 인터페이스 명세
├── PROJECT.md                        # 프로젝트 구조 및 실행 가이드 (현재 파일)
│
├── server/                           # Python 백엔드 서버
│   ├── app/
│   │   ├── main.py                   # FastAPI 앱 진입점, CORS 설정
│   │   ├── api/
│   │   │   └── websocket.py          # WebSocket 엔드포인트 (/ws/audio)
│   │   ├── core/
│   │   │   ├── config.py             # 환경 설정 (샘플레이트, 임계값, OpenAI 키 등)
│   │   │   └── schemas.py            # 파이프라인 입출력 Pydantic 스키마
│   │   ├── models/
│   │   │   ├── stt.py                # STT 모델 (현재 더미 → faster-whisper 교체 예정)
│   │   │   ├── deepfake.py           # 딥보이스 탐지 모델 (현재 더미 → RawNet2 교체 예정)
│   │   │   └── nlu.py                # 위험도 분석 모델 (현재 더미 → KoELECTRA 교체 예정)
│   │   └── services/
│   │       ├── audio_processor.py    # FFmpeg으로 오디오 → PCM 16kHz mono 16-bit 변환
│   │       ├── pipeline.py           # STT·딥보이스·NLU 병렬 실행 조율
│   │       └── explainer.py          # GPT-4o-mini로 위험 상황 설명 문장 생성
│   ├── main.py                       # 서버 직접 실행 진입점 (uvicorn)
│   ├── test_websocket.py             # WebSocket 연결 및 파이프라인 테스트 스크립트
│   ├── Dockerfile                    # Docker 이미지 빌드 설정
│   ├── docker-compose.yml            # 컨테이너 실행 설정 (포트 8000)
│   ├── pyproject.toml                # Python 의존성 목록 (uv 패키지 매니저)
│   └── .env                          # 환경 변수 (OpenAI API 키 등, git 제외)
│
└── client/                           # Flutter 앱 (Android / iOS / Windows)
    ├── lib/
    │   ├── main.dart                 # 앱 진입점, 네비게이션 셸, 배경 UI
    │   ├── config.dart               # 서버 WebSocket URL 설정
    │   ├── models/
    │   │   ├── analysis_result.dart  # 서버 JSON 응답 → Dart 객체 변환
    │   │   └── call_record.dart      # 통화 기록 데이터 모델
    │   ├── screens/
    │   │   ├── home_screen.dart      # 홈 화면 (보호 상태, 통계 카드, 주간 차트)
    │   │   ├── history_screen.dart   # 통화 이력 화면 (검색, 필터, 상세 보기)
    │   │   └── statistics_screen.dart# 통계 화면 (위험 분포, 주간 추이, 탐지율)
    │   └── services/
    │       ├── websocket_service.dart# 서버 WebSocket 연결 및 오디오 전송
    │       └── audio_service.dart    # 마이크 녹음 및 오디오 스트리밍
    ├── android/
    │   └── app/src/main/
    │       └── AndroidManifest.xml   # 권한 설정 (RECORD_AUDIO, INTERNET)
    ├── ios/
    │   └── Runner/
    │       └── Info.plist            # 마이크 권한 문구, 앱 이름 설정
    └── pubspec.yaml                  # Flutter 의존성 목록
```

---

## 서버 동작 방식

### 흐름

```
클라이언트 (Flutter)
    │  바이너리 오디오 청크 전송 (WebSocket)
    ▼
/ws/audio  [websocket.py]
    │  500ms 단위로 버퍼링
    ▼
audio_processor.py
    │  FFmpeg → PCM 16kHz / mono / 16-bit 변환
    ▼
pipeline.py  (ThreadPoolExecutor 병렬 처리)
    ├──▶ stt.py        transcribe()  → 텍스트
    │         └──▶ nlu.py  analyze() → risk_score (0~100)
    └──▶ deepfake.py   predict()     → is_fake, confidence
    │
    │  warning_level 결정
    │    is_fake=True          → level 3 (위험, 무조건)
    │    risk_score  0~24      → level 0 (안전)
    │    risk_score 25~49      → level 1 (주의)
    │    risk_score 50~74      → level 2 (경고)
    │    risk_score 75~100     → level 3 (위험)
    │
    └──▶ explainer.py  GPT-4o-mini → 설명 문장 생성 (위험 시에만)
    │
    │  JSON 응답
    ▼
클라이언트 → UI 업데이트
```

### 응답 JSON 형식

```json
{
  "text":                "STT 변환 텍스트",
  "risk_score":          75,
  "warning_level":       2,
  "is_fake_voice":       false,
  "deepfake_confidence": 0.91,
  "explanation":         "AI 분석 설명 문장"
}
```

---

## 데모 실행 방법

### 사전 조건
- Docker Desktop 설치
- `.env` 파일에 `OPENAI_API_KEY` 입력

### 서버 실행 (Docker)

```bash
cd server
docker-compose up --build
```

> 서버 주소: `http://localhost:8000`
> 헬스체크: `http://localhost:8000/health` → `{"status": "ok"}`

### 서버 실행 (로컬 직접)

```bash
cd server
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

### WebSocket 연결 테스트

```bash
cd server
uv run python test_websocket.py
```

### Flutter Windows 앱 실행 (데스크탑 데모)

```bash
cd client
flutter run -d windows
```

> `config.dart`의 `wsUrl`이 `ws://localhost:8000/ws/audio`로 설정되어 있어야 함

---

## Android 클라이언트

### 설정 완료 항목

| 항목 | 파일 | 내용 |
|------|------|------|
| 마이크 권한 | `AndroidManifest.xml` | `RECORD_AUDIO` 등록 |
| 인터넷 권한 | `AndroidManifest.xml` | `INTERNET` 등록 |
| HTTP 통신 허용 | `AndroidManifest.xml` | `usesCleartextTraffic="true"` (ws:// 접속용) |
| 앱 이름 | `AndroidManifest.xml` | `android:label="Vaia"` |

### 빌드 및 실행

```bash
# 에뮬레이터 실행
flutter run -d android

# APK 빌드
flutter build apk --release
# 출력 경로: build/app/outputs/flutter-apk/app-release.apk
```

### 서버 주소 변경 (`client/lib/config.dart`)

```dart
// 에뮬레이터에서 접속 시
static const String wsUrl = 'ws://10.0.2.2:8000/ws/audio';

// 실기기에서 접속 시 (같은 Wi-Fi)
static const String wsUrl = 'ws://[서버 IP]:8000/ws/audio';
```

---

## iOS 클라이언트

### 설정 완료 항목

| 항목 | 파일 | 내용 |
|------|------|------|
| 마이크 권한 문구 | `Info.plist` | `NSMicrophoneUsageDescription` 등록 |
| HTTP 통신 허용 | `Info.plist` | `NSAllowsArbitraryLoads = true` |
| 앱 이름 | `Info.plist` | `CFBundleDisplayName = "Vaia"` |

### Xcode 빌드 순서 (Mac 필요)

```
1. client/ios/Runner.xcworkspace 열기   ← .xcodeproj 아님, 반드시 .xcworkspace
2. Signing & Capabilities → Team 선택  ← Apple ID 로그인
3. Bundle Identifier 설정              ← 예: com.yourname.vaia
4. iPhone USB 연결 → Xcode에서 기기 선택
5. ▶ 버튼으로 빌드 및 설치
6. iPhone → 설정 → 일반 → VPN 및 기기 관리 → 개발자 앱 신뢰
```

### 서버 주소 변경 (`client/lib/config.dart`)

```dart
// 실기기에서 접속 시 (같은 Wi-Fi)
static const String wsUrl = 'ws://[서버 IP]:8000/ws/audio';
```

> **주의:** 무료 Apple 개발자 계정 사용 시 7일마다 Xcode에서 재서명 필요
