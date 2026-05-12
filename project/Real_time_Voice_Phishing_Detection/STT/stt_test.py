import pyaudio
import numpy as np
import queue
import threading
import time
from faster_whisper import WhisperModel

# ── 설정 ──────────────────────────────────────────────
SAMPLE_RATE = 16000
CHANNELS = 1
FORMAT = pyaudio.paInt16
CHUNK_SIZE = 1024
RECORD_SECONDS = 2.0
SILENCE_THRESHOLD = 500
WINDOW_SECONDS = 8.0

# ── 모델 로드 ──────────────────────────────────────────
print("🔄 Whisper 모델 로딩 중...")
load_start = time.time()
model = WhisperModel("small", device="cpu", compute_type="int8")
print(f"✅ 모델 로드 완료 ({time.time() - load_start:.1f}초)\n")

audio_queue = queue.Queue()

# ── 성능 측정용 카운터 ─────────────────────────────────
stats = {
    "total_segments": 0,
    "skipped_silence": 0,
    "dropped_segments": 0,
    "window_resets": 0,
    "total_stt_time": 0.0,
    "total_latency": 0.0,
    "results": 0,
}
stats_lock = threading.Lock()


# ── 마이크 캡처 ────────────────────────────────────────
def capture_audio(stop_event):
    pa = pyaudio.PyAudio()

    print("🎤 사용 가능한 마이크 목록:")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(f"  [{i}] {info['name']}")
    print()

    stream = pa.open(
        format=FORMAT, channels=CHANNELS,
        rate=SAMPLE_RATE, input=True,
        frames_per_buffer=CHUNK_SIZE,
    )
    frames_per_segment = int(SAMPLE_RATE * RECORD_SECONDS)
    buffer = []
    print("🎙️  마이크 입력 시작 — 말씀해보세요!\n")

    try:
        while not stop_event.is_set():
            raw = stream.read(CHUNK_SIZE, exception_on_overflow=False)
            pcm = np.frombuffer(raw, dtype=np.int16)
            buffer.extend(pcm.tolist())

            if len(buffer) >= frames_per_segment:
                segment = np.array(buffer[:frames_per_segment], dtype=np.int16)
                audio_queue.put((segment, time.time()))
                buffer = buffer[frames_per_segment // 2:]
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


# ── 무음 판별 ──────────────────────────────────────────
def is_speech(audio_int16):
    rms = np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2))
    return rms > SILENCE_THRESHOLD


# ── 슬라이딩 윈도우 + 중복 제거 ───────────────────────
window_samples = int(SAMPLE_RATE * WINDOW_SECONDS)
audio_window = np.array([], dtype=np.int16)
prev_text = ""

def postprocess(text: str) -> str:
    global prev_text
    if text.startswith(prev_text):
        new_part = text[len(prev_text):].strip()
    else:
        new_part = text.strip()
    prev_text = text
    return new_part


# ── STT 처리 ───────────────────────────────────────────
def transcribe_audio(stop_event, result_callback):
    global audio_window

    while not stop_event.is_set():
        try:
            segment_int16, enqueue_time = audio_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        # ✅ 큐에 밀린 세그먼트가 있으면 최신 것만 사용
        dropped = 0
        while not audio_queue.empty():
            try:
                segment_int16, enqueue_time = audio_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            with stats_lock:
                stats["dropped_segments"] += dropped
            print(f"  [⚠️  밀린 세그먼트 {dropped}개 드롭]", end="\r")

        # ✅ 지연이 2초 초과면 윈도우 리셋 후 스킵
        current_latency = time.time() - enqueue_time
        if current_latency > 2.0:
            audio_window = np.array([], dtype=np.int16)
            with stats_lock:
                stats["window_resets"] += 1
            print(f"  [🔄 윈도우 리셋 | 지연 {current_latency:.1f}s]", end="\r")
            continue

        if not is_speech(segment_int16):
            with stats_lock:
                stats["skipped_silence"] += 1
            print(f"  [무음 스킵 | RMS: {np.sqrt(np.mean(segment_int16.astype(np.float32)**2)):.0f}]", end="\r")
            continue

        audio_window = np.concatenate([audio_window, segment_int16])
        if len(audio_window) > window_samples:
            audio_window = audio_window[-window_samples:]

        audio_float32 = audio_window.astype(np.float32) / 32768.0

        stt_start = time.time()
        segments, _ = model.transcribe(
            audio_float32,
            language="ko",
            beam_size=5,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 300,
                "speech_pad_ms": 100,
            },
        )
        stt_elapsed = time.time() - stt_start
        total_latency = current_latency + stt_elapsed

        full_text = "".join(seg.text for seg in segments).strip()

        with stats_lock:
            stats["total_segments"] += 1
            stats["total_stt_time"] += stt_elapsed
            stats["total_latency"] += total_latency

        if not full_text:
            print(f"  [빈 결과 | STT {stt_elapsed:.2f}s]", end="\r")
            continue

        new_part = postprocess(full_text)
        if new_part:
            with stats_lock:
                stats["results"] += 1
            result_callback(new_part, stt_elapsed, total_latency)


# ── 결과 출력 ──────────────────────────────────────────
def on_transcribed(text: str, stt_time: float, latency: float):
    timestamp = time.strftime("%H:%M:%S")
    print(f"\n[{timestamp}] 📝 {text}")
    print(f"           ├─ STT 처리시간 : {stt_time:.2f}s")
    print(f"           └─ 총 지연시간  : {latency:.2f}s")


# ── 주기적 통계 출력 ───────────────────────────────────
def print_stats(stop_event):
    while not stop_event.is_set():
        time.sleep(10)
        with stats_lock:
            total    = stats["total_segments"]
            results  = stats["results"]
            skipped  = stats["skipped_silence"]
            dropped  = stats["dropped_segments"]
            resets   = stats["window_resets"]
            avg_stt  = stats["total_stt_time"] / total if total > 0 else 0
            avg_lat  = stats["total_latency"]  / total if total > 0 else 0

        print(f"\n{'─'*45}")
        print(f"📊 [10초 누적 통계]")
        print(f"  처리 세그먼트  : {total}개")
        print(f"  텍스트 출력    : {results}회")
        print(f"  무음 스킵      : {skipped}회")
        print(f"  드롭 세그먼트  : {dropped}개")
        print(f"  윈도우 리셋    : {resets}회")
        print(f"  평균 STT시간   : {avg_stt:.2f}s")
        print(f"  평균 총지연    : {avg_lat:.2f}s")
        print(f"{'─'*45}\n")


# ── 메인 ───────────────────────────────────────────────
if __name__ == "__main__":
    stop_event = threading.Event()

    t_capture = threading.Thread(target=capture_audio,    args=(stop_event,),               daemon=True)
    t_stt     = threading.Thread(target=transcribe_audio, args=(stop_event, on_transcribed), daemon=True)
    t_stats   = threading.Thread(target=print_stats,      args=(stop_event,),               daemon=True)

    t_capture.start()
    t_stt.start()
    t_stats.start()

    print("실시간 STT 테스트 시작 — 종료하려면 Ctrl+C")
    print("(10초마다 성능 통계가 출력됩니다)\n")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\n🛑 종료 중...")
        stop_event.set()

    t_capture.join(timeout=3)
    t_stt.join(timeout=3)

    # 최종 통계
    with stats_lock:
        total   = stats["total_segments"]
        avg_stt = stats["total_stt_time"] / total if total > 0 else 0
        avg_lat = stats["total_latency"]  / total if total > 0 else 0

    print(f"\n{'='*45}")
    print(f"🏁 최종 결과")
    print(f"  총 처리 세그먼트 : {stats['total_segments']}개")
    print(f"  총 텍스트 출력   : {stats['results']}회")
    print(f"  총 무음 스킵     : {stats['skipped_silence']}회")
    print(f"  총 드롭 세그먼트 : {stats['dropped_segments']}개")
    print(f"  총 윈도우 리셋   : {stats['window_resets']}회")
    print(f"  평균 STT 처리시간: {avg_stt:.2f}s")
    print(f"  평균 총 지연시간 : {avg_lat:.2f}s")
    print(f"{'='*45}")