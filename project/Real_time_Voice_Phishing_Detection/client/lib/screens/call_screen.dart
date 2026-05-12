import 'dart:async';
import 'package:flutter/material.dart';
import 'package:just_audio/just_audio.dart';
import 'package:speech_to_text/speech_to_text.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import '../services/phishing_analyzer_service.dart';
import '../services/deepfake_detector_service.dart';
import '../models/analysis_result.dart';

enum _Phase { preparing, active, ended }

// ── 라이트 테마 색상 상수 ─────────────────────────────────────
const _bg          = Color(0xFFF8FAFC);
const _cardBg      = Colors.white;
const _textPrimary = Color(0xFF1E293B);
const _textSecond  = Color(0xFF64748B);
const _textHint    = Color(0xFF94A3B8);
const _border      = Color(0xFFE2E8F0);

class CallScreen extends StatefulWidget {
  final String audioAsset;
  final String callerName;
  final String callerNumber;

  const CallScreen({
    super.key,
    this.audioAsset = '',
    this.callerName = '알 수 없음',
    this.callerNumber = '010-0000-0000',
  });

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> with TickerProviderStateMixin {
  _Phase _phase = _Phase.preparing;

  final _player = AudioPlayer();
  final _speech = SpeechToText();
  final _analyzer = PhishingAnalyzerService.instance;
  final _deepfake = DeepfakeDetectorService.instance;

  String _fullText = '';
  String _partialText = '';
  int _warningLevel = 0;
  int _riskPercent = 0;
  int _peakRiskPercent = 0;
  int _lockedRisk = 0;
  final List<String> _detectedLabels = [];
  final Map<String, int> _labelCounts = {'기관사칭': 0, '금전요구': 0, '개인정보': 0};
  bool _hangupWarningShown = false;
  bool _showDangerOverlay = false;
  bool _showDeepfakeOverlay = false;
  String? _errorMsg;
  bool _callActive = false;

  DeepfakeResult _deepfakeResult = DeepfakeResult.notReady();
  bool _deepfakeAnalyzing = false;
  bool _deepfakeChecking  = false;
  bool _deepfakeAlertShown = false;

  Duration _elapsed = Duration.zero;
  Timer? _callTimer;
  DateTime? _callStartTime;

  StreamSubscription<PlaybackEvent>? _playbackSub;

  bool _sttRestarting = false;
  Timer? _sttWatchdog;
  DateTime _sttBusyUntil = DateTime(0);

  late AnimationController _pulseCtrl;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 800))
      ..repeat(reverse: true);
    _initAll().then((_) {
      if (mounted) _answerCall();
    });
  }

  @override
  void dispose() {
    _callActive = false;
    _callTimer?.cancel();
    _sttWatchdog?.cancel();
    _speech.cancel();
    _playbackSub?.cancel();
    _player.dispose();
    _pulseCtrl.dispose();
    _deepfake.dispose();
    super.dispose();
  }

  Future<void> _initAll() async {
    final available = await _speech.initialize(
      onError: (e) {
        debugPrint('[STT] 오류: ${e.errorMsg}');
        if (e.errorMsg == 'error_busy') {
          _sttBusyUntil = DateTime.now().add(const Duration(seconds: 3));
          debugPrint('[STT] error_busy → 3초 백오프 설정');
        }
        if (mounted) setState(() {});
      },
      onStatus: _onSpeechStatus,
    );
    if (!available && mounted) {
      setState(() => _errorMsg = '마이크 권한이 필요합니다');
    }

    if (!_analyzer.isReady) {
      _analyzer.initialize().then((_) {
        if (mounted) setState(() {});
      }).catchError((e) {
        debugPrint('[Analyzer] 초기화 오류: $e');
        if (mounted) setState(() {});
      });
    }

    if (!_deepfake.isReady) {
      _deepfake.initialize().then((_) {
        if (mounted) setState(() {});
      }).catchError((e) {
        debugPrint('[Deepfake] 초기화 오류: $e');
      });
    }

    if (mounted) setState(() {});
  }

  Future<void> _answerCall() async {
    setState(() {
      _phase = _Phase.active;
      _callActive = true;
      _callStartTime = DateTime.now();
    });
    _callTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() => _elapsed += const Duration(seconds: 1));
    });
    if (widget.audioAsset.isNotEmpty) unawaited(_startPlayback());
    unawaited(_startListening());

    // STT가 예기치 않게 멈춰도 2초 내 자동 재시작
    _sttWatchdog = Timer.periodic(const Duration(seconds: 2), (_) {
      if (_callActive && mounted && !_speech.isListening && !_sttRestarting) {
        debugPrint('[STT] Watchdog: 재시작');
        unawaited(_startListening());
      }
    });
  }

  Future<void> _startPlayback() async {
    try {
      await _player.setAsset('assets/audio/${widget.audioAsset}');
      _playbackSub = _player.playbackEventStream.listen(
        (_) {},
        onError: (Object e, StackTrace _) {
          debugPrint('[Playback] 음성파일 오류: $e');
        },
      );
      await _player.play();
    } catch (e) {
      debugPrint('[Playback] 음성파일 없음: $e');
    }
  }

  Future<void> _runDeepfakeCheck({required bool isManual}) async {
    if (!mounted || _deepfakeChecking) return;

    for (var i = 0; i < 30 && !_deepfake.isReady && mounted; i++) {
      await Future.delayed(const Duration(milliseconds: 500));
    }
    if (!mounted || !_deepfake.isReady) return;

    setState(() {
      _deepfakeChecking = true;
      _deepfakeAnalyzing = true;
    });

    DeepfakeResult result;

    if (widget.audioAsset.isNotEmpty) {
      debugPrint('[Deepfake] WAV 분석');
      result = await _deepfake.analyzeAsset('assets/audio/${widget.audioAsset}');
    } else {
      if (isManual) {
        debugPrint('[Deepfake] STT 중지 → 단발 캡처');
        await _speech.stop();
        await Future.delayed(const Duration(milliseconds: 300));
      } else {
        debugPrint('[Deepfake] 자동 체크: STT 미시작 상태에서 단발 캡처');
      }
      result = await _deepfake.captureAndAnalyze();
      if (isManual && mounted && _callActive) {
        unawaited(_startListening());
      }
    }

    if (mounted) {
      setState(() {
        _deepfakeResult = result;
        _deepfakeChecking = false;
        _deepfakeAnalyzing = false;
      });
      _checkDeepfakeWarning(result);
    }
  }

  void _checkDeepfakeWarning(DeepfakeResult result) {
    if (_deepfakeAlertShown || result.level < 3 || !mounted) return;
    _deepfakeAlertShown = true;
    setState(() => _showDeepfakeOverlay = true);
  }

  Future<void> _startListening() async {
    if (!_speech.isAvailable || !mounted || !_callActive) return;
    if (_speech.isListening || _sttRestarting) return;
    if (_deepfakeChecking) return;                                    // deepfake 캡처 중 재시작 방지
    if (DateTime.now().isBefore(_sttBusyUntil)) return;              // error_busy 백오프
    _sttRestarting = true;
    try {
      await _speech.listen(
        onResult: _onSpeechResult,
        localeId: 'ko_KR',
        listenFor: const Duration(seconds: 30),
        pauseFor: const Duration(seconds: 4),
        listenOptions: SpeechListenOptions(
          partialResults: true,
          listenMode: ListenMode.dictation,
          cancelOnError: false,
        ),
      );
      if (mounted) setState(() {});
    } catch (e) {
      debugPrint('[STT] listen 오류: $e');
    } finally {
      _sttRestarting = false;
    }
  }

  void _onSpeechResult(SpeechRecognitionResult result) {
    if (!mounted) return;
    setState(() => _partialText = result.recognizedWords);

    if (!result.finalResult && result.recognizedWords.isNotEmpty) {
      final combined = _fullText.isEmpty
          ? result.recognizedWords
          : '$_fullText ${result.recognizedWords}';
      final words = combined.split(RegExp(r'\s+'));
      final window = words.length > 100
          ? words.sublist(words.length - 100).join(' ')
          : combined;
      // raw 점수 100% 초과 방지: /3 정규화 + 30 상한
      final provisional = (_analyzer.quickScan(window) / 3).clamp(0, 30).toInt();
      // 경고창 이후에만 _lockedRisk 하한 적용
      final effective = (_hangupWarningShown && _lockedRisk > provisional)
          ? _lockedRisk
          : provisional;
      if (effective > _riskPercent) {
        setState(() {
          _riskPercent = effective;
          _warningLevel = effective >= 61 ? 3 : effective >= 31 ? 2 : effective >= 11 ? 1 : 0;
        });
      }
    }

    if (result.finalResult) {
      if (result.recognizedWords.isNotEmpty) {
        setState(() {
          _fullText += (_fullText.isEmpty ? '' : ' ') + result.recognizedWords;
          _partialText = '';
        });
        _updateWarningLevel(_fullText);
      }
      if (_callActive && mounted) {
        Future.delayed(const Duration(milliseconds: 50), () {
          if (_callActive && mounted && !_speech.isListening && !_sttRestarting) {
            unawaited(_startListening());
          }
        });
      }
    }
  }

  void _onSpeechStatus(String status) {
    debugPrint('[STT] 상태: $status');
    if (mounted) setState(() {});
    // done은 _onSpeechResult finalResult 이후 재시작 (순서 보장)
    // 결과 없이 끝난 경우만 여기서 처리
    if ((status == 'notListening' || status == 'doneNoResult') &&
        _callActive && mounted) {
      Future.delayed(const Duration(milliseconds: 50), () {
        if (_callActive && mounted && !_speech.isListening && !_sttRestarting) {
          unawaited(_startListening());
        }
      });
    }
  }

  Future<void> _endCall() async {
    _callActive = false;
    _callTimer?.cancel();
    _sttWatchdog?.cancel();
    await _speech.stop();
    await _player.stop();
    if (_partialText.isNotEmpty) {
      _fullText += (_fullText.isEmpty ? '' : ' ') + _partialText;
      _partialText = '';
    }
    setState(() {
      _phase = _Phase.ended;
      _showDangerOverlay = false;
      _showDeepfakeOverlay = false;
    });
    if (_fullText.isNotEmpty) _updateWarningLevel(_fullText);
  }

  void _popWithResult() {
    Navigator.of(context).pop(AnalysisResult(
      text: _fullText.isEmpty ? '(인식된 텍스트 없음)' : _fullText,
      riskScore: _peakRiskPercent,
      warningLevel: _peakRiskPercent >= 61
          ? 3
          : _peakRiskPercent >= 31
              ? 2
              : _peakRiskPercent >= 11
                  ? 1
                  : 0,
      explanation: '',
      detectedLabels: _detectedLabels,
    ));
  }

  static const _hangupThreshold = 70;

  void _updateWarningLevel(String text) {
    final words = text.split(RegExp(r'\s+'));
    final window = words.length > 100
        ? words.sublist(words.length - 100).join(' ')
        : text;

    debugPrint('[UI] 분석 텍스트(${words.length}단어): "$window"');
    final result = _analyzer.analyze(window);
    debugPrint('[UI] keyword=${result.keywordScore} risk=${result.riskPercent}% triggered=${result.triggered} labels=${result.detectedLabels}');

    // 경고창 이후에만 _lockedRisk 하한 적용, 그 전까지는 자유롭게 오르내림
    final effectiveRisk = ((_hangupWarningShown && result.riskPercent < _lockedRisk)
        ? _lockedRisk
        : result.riskPercent).clamp(0, 100);

    setState(() {
      _riskPercent = effectiveRisk;
      _warningLevel = effectiveRisk >= 61 ? 3 : effectiveRisk >= 31 ? 2 : effectiveRisk >= 11 ? 1 : 0;
      if (effectiveRisk > _peakRiskPercent) _peakRiskPercent = effectiveRisk;
      for (final l in result.detectedLabels) {
        _labelCounts[l] = (_labelCounts[l] ?? 0) + 1;
        if (!_detectedLabels.contains(l)) _detectedLabels.add(l);
      }
    });

    if (effectiveRisk >= _hangupThreshold &&
        !_hangupWarningShown &&
        _phase == _Phase.active) {
      _hangupWarningShown = true;
      _lockedRisk = effectiveRisk;  // 팝업 뜨는 순간의 실제 값을 하한으로 고정
      _showHangupWarning();
    }
  }

  void _showHangupWarning() {
    if (!mounted) return;
    setState(() => _showDangerOverlay = true);
  }

  // ── Build ─────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: Stack(
          children: [
            switch (_phase) {
              _Phase.preparing => _buildPreparing(),
              _Phase.active    => _buildActive(),
              _Phase.ended     => _buildEnded(),
            },
            if (_showDangerOverlay) _buildDangerOverlay(),
            if (_showDeepfakeOverlay) _buildDeepfakeOverlay(),
          ],
        ),
      ),
    );
  }

  // ── 위험 오버레이 (빨간 반투명 배경 + 중앙 흰 카드) ──────────
  Widget _buildDangerOverlay() {
    return Positioned.fill(
      child: Container(
        color: const Color(0xFFEF4444).withValues(alpha: 0.55),
        child: Center(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 32),
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFEF4444).withValues(alpha: 0.3),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444).withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.warning_amber_rounded,
                      color: Color(0xFFEF4444), size: 32),
                ),
                const SizedBox(height: 16),
                const Text('보이스피싱 의심!',
                    style: TextStyle(
                        color: Color(0xFFEF4444),
                        fontSize: 22,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 10),
                const Text(
                  '위험도가 높습니다.\n지금 바로 전화를 끊으세요.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      color: _textSecond, fontSize: 14, height: 1.6),
                ),
                const SizedBox(height: 24),
                Row(children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        setState(() => _showDangerOverlay = false);
                        if (_callActive && !_speech.isListening) {
                          unawaited(_startListening());
                        }
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _textSecond,
                        side: const BorderSide(color: _border),
                        padding: const EdgeInsets.symmetric(vertical: 13),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('계속 분석',
                          style: TextStyle(fontSize: 14)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        setState(() => _showDangerOverlay = false);
                        _endCall();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFEF4444),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 13),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                      child: const Text('분석 종료',
                          style: TextStyle(
                              fontSize: 14, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── 변조 목소리 오버레이 (빨간 반투명 배경 + 중앙 흰 카드) ──────
  Widget _buildDeepfakeOverlay() {
    return Positioned.fill(
      child: Container(
        color: const Color(0xFFEF4444).withValues(alpha: 0.55),
        child: Center(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 32),
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFEF4444).withValues(alpha: 0.3),
                  blurRadius: 24,
                  offset: const Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: const Color(0xFFEF4444).withValues(alpha: 0.1),
                    shape: BoxShape.circle,
                  ),
                  child: const Icon(Icons.mic_off_rounded,
                      color: Color(0xFFEF4444), size: 32),
                ),
                const SizedBox(height: 16),
                const Text('변조 목소리 의심',
                    style: TextStyle(
                        color: Color(0xFFEF4444),
                        fontSize: 22,
                        fontWeight: FontWeight.bold)),
                const SizedBox(height: 10),
                Text(
                  '상대방 음성이 AI 합성 음성일 가능성이 높습니다.\n'
                  '변조 목소리 확률: ${_deepfakeResult.fakePercent}%\n\n'
                  '주의하세요.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                      color: _textSecond, fontSize: 14, height: 1.6),
                ),
                const SizedBox(height: 24),
                Row(children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () {
                        setState(() {
                          _showDeepfakeOverlay = false;
                          _deepfakeAlertShown = false;
                        });
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _textSecond,
                        side: const BorderSide(color: _border),
                        padding: const EdgeInsets.symmetric(vertical: 13),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('계속 받기',
                          style: TextStyle(fontSize: 14)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        setState(() => _showDeepfakeOverlay = false);
                        _endCall();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFEF4444),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 13),
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                        elevation: 0,
                      ),
                      child: const Text('전화 끊기',
                          style: TextStyle(
                              fontSize: 14, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── 준비 중 화면 ───────────────────────────────────────────
  Widget _buildPreparing() {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(color: Color(0xFF3B82F6)),
          const SizedBox(height: 24),
          const Text('준비 중...',
              style: TextStyle(
                  color: _textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const Text('잠시만 기다려 주세요',
              style: TextStyle(color: _textSecond, fontSize: 13)),
        ],
      ),
    );
  }

  // ── 색상 / 라벨 / 메시지 상수 ─────────────────────────────
  static const _riskColors = [
    Color(0xFF22C55E),
    Color(0xFFF59E0B),
    Color(0xFFEA580C),
    Color(0xFFEF4444),
  ];
  static const _riskLabels = ['안전', '주의', '경고', '위험'];
  static const _statusMessages = [
    '위협 요소가 감지되지 않았습니다',
    '의심스러운 패턴이 감지되었습니다',
    '보이스피싱 패턴 다수 감지 중',
    '즉시 전화를 끊으세요!',
  ];

  // ── 원형 위험도 인디케이터 ─────────────────────────────────
  Widget _buildCircularRisk() {
    final color = _riskColors[_warningLevel];
    final label = _riskLabels[_warningLevel];
    return SizedBox(
      width: 180,
      height: 180,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Container(
            width: 180,
            height: 180,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: color.withValues(alpha: 0.08),
            ),
          ),
          TweenAnimationBuilder<double>(
            tween: Tween(end: _riskPercent / 100),
            duration: const Duration(milliseconds: 600),
            builder: (_, value, _) => SizedBox(
              width: 180,
              height: 180,
              child: CircularProgressIndicator(
                value: value,
                strokeWidth: 10,
                backgroundColor: _border,
                valueColor: AlwaysStoppedAnimation(color),
                strokeCap: StrokeCap.round,
              ),
            ),
          ),
          Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('$_riskPercent%',
                  style: TextStyle(
                      color: color,
                      fontSize: 38,
                      fontWeight: FontWeight.bold,
                      height: 1.0)),
              const SizedBox(height: 4),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Text(label,
                    style: TextStyle(
                        color: color,
                        fontSize: 13,
                        fontWeight: FontWeight.bold)),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // ── 카테고리 감지 횟수 카드 ────────────────────────────────
  Widget _buildCategoryCount(String label) {
    final count = _labelCounts[label] ?? 0;
    final isDetected = count > 0;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 10),
      decoration: BoxDecoration(
        color: isDetected
            ? const Color(0xFFEF4444).withValues(alpha: 0.06)
            : _cardBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDetected
              ? const Color(0xFFEF4444).withValues(alpha: 0.35)
              : _border,
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$count회',
              style: TextStyle(
                  color: isDetected
                      ? const Color(0xFFEF4444)
                      : _textHint,
                  fontSize: 18,
                  fontWeight: FontWeight.bold)),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(
                  color: isDetected ? _textSecond : _textHint,
                  fontSize: 11)),
        ],
      ),
    );
  }

  // ── 딥보이스 탐지 인디케이터 ──────────────────────────────────
  static const _deepfakeColors = [
    Color(0xFF94A3B8),
    Color(0xFF22C55E),
    Color(0xFFF59E0B),
    Color(0xFFEF4444),
  ];

  Widget _buildDeepfakeIndicator() {
    final isBusy = _deepfakeChecking || _deepfakeAnalyzing;
    final level  = isBusy ? 0 : _deepfakeResult.level;
    final color  = _deepfakeColors[level];
    final label  = isBusy ? '변조 목소리 체크 중…' : _deepfakeResult.label;
    final pct    = (!isBusy && _deepfakeResult.isAnalyzed)
        ? _deepfakeResult.fakePercent
        : null;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: _cardBg,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withValues(alpha: 0.5)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 4,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(children: [
          if (isBusy)
            SizedBox(
              width: 8, height: 8,
              child: CircularProgressIndicator(
                  strokeWidth: 2, color: color),
            )
          else
            Container(
              width: 8, height: 8,
              decoration: BoxDecoration(color: color, shape: BoxShape.circle),
            ),
          const SizedBox(width: 8),
          const Icon(Icons.record_voice_over_rounded,
              color: _textHint, size: 14),
          const SizedBox(width: 6),
          Text(label,
              style: TextStyle(
                  color: color, fontSize: 13, fontWeight: FontWeight.bold)),
          const Spacer(),
          if (pct != null) ...[
            Text('변조 목소리 $pct%',
                style: TextStyle(
                    color: color, fontSize: 13, fontWeight: FontWeight.bold)),
            const SizedBox(width: 8),
          ],
          GestureDetector(
            onTap: isBusy ? null : () => _runDeepfakeCheck(isManual: true),
            child: Container(
              padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(
                color: isBusy ? const Color(0xFFF1F5F9) : const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                    color: isBusy ? _border : const Color(0xFF6366F1).withValues(alpha: 0.4)),
              ),
              child: Text('변조 분석',
                  style: TextStyle(
                      color: isBusy ? _textHint : const Color(0xFF6366F1),
                      fontSize: 11,
                      fontWeight: FontWeight.w600)),
            ),
          ),
        ]),
      ),
    );
  }

  // ── 통화 중 화면 ───────────────────────────────────────────
  Widget _buildActive() {
    final mm = _elapsed.inMinutes.toString().padLeft(2, '0');
    final ss = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    final color = _riskColors[_warningLevel];

    return Column(
      children: [
        // 상단 바
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 0),
          child: Row(
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('분석 중...',
                      style: TextStyle(
                          color: _textPrimary,
                          fontSize: 16,
                          fontWeight: FontWeight.bold)),
                  Text(widget.callerNumber,
                      style: const TextStyle(
                          color: _textSecond, fontSize: 12)),
                ],
              ),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFFDCFCE7),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.circle,
                      color: Color(0xFF22C55E), size: 8),
                  const SizedBox(width: 6),
                  Text('$mm:$ss',
                      style: const TextStyle(
                          color: Color(0xFF16A34A),
                          fontSize: 13,
                          fontWeight: FontWeight.w600)),
                ]),
              ),
            ],
          ),
        ),
        const SizedBox(height: 20),

        // 원형 위험도
        _buildCircularRisk(),
        const SizedBox(height: 10),

        // 상태 메시지
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32),
          child: Text(
            _statusMessages[_warningLevel],
            textAlign: TextAlign.center,
            style: TextStyle(
                color: color, fontSize: 13, fontWeight: FontWeight.w600),
          ),
        ),
        const SizedBox(height: 10),

        // 딥보이스 인디케이터
        _buildDeepfakeIndicator(),
        const SizedBox(height: 8),

        // STT 텍스트 박스
        Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            child: Stack(
              children: [
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _cardBg,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: _border),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withValues(alpha: 0.04),
                        blurRadius: 4,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        const Icon(Icons.text_fields_rounded,
                            color: _textHint, size: 14),
                        const SizedBox(width: 6),
                        const Text('실시간 텍스트',
                            style: TextStyle(color: _textHint, fontSize: 12)),
                        const Spacer(),
                        if (!_analyzer.isReady) ...[
                          const SizedBox(
                            width: 10, height: 10,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: _textHint),
                          ),
                          const SizedBox(width: 4),
                          const Text('AI 로딩',
                              style: TextStyle(color: _textHint, fontSize: 10)),
                          const SizedBox(width: 8),
                        ],
                        if (_speech.isListening)
                          const SizedBox(
                            width: 12, height: 12,
                            child: CircularProgressIndicator(
                                strokeWidth: 2, color: _textHint),
                          ),
                      ]),
                      const SizedBox(height: 8),
                      Expanded(
                        child: SingleChildScrollView(
                          reverse: true,
                          child: RichText(
                            text: TextSpan(children: [
                              TextSpan(
                                text: _errorMsg ??
                                    (_fullText.isEmpty && _partialText.isEmpty
                                        ? (_speech.isListening
                                            ? '듣는 중...'
                                            : '대기 중')
                                        : _fullText),
                                style: TextStyle(
                                  color: _errorMsg != null
                                      ? const Color(0xFFEF4444)
                                      : _textPrimary,
                                  fontSize: 14,
                                  height: 1.7,
                                ),
                              ),
                              if (_partialText.isNotEmpty)
                                TextSpan(
                                  text: (_fullText.isEmpty ? '' : ' ') +
                                      _partialText,
                                  style: const TextStyle(
                                    color: _textHint,
                                    fontSize: 14,
                                    height: 1.7,
                                    fontStyle: FontStyle.italic,
                                  ),
                                ),
                            ]),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                // 변조 체크 중 STT 비활성 오버레이
                if (_deepfakeChecking)
                  Positioned.fill(
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(16),
                      child: ColoredBox(
                        color: Colors.grey.withValues(alpha: 0.82),
                        child: const Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.mic_off_rounded,
                                color: Colors.white70, size: 22),
                            SizedBox(height: 6),
                            Text(
                              '변조 목소리 체크 중\nSTT 일시 중지',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 13,
                                fontWeight: FontWeight.w500,
                                height: 1.5,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),

        // 카테고리 감지 횟수
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 6),
          child: Row(
            children: [
              Expanded(child: _buildCategoryCount('기관사칭')),
              const SizedBox(width: 8),
              Expanded(child: _buildCategoryCount('금전요구')),
              const SizedBox(width: 8),
              Expanded(child: _buildCategoryCount('개인정보')),
            ],
          ),
        ),

        // 분석 종료 버튼
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 6, 20, 24),
          child: SizedBox(
            width: double.infinity,
            height: 54,
            child: ElevatedButton(
              onPressed: _endCall,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFEF4444),
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
                elevation: 0,
              ),
              child: const Text('분석 종료',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            ),
          ),
        ),
      ],
    );
  }

  // ── 통화 종료 화면 ─────────────────────────────────────────
  int get _peakWarningLevel =>
      _peakRiskPercent >= 61 ? 3 : _peakRiskPercent >= 31 ? 2 : _peakRiskPercent >= 11 ? 1 : 0;

  String _formatStartTime() {
    final dt = _callStartTime ?? DateTime.now();
    final period = dt.hour < 12 ? '오전' : '오후';
    final h = dt.hour == 0 ? 12 : (dt.hour > 12 ? dt.hour - 12 : dt.hour);
    return '${dt.year}.${dt.month.toString().padLeft(2,'0')}.${dt.day.toString().padLeft(2,'0')} $period $h:${dt.minute.toString().padLeft(2,'0')}';
  }

  Widget _buildEnded() {
    final mm = _elapsed.inMinutes.toString().padLeft(2, '0');
    final ss = (_elapsed.inSeconds % 60).toString().padLeft(2, '0');
    final level = _peakWarningLevel;
    final color = _riskColors[level];
    final label = _riskLabels[level];

    return Column(
      children: [
        // 상단 바
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 8, 16, 0),
          child: Row(children: [
            IconButton(
              icon: const Icon(Icons.arrow_back, color: _textPrimary, size: 24),
              onPressed: _popWithResult,
            ),
            const Text('통화 분석 결과',
                style: TextStyle(
                    color: _textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w600)),
            const Spacer(),
            // 분석 시간 뱃지
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.timer_outlined, color: _textSecond, size: 14),
                const SizedBox(width: 4),
                Text('분석 시간  $mm:$ss',
                    style: const TextStyle(
                        color: _textSecond,
                        fontSize: 12,
                        fontWeight: FontWeight.w600)),
              ]),
            ),
          ]),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 분석 날짜
                Text(_formatStartTime(),
                    style: const TextStyle(color: _textHint, fontSize: 13)),
                const SizedBox(height: 12),
                // 위험도 카드
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: color.withValues(alpha: 0.06),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: color.withValues(alpha: 0.3)),
                  ),
                  child: Column(
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text('최고 위험도',
                                  style: TextStyle(
                                      color: _textHint, fontSize: 12)),
                              const SizedBox(height: 4),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.center,
                                children: [
                                  Text('$_peakRiskPercent%',
                                      style: TextStyle(
                                          color: color,
                                          fontSize: 32,
                                          fontWeight: FontWeight.bold,
                                          height: 1.0)),
                                  const SizedBox(width: 8),
                                  Container(
                                    padding: const EdgeInsets.symmetric(
                                        horizontal: 8, vertical: 3),
                                    decoration: BoxDecoration(
                                      color: color.withValues(alpha: 0.15),
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: Text(label,
                                        style: TextStyle(
                                            color: color,
                                            fontSize: 12,
                                            fontWeight: FontWeight.bold)),
                                  ),
                                ],
                              ),
                            ],
                          ),
                          const Spacer(),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              const Text('위험도 구간',
                                  style: TextStyle(
                                      color: _textHint, fontSize: 12)),
                              const SizedBox(height: 6),
                              Row(
                                children: List.generate(4, (i) => Padding(
                                  padding: EdgeInsets.only(left: i > 0 ? 4 : 0),
                                  child: Column(children: [
                                    Container(
                                      width: 30,
                                      height: 6,
                                      decoration: BoxDecoration(
                                        color: i <= level
                                            ? _riskColors[i]
                                            : const Color(0xFFE2E8F0),
                                        borderRadius: BorderRadius.circular(3),
                                      ),
                                    ),
                                    const SizedBox(height: 3),
                                    Text(
                                      ['안전', '주의', '경고', '위험'][i],
                                      style: TextStyle(
                                          fontSize: 9,
                                          color: i <= level
                                              ? _riskColors[i]
                                              : _textHint),
                                    ),
                                  ]),
                                )),
                              ),
                            ],
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: _peakRiskPercent / 100,
                          minHeight: 4,
                          backgroundColor: const Color(0xFFE2E8F0),
                          valueColor: AlwaysStoppedAnimation(color),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 20),

                // 카테고리별 감지
                const Text('카테고리별 감지',
                    style: TextStyle(
                        color: _textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600)),
                const SizedBox(height: 10),
                Row(children: [
                  Expanded(child: _buildCategoryCount('기관사칭')),
                  const SizedBox(width: 8),
                  Expanded(child: _buildCategoryCount('금전요구')),
                  const SizedBox(width: 8),
                  Expanded(child: _buildCategoryCount('개인정보')),
                ]),
                const SizedBox(height: 20),

                // 감지된 키워드
                const Text('감지된 키워드',
                    style: TextStyle(
                        color: _textPrimary,
                        fontSize: 14,
                        fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                _detectedLabels.isEmpty
                    ? const Text('감지된 키워드 없음',
                        style: TextStyle(
                            color: _textHint,
                            fontSize: 13,
                            fontStyle: FontStyle.italic))
                    : Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: _detectedLabels.map((l) => Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEF4444).withValues(alpha: 0.08),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                                color: const Color(0xFFEF4444).withValues(alpha: 0.3)),
                          ),
                          child: Text(l,
                              style: const TextStyle(
                                  color: Color(0xFFEF4444),
                                  fontSize: 12,
                                  fontWeight: FontWeight.w600)),
                        )).toList(),
                      ),
                const SizedBox(height: 20),

                // 변조 목소리 탐지 결과
                _buildEndedDeepfakeCard(),
                const SizedBox(height: 24),

                // 결과 저장하기 버튼
                SizedBox(
                  width: double.infinity,
                  height: 54,
                  child: ElevatedButton(
                    onPressed: _popWithResult,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFEF4444),
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14)),
                      elevation: 0,
                    ),
                    child: const Text('결과 저장하기',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.bold)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildEndedDeepfakeCard() {
    final isAnalyzed = _deepfakeResult.isAnalyzed;
    final dfColor = isAnalyzed
        ? _deepfakeColors[_deepfakeResult.level]
        : _textHint;
    final dfLabel = isAnalyzed ? _deepfakeResult.label : '미실시';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _cardBg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _border),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: dfColor.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(Icons.fingerprint_rounded, color: dfColor, size: 24),
        ),
        const SizedBox(width: 12),
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('변조 목소리 탐지',
                style: TextStyle(
                    color: _textPrimary,
                    fontSize: 14,
                    fontWeight: FontWeight.w600)),
            const SizedBox(height: 2),
            Text(
              isAnalyzed
                  ? '$dfLabel (${_deepfakeResult.fakePercent}%)'
                  : '수동 탐지 — $dfLabel',
              style: const TextStyle(color: _textSecond, fontSize: 12),
            ),
          ],
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: isAnalyzed
                ? dfColor.withValues(alpha: 0.1)
                : const Color(0xFFEEF2FF),
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: isAnalyzed
                  ? dfColor.withValues(alpha: 0.35)
                  : const Color(0xFF6366F1).withValues(alpha: 0.3),
            ),
          ),
          child: Text(
            isAnalyzed ? dfLabel : '탐지하기',
            style: TextStyle(
                color: isAnalyzed ? dfColor : const Color(0xFF6366F1),
                fontSize: 12,
                fontWeight: FontWeight.w600),
          ),
        ),
      ]),
    );
  }
}

