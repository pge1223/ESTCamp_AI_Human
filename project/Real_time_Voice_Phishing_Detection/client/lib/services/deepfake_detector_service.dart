import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:tflite_flutter/tflite_flutter.dart';

/// RawNet2 기반 딥보이스 탐지 서비스
/// - 입력: 16kHz mono float32, 64600 샘플(≈4초)
/// - 출력: [genuine_score, spoof_score] → softmax → fakeProb
/// - 오디오 캡처: Android 플랫폼 채널 PcmCapturePlugin(AudioSource.VOICE_RECOGNITION)
///   → STT(SpeechRecognizer)와 동일한 AudioSource 사용, 마이크 점유 충돌 없음
class DeepfakeDetectorService {
  DeepfakeDetectorService._();
  static final instance = DeepfakeDetectorService._();

  static const _modelFile        = 'assets/korean_model.tflite';
  static const _targetSampleRate = 16000;
  static const _inputSamples     = 64600; // 모델 고정 입력 [1, 64600, 1] ≈ 4초


  // 플랫폼 채널 — PcmCapturePlugin.kt 와 채널명 일치
  static const _pcmChannel = EventChannel('com.voiceguard.app/pcm_capture');

  Interpreter? _interpreter;
  StreamSubscription<dynamic>? _streamSub;
  final List<double> _pcmBuffer = [];
  int _generation = 0;

  bool get isReady => _interpreter != null;

  // ── 초기화 ──────────────────────────────────────────────────
  Future<void> initialize() async {
    if (_interpreter != null) return;
    debugPrint('[Deepfake] initialize() 시작');
    final gen = _generation;
    try {
      final options = InterpreterOptions()..threads = 2;
      final interpreter = await Interpreter.fromAsset(_modelFile, options: options);

      // await 사이에 dispose()가 호출됐으면 새 interpreter를 즉시 해제
      if (gen != _generation) {
        interpreter.close();
        debugPrint('[Deepfake] 초기화 중 dispose 감지 → interpreter 즉시 해제');
        return;
      }

      interpreter.allocateTensors();
      _interpreter = interpreter;

      final inp = _interpreter!.getInputTensors()[0];
      final out = _interpreter!.getOutputTensors()[0];
      debugPrint('[Deepfake] 입력텐서: ${inp.name} shape=${inp.shape} type=${inp.type}');
      debugPrint('[Deepfake] 출력텐서: ${out.name} shape=${out.shape} type=${out.type}');
      debugPrint('[Deepfake] 모델 로드 완료');
    } catch (e) {
      _interpreter = null;
      debugPrint('[Deepfake] 모델 로드 실패: $e');
    }
  }

  // ── 마이크 PCM 스트리밍 시작 (플랫폼 채널 사용) ──────────────
  /// Android PcmCapturePlugin(AudioSource.VOICE_RECOGNITION) 에서 PCM 수신.
  /// SpeechRecognizer 와 동일한 AudioSource → 마이크 점유 충돌 없음.
  /// [onResult]: 64600 샘플마다 추론 결과를 콜백으로 전달
  Future<void> startMicStreaming(void Function(DeepfakeResult) onResult) async {
    if (!isReady) {
      debugPrint('[Deepfake] startMicStreaming: 모델 미준비');
      return;
    }

    await stopMicStreaming(); // 이전 스트림 정리
    _pcmBuffer.clear();

    // 마이크 권한 확인
    final status = await Permission.microphone.status;
    if (!status.isGranted) {
      final result = await Permission.microphone.request();
      if (!result.isGranted) {
        debugPrint('[Deepfake] 마이크 권한 없음');
        return;
      }
    }

    debugPrint('[Deepfake] 마이크 PCM 스트리밍 시작 '
        '(플랫폼 채널, VOICE_RECOGNITION 16kHz mono int16)');
    var chunkCount = 0;

    _streamSub = _pcmChannel.receiveBroadcastStream().listen(
      (dynamic chunk) {
        if (chunk is! Uint8List) return;
        chunkCount++;
        if (chunkCount <= 5 || chunkCount % 50 == 0) {
          debugPrint('[Deepfake] chunk[$chunkCount] size=${chunk.length}B '
              'buf=${_pcmBuffer.length}/$_inputSamples');
        }

        // int16 LE → float32 변환 후 버퍼에 누적
        for (var i = 0; i + 1 < chunk.length; i += 2) {
          var s = ((chunk[i + 1] & 0xFF) << 8) | (chunk[i] & 0xFF);
          if (s >= 0x8000) s -= 0x10000; // 부호 처리
          _pcmBuffer.add(s / 32768.0);
        }

        // 64600 샘플 누적 시 추론
        if (_pcmBuffer.length >= _inputSamples) {
          final samples = Float32List.fromList(
            _pcmBuffer.sublist(0, _inputSamples),
          );
          // 슬라이딩: 절반씩 넘겨서 연속 분석 (2초 간격)
          _pcmBuffer.removeRange(0, _inputSamples ~/ 2);

          try {
            final result = _runInference(samples);
            debugPrint('[Deepfake] 결과: ${result.label} (${result.fakePercent}%)');
            onResult(result);
          } catch (e) {
            debugPrint('[Deepfake] 추론 오류: $e');
          }
        }
      },
      onError: (e) => debugPrint('[Deepfake] 스트림 오류: $e'),
    );
  }

  // ── 마이크 스트리밍 중지 ─────────────────────────────────────
  Future<void> stopMicStreaming() async {
    await _streamSub?.cancel();
    _streamSub = null;
    _pcmBuffer.clear();
    debugPrint('[Deepfake] 마이크 스트리밍 중지');
  }

  // ── 단발 캡처 추론 (버튼 트리거) ────────────────────────────
  /// 버튼 누름 시 기존 버퍼 clear 후 새 마이크 샘플만 사용.
  /// 64600샘플 수집 → 추론 → 8000샘플 스킵 → 반복 (총 3회).
  /// 64600샘플 미만이면 모델 미실행, 0 패딩 없음.
  /// 최종 판단: fakeProb > 0.4가 2회 이상 또는 > 0.8이 1회 이상이면 fake.
  Future<DeepfakeResult> captureAndAnalyze() async {
    if (!isReady) return DeepfakeResult.notReady();

    _pcmBuffer.clear();
    final completer = Completer<DeepfakeResult>();
    StreamSubscription<dynamic>? sub;
    final probs = <double>[];

    const totalWindows = 3;
    const skipSamples  = 8000;
    var skipRemain     = 0;

    debugPrint('[Deepfake] captureAndAnalyze 시작 — 버퍼 clear, 새 샘플 수집');

    sub = _pcmChannel.receiveBroadcastStream().listen(
      (dynamic chunk) {
        if (chunk is! Uint8List || completer.isCompleted) return;

        var byteIdx = 0;
        while (byteIdx + 1 < chunk.length && !completer.isCompleted) {
          if (skipRemain > 0) {
            final availSamples = (chunk.length - byteIdx) ~/ 2;
            final toSkip = math.min(skipRemain, availSamples);
            skipRemain -= toSkip;
            byteIdx += toSkip * 2;
          } else {
            final needed    = _inputSamples - _pcmBuffer.length;
            final available = (chunk.length - byteIdx) ~/ 2;
            final toCollect = math.min(needed, available);

            for (var i = 0; i < toCollect; i++) {
              var s = ((chunk[byteIdx + 1] & 0xFF) << 8) | (chunk[byteIdx] & 0xFF);
              if (s >= 0x8000) s -= 0x10000;
              _pcmBuffer.add(s / 32768.0);
              byteIdx += 2;
            }

            if (_pcmBuffer.length >= _inputSamples) {
              final windowIdx = probs.length + 1;
              debugPrint('[Deepfake] 윈도우[$windowIdx/$totalWindows] 64600샘플 수집 완료 → 추론');
              final samples = Float32List.fromList(_pcmBuffer);
              _pcmBuffer.clear();

              final rms = _computeRms(samples);
              debugPrint('[Deepfake] 윈도우[$windowIdx] RMS=${rms.toStringAsFixed(4)}');

              double prob;
              if (rms < 0.01) {
                debugPrint('[Deepfake] 윈도우[$windowIdx] 침묵 구간 → 추론 스킵 (prob=0.0)');
                prob = 0.0;
              } else {
                try {
                  prob = _inferFakeProb(samples);
                } catch (e) {
                  debugPrint('[Deepfake] 윈도우[$windowIdx] 추론 오류: $e');
                  prob = 0.0;
                }
              }
              probs.add(prob);
              debugPrint('[Deepfake] 윈도우[$windowIdx] fakeProb=${(prob * 100).toStringAsFixed(1)}%');

              if (probs.length >= totalWindows) {
                sub?.cancel();
                _pcmBuffer.clear();
                if (!completer.isCompleted) {
                  final result = _makeFinalResult(probs);
                  debugPrint('[Deepfake] 최종 판단: ${result.label} (${result.fakePercent}%) probs=$probs');
                  completer.complete(result);
                }
                return;
              }
              debugPrint('[Deepfake] 윈도우[$windowIdx] 완료 → $skipSamples샘플 스킵');
              skipRemain = skipSamples;
            }
          }
        }
      },
      onError: (e) {
        debugPrint('[Deepfake] 스트림 오류: $e');
        if (!completer.isCompleted) completer.complete(_makeFinalResult(probs));
      },
    );

    final timeoutSec =
        ((_inputSamples * totalWindows + skipSamples * (totalWindows - 1)) /
                _targetSampleRate)
            .ceil() +
        10;
    debugPrint('[Deepfake] 타임아웃: $timeoutSec초');
    Future.delayed(Duration(seconds: timeoutSec), () {
      if (!completer.isCompleted) {
        sub?.cancel();
        _pcmBuffer.clear();
        debugPrint('[Deepfake] 타임아웃 — ${probs.length}/$totalWindows 윈도우 완료');
        completer.complete(_makeFinalResult(probs));
      }
    });

    return completer.future;
  }

  // ── WAV 에셋 단발 분석 (시뮬레이션 fallback) ────────────────
  Future<DeepfakeResult> analyzeAsset(String assetPath) async {
    if (!isReady) return DeepfakeResult.notReady();
    try {
      final data = await rootBundle.load(assetPath);
      final pcm = _parseWav(data);
      if (pcm == null) {
        debugPrint('[Deepfake] WAV 파싱 실패: $assetPath');
        return DeepfakeResult.notReady();
      }
      return _runInference(pcm);
    } catch (e) {
      debugPrint('[Deepfake] analyzeAsset 오류: $e');
      return DeepfakeResult.notReady();
    }
  }

  void dispose() {
    _generation++; // initialize() 진행 중이면 완료 시 interpreter를 즉시 해제하도록 무효화
    _interpreter?.close();
    _interpreter = null;
    _streamSub?.cancel();
    _streamSub = null;
    _pcmBuffer.clear();
  }

  // ── WAV 파서 ────────────────────────────────────────────────
  Float32List? _parseWav(ByteData data) {
    final bytes = data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes);
    if (bytes.length < 44) return null;

    final riff = String.fromCharCodes(bytes.sublist(0, 4));
    final wave = String.fromCharCodes(bytes.sublist(8, 12));
    if (riff != 'RIFF' || wave != 'WAVE') return null;

    int offset = 12;
    int? numChannels, sampleRate, bitsPerSample, dataStart, dataLength;

    while (offset + 8 <= bytes.length) {
      final chunkId   = String.fromCharCodes(bytes.sublist(offset, offset + 4));
      final chunkSize = ByteData.view(bytes.buffer, bytes.offsetInBytes + offset + 4, 4)
          .getUint32(0, Endian.little);

      if (chunkId == 'fmt ') {
        final fmt = ByteData.view(
            bytes.buffer, bytes.offsetInBytes + offset + 8, math.min(chunkSize, 18));
        numChannels   = fmt.getUint16(2, Endian.little);
        sampleRate    = fmt.getUint32(4, Endian.little);
        bitsPerSample = fmt.getUint16(14, Endian.little);
      } else if (chunkId == 'data') {
        dataStart  = offset + 8;
        dataLength = chunkSize;
        break;
      }
      offset += 8 + chunkSize;
      if (chunkSize == 0) break;
    }

    if (numChannels == null || sampleRate == null || bitsPerSample == null ||
        dataStart == null || dataLength == null) {
      return null;
    }

    debugPrint('[Deepfake] WAV: ${numChannels}ch ${sampleRate}Hz '
        '${bitsPerSample}bit ${dataLength}bytes');

    final bytesPerSample = bitsPerSample ~/ 8;
    final frameCount = dataLength ~/ (bytesPerSample * numChannels);
    final mono = Float32List(frameCount);
    final dv = ByteData.view(bytes.buffer, bytes.offsetInBytes + dataStart, dataLength);

    for (var i = 0; i < frameCount; i++) {
      double sum = 0;
      for (var ch = 0; ch < numChannels; ch++) {
        final off = (i * numChannels + ch) * bytesPerSample;
        if (bytesPerSample == 2) {
          sum += dv.getInt16(off, Endian.little) / 32768.0;
        } else if (bytesPerSample == 4) {
          sum += dv.getFloat32(off, Endian.little);
        } else if (bytesPerSample == 3) {
          final b0 = dv.getUint8(off);
          final b1 = dv.getUint8(off + 1);
          final b2 = dv.getUint8(off + 2);
          final v  = (b2 & 0x80) != 0
              ? (0xFF000000 | (b2 << 16) | (b1 << 8) | b0)
              : ((b2 << 16) | (b1 << 8) | b0);
          sum += v / 8388608.0;
        }
      }
      mono[i] = (sum / numChannels).clamp(-1.0, 1.0);
    }

    if (sampleRate != _targetSampleRate) {
      return _resample(mono, sampleRate, _targetSampleRate);
    }
    return mono;
  }

  Float32List _resample(Float32List src, int srcRate, int dstRate) {
    final ratio  = srcRate / dstRate;
    final dstLen = (src.length / ratio).floor();
    final dst    = Float32List(dstLen);
    for (var i = 0; i < dstLen; i++) {
      final pos = i * ratio;
      final lo  = pos.floor();
      final hi  = math.min(lo + 1, src.length - 1);
      dst[i] = src[lo] + (src[hi] - src[lo]) * (pos - lo);
    }
    return dst;
  }

  // ── RMS 에너지 계산 (VAD용) ─────────────────────────────────
  // 0.01 미만 = 침묵/잡음 구간으로 판단 (int16 기준 약 328/32768)
  double _computeRms(Float32List samples) {
    double sum = 0.0;
    for (final s in samples) {
      sum += s * s;
    }
    return math.sqrt(sum / samples.length);
  }

  // ── 전화 채널 시뮬레이션 (16kHz→8kHz→16kHz, 4kHz 이상 제거) ──
  Float32List _phoneChannel(Float32List wav) {
    final down = _resample(wav, 16000, 8000);
    var up = _resample(down, 8000, 16000);
    if (up.length > wav.length) {
      up = Float32List.fromList(up.sublist(0, wav.length));
    } else if (up.length < wav.length) {
      final padded = Float32List(wav.length);
      padded.setRange(0, up.length, up);
      up = padded;
    }
    return up;
  }

  // ── 단일 창 추론 — fakeProb 반환, 패딩 없음 ─────────────────
  double _inferFakeProb(Float32List samples) {
    final filtered = _phoneChannel(samples);
    final output = [[0.0, 0.0]];
    _interpreter!.run(filtered.buffer.asUint8List(), output);
    final genuine = output[0][0];
    final spoof   = output[0][1];
    final maxV    = math.max(genuine, spoof);
    final expG    = math.exp(genuine - maxV);
    final expS    = math.exp(spoof - maxV);
    final fakeProb = expS / (expG + expS);
    debugPrint('[Deepfake] raw: genuine=$genuine spoof=$spoof → fakeProb=${(fakeProb * 100).toStringAsFixed(1)}%');
    return fakeProb;
  }

  // ── 3회 결과 최종 판단 ────────────────────────────────────
  // 판단 기준 (진짜 목소리 보호 우선):
  //  1) 3개 윈도우 모두 수집 + W2(중간) < 5% → 진짜 음성 확정 (veto)
  //     - 실제 오탐 패턴: W1·W3 극단 高, W2 ≈ 0% (중간만 진짜)
  //  2) 그 외: count(>0.5) >= 2 OR any(>0.85) → 가짜
  //     - 임계값 상향 (기존 0.4/0.8 → 0.5/0.85) 으로 오탐 감소
  DeepfakeResult _makeFinalResult(List<double> probs) {
    if (probs.isEmpty) return DeepfakeResult.notReady();

    bool isFake;
    if (probs.length == 3 && probs[1] < 0.05) {
      // W2 가 5% 미만 → 중간 윈도우가 매우 강하게 진짜 → 가짜 판정 보류
      debugPrint('[Deepfake] W2=${(probs[1] * 100).toStringAsFixed(1)}% < 5% → '
          '중간 윈도우 진짜 음성 신호 → 가짜 판정 보류');
      isFake = false;
    } else {
      final overThreshold = probs.where((p) => p > 0.5).length;  // 0.4 → 0.5
      final hasHighConf   = probs.any((p) => p > 0.85);          // 0.8 → 0.85
      isFake = overThreshold >= 2 || hasHighConf;
    }

    final maxProb = probs.reduce(math.max);
    final avgProb = probs.reduce((a, b) => a + b) / probs.length;
    return DeepfakeResult(
      fakeProb:   isFake ? maxProb : avgProb.clamp(0.0, 0.39),
      isAnalyzed: true,
    );
  }

  // ── TFLite 추론 (WAV 분석용, 패딩 허용) ────────────────────
  DeepfakeResult _runInference(Float32List samples) {
    final trimmed = samples.length > _inputSamples
        ? Float32List.fromList(samples.sublist(0, _inputSamples))
        : samples;
    final filtered = _phoneChannel(trimmed);

    final input = Float32List(_inputSamples);
    input.setRange(0, math.min(filtered.length, _inputSamples), filtered);

    final output = [[0.0, 0.0]]; // shape [1, 2]
    _interpreter!.run(input.buffer.asUint8List(), output);

    final genuine = output[0][0];
    final spoof   = output[0][1];
    debugPrint('[Deepfake] 추론 raw: genuine=$genuine spoof=$spoof');

    // Softmax
    final maxV   = math.max(genuine, spoof);
    final expG   = math.exp(genuine - maxV);
    final expS   = math.exp(spoof - maxV);
    final fakeProb = expS / (expG + expS);

    debugPrint('[Deepfake] fakeProb=${(fakeProb * 100).toStringAsFixed(1)}%');
    return DeepfakeResult(fakeProb: fakeProb, isAnalyzed: true);
  }
}

// ── 결과 모델 ──────────────────────────────────────────────
class DeepfakeResult {
  final double fakeProb;  // 0.0 ~ 1.0
  final bool   isAnalyzed;

  const DeepfakeResult({required this.fakeProb, required this.isAnalyzed});

  factory DeepfakeResult.notReady() =>
      const DeepfakeResult(fakeProb: 0.0, isAnalyzed: false);

  bool   get isFake       => isAnalyzed && fakeProb >= 0.5;
  int    get fakePercent  => (fakeProb * 100).toInt();

  /// 0: 분석 전/불가, 1: 일반 음성, 2: 가능성, 3: 의심
  int get level {
    if (!isAnalyzed) return 0;
    if (fakeProb >= 0.7) return 3;
    if (fakeProb >= 0.5) return 2;
    return 1;
  }

  static const _labels = ['분석 중', '일반 음성', '변조목소리 가능성', '변조 목소리 의심'];
  String get label => _labels[level];
}
