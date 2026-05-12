package com.voiceguard.app

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder.AudioSource
import android.os.Handler
import android.os.Looper
import android.util.Log
import io.flutter.plugin.common.EventChannel
import kotlin.concurrent.thread

/**
 * PcmCapturePlugin
 *
 * AudioSource.VOICE_RECOGNITION 으로 마이크 PCM을 캡처해
 * Flutter EventChannel(com.voiceguard.app/pcm_capture) 로 스트리밍한다.
 *
 * SpeechRecognizer 와 동일한 AudioSource 를 사용하므로
 * Android 10+ 동시 캡처 정책(동일 앱 내, 동일 source) 충돌이 없다.
 */
class PcmCapturePlugin : EventChannel.StreamHandler {

    companion object {
        const val CHANNEL = "com.voiceguard.app/pcm_capture"
        private const val TAG = "PcmCapture"
        private const val SAMPLE_RATE = 16000
        // 160 ms 단위 청크 (딥보이스 추론 누적 효율 고려)
        private const val CHUNK_SAMPLES = 2560          // 160 ms @ 16 kHz
        private const val CHUNK_BYTES   = CHUNK_SAMPLES * 2 // int16 → 2 bytes
    }

    private var audioRecord: AudioRecord? = null
    private var recordThread: Thread?     = null
    @Volatile private var running = false
    private var sink: EventChannel.EventSink? = null
    private val mainHandler = Handler(Looper.getMainLooper())

    // ── EventChannel.StreamHandler ────────────────────────────
    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        sink = events
        startCapture()
    }

    override fun onCancel(arguments: Any?) {
        stopCapture()
        sink = null
    }

    // ── 캡처 시작 ─────────────────────────────────────────────
    private fun startCapture() {
        val minBuf = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuf == AudioRecord.ERROR || minBuf == AudioRecord.ERROR_BAD_VALUE) {
            mainHandler.post {
                sink?.error("INIT_ERROR", "getMinBufferSize 실패: $minBuf", null)
            }
            return
        }
        val bufSize = maxOf(minBuf, CHUNK_BYTES * 8)

        val ar = AudioRecord(
            AudioSource.VOICE_RECOGNITION,
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufSize,
        )
        if (ar.state != AudioRecord.STATE_INITIALIZED) {
            ar.release()
            mainHandler.post {
                sink?.error("INIT_ERROR", "AudioRecord 초기화 실패 (권한 확인)", null)
            }
            return
        }

        audioRecord = ar
        running     = true
        ar.startRecording()
        Log.d(TAG, "캡처 시작: VOICE_RECOGNITION ${SAMPLE_RATE}Hz mono int16 " +
                "chunkBytes=$CHUNK_BYTES bufSize=$bufSize")

        recordThread = thread(name = "PcmCaptureThread", isDaemon = true) {
            val buf = ByteArray(CHUNK_BYTES)
            while (running) {
                val read = ar.read(buf, 0, CHUNK_BYTES)
                when {
                    read > 0  -> {
                        val chunk = buf.copyOf(read)
                        mainHandler.post { sink?.success(chunk) }
                    }
                    read == AudioRecord.ERROR_INVALID_OPERATION -> {
                        Log.w(TAG, "read: ERROR_INVALID_OPERATION – 중지")
                        break
                    }
                    read < 0  -> Log.w(TAG, "read 오류: $read")
                }
            }
            Log.d(TAG, "캡처 스레드 종료")
        }
    }

    // ── 캡처 중지 ─────────────────────────────────────────────
    private fun stopCapture() {
        running = false
        recordThread?.join(800)
        recordThread = null
        try {
            audioRecord?.stop()
            audioRecord?.release()
        } catch (e: Exception) {
            Log.w(TAG, "stopCapture 오류: ${e.message}")
        }
        audioRecord = null
        Log.d(TAG, "캡처 중지")
    }
}
