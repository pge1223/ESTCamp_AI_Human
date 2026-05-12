# Option C: WebSocket 서버 릴레이 — 실시간 VoIP 구현 계획

> **상태**: 미구현 (팀원 조율 후 진행 예정)
> **배경**: WAV 파일 기반 청크 STT는 파일 전체를 미리 알기 때문에 재생보다 ~5초 앞서 텍스트가 출력됨.
> 실제 전화처럼 미래 음성을 모르는 진짜 실시간 처리를 위해 두 기기 간 VoIP 구조로 전환.

---

## 아키텍처

```
[발신자 기기 A]                  [FastAPI 서버]                [수신자 기기 B]
 record 패키지                  /ws/call/{room}/{role}         WebSocket 수신
 마이크 → PCM 청크  ──WS──▶   room dict 릴레이   ──WS──▶   just_audio 재생
                                                              whisper.cpp STT
                                                              NLU 경고 UI
```

- 두 기기가 서버에 각각 아웃바운드 WebSocket 연결 — P2P 아님
- **같은 와이파이 불필요** (서버를 클라우드에 배포 시 4G/LTE 등 어떤 네트워크에서도 동작)
- 로컬 개발 시: 같은 와이파이에서 서버 IP로 접속

---

## 왜 Option C인가

| 옵션 | 설명 | 탈락 이유 |
|------|------|-----------|
| **A. 단일 기기 마이크** | record 패키지로 내 마이크만 실시간 처리 | 두 기기 간 실제 통화가 아님 |
| **B. WebRTC P2P** | flutter_webrtc로 Discord처럼 P2P | flutter_webrtc가 Flutter 레이어에서 raw PCM 콜백 미제공 → Kotlin/Swift 플랫폼 채널 별도 개발 필요 |
| **C. WebSocket 릴레이** | 서버가 PCM 청크를 발신자→수신자로 중계 | **선택** |

**Option C 선택 근거**
- `server/pyproject.toml`에 `websockets>=12.0` 이미 포함 — 추가 의존성 없음
- 기존 FastAPI 서버에 엔드포인트 하나만 추가하면 됨
- `WhisperSttService.transcribeChunk()` 이미 구현 완료 — 그대로 재사용
- 서버에서 NLU / 딥페이크 분석 동시 실행 가능

---

## 구현 상세

### 1. 서버: `server/app/api/call_ws.py` (신규 파일)

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
rooms: dict[str, list[WebSocket]] = {}

@router.websocket("/ws/call/{room_id}/{role}")
async def call_websocket(ws: WebSocket, room_id: str, role: str):
    await ws.accept()
    rooms.setdefault(room_id, []).append(ws)
    try:
        async for chunk in ws.iter_bytes():
            for other in rooms[room_id]:
                if other != ws:
                    await other.send_bytes(chunk)
    except WebSocketDisconnect:
        pass
    finally:
        rooms[room_id].remove(ws)
        if not rooms[room_id]:
            del rooms[room_id]
```

### 2. 서버: `server/app/main.py` — 라우터 등록 추가

```python
from app.api.call_ws import router as call_ws_router
app.include_router(call_ws_router)
```

### 3. 클라이언트 의존성: `client/pubspec.yaml`

```yaml
dependencies:
  record: ^5.0.0             # 마이크 PCM 스트림 실시간 캡처
  web_socket_channel: ^3.0.0 # WebSocket 클라이언트
```

기존 유지: `just_audio`, `whisper_flutter_new`, `http`, `path_provider`, `permission_handler`

### 4. 발신자(Caller) 화면 핵심 코드

```dart
import 'package:record/record.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

final _recorder = AudioRecorder();
WebSocketChannel? _channel;

Future<void> startCall(String roomId) async {
  _channel = WebSocketChannel.connect(
    Uri.parse('ws://서버주소/ws/call/$roomId/caller'),
  );
  final stream = await _recorder.startStream(RecordConfig(
    encoder: AudioEncoder.pcm16bits,
    sampleRate: 16000,
    numChannels: 1,
  ));
  stream.listen((chunk) => _channel!.sink.add(chunk));
}

void endCall() {
  _recorder.stop();
  _channel?.sink.close();
}
```

### 5. 수신자(Receiver) 화면 핵심 코드

```dart
import 'package:web_socket_channel/web_socket_channel.dart';

WebSocketChannel? _channel;
final List<int> _sttBuffer = [];
static const _chunkBytes = 16000 * 2 * 6; // 6초 분량 PCM (16kHz × 2bytes × 6s)

Future<void> joinCall(String roomId) async {
  _channel = WebSocketChannel.connect(
    Uri.parse('ws://서버주소/ws/call/$roomId/receiver'),
  );
  _channel!.stream.listen((dynamic data) {
    final bytes = data as Uint8List;

    // 1. 오디오 재생 (just_audio)
    _audioPlayer.feedChunk(bytes);

    // 2. STT 버퍼 누적 → 6초마다 whisper.cpp 처리
    _sttBuffer.addAll(bytes);
    if (_sttBuffer.length >= _chunkBytes) {
      final pcm = Uint8List.fromList(_sttBuffer.sublist(0, _chunkBytes));
      _sttBuffer.removeRange(0, _chunkBytes);
      WhisperSttService.instance.transcribeChunk(pcm).then((text) {
        if (text.isNotEmpty) {
          setState(() => _fullText += '$text ');
          _updateWarningLevel(text); // NLU 연동
        }
      });
    }
  });
}
```

---

## 오디오 포맷 (전 구간 통일)

| 항목 | 값 |
|------|-----|
| 샘플레이트 | 16,000 Hz |
| 채널 | Mono (1ch) |
| 비트 깊이 | 16-bit PCM |
| 6초 청크 크기 | 192,000 bytes (16000 × 2 × 6) |

`WhisperSttService._buildWavHeader()` 및 `transcribeChunk()`는 이미 이 포맷으로 구현됨.

---

## 룸 ID 연결 방식

| 방식 | 구현 난이도 | 용도 |
|------|-----------|------|
| **수동 입력** (TextField) | 낮음 | 데모/테스트 |
| QR 코드 (`qr_flutter` + `mobile_scanner`) | 중간 | 실사용 |

데모 시연에는 수동 입력이 가장 빠름.

---

## 배포 환경별 서버 주소

| 환경 | WebSocket URL | 같은 와이파이 필요 |
|------|--------------|-----------------|
| 로컬 개발 | `ws://192.168.x.x:8000/ws/call/...` | 필요 |
| ngrok 터널 | `wss://xxxx.ngrok.io/ws/call/...` | 불필요 |
| Railway / Render | `wss://앱이름.railway.app/ws/call/...` | 불필요 |

---

## 구현 순서

1. `server/app/api/call_ws.py` 생성 (WebSocket 릴레이 엔드포인트)
2. `server/app/main.py`에 라우터 등록
3. `client/pubspec.yaml`에 `record`, `web_socket_channel` 추가
4. 발신자 화면 구현 (마이크 → PCM → WebSocket 전송)
5. 수신자 화면 구현 (WebSocket 수신 → 재생 + STT 병렬)
6. 룸 ID 연결 UI (수동 입력 TextField)
7. 두 기기 로컬 테스트 (같은 와이파이)
8. (선택) ngrok 또는 Railway 배포 → 다른 네트워크 테스트

---

## 재사용 가능한 기존 코드

| 파일 | 재사용 항목 |
|------|-----------|
| `client/lib/services/whisper_stt_service.dart` | `transcribeChunk()`, `_buildWavHeader()` 그대로 사용 |
| `client/lib/screens/call_screen.dart` | `_updateWarningLevel()` 플레이스홀더 — NLU 연동 시 활용 |
| `server/pyproject.toml` | `websockets>=12.0` 이미 포함 |
| `server/app/api/session.py` | 기존 HTTP 세션 API와 공존 (영향 없음) |
