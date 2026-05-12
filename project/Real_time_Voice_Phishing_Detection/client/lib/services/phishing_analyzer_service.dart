import 'dart:math' as math;
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:tflite_flutter/tflite_flutter.dart';

/// KoELECTRA 기반 보이스피싱 탐지 서비스
/// 1단계: 슬라이딩 윈도우 키워드 필터 (<10ms)
/// 2단계: TFLite 추론 (~80ms), 1단계 통과(15점 이상)시에만 실행
class PhishingAnalyzerService {
  PhishingAnalyzerService._();
  static final instance = PhishingAnalyzerService._();

  static const _maxLength = 128;
  static const _filterThreshold = 15;

  // 특수 토큰 ID
  static const _clsId = 2;
  static const _sepId = 3;
  static const _padId = 0;
  static const _unkId = 1;

  Interpreter? _interpreter;
  Map<String, int>? _vocab;
  String _modelVersion = '없음';

  // --dart-define으로 빌드 시 주입. 기본값: dynamic range quant
  static const _modelFile = String.fromEnvironment(
    'MODEL_FILE',
    defaultValue: 'model_int8_v6.tflite',
  );
  static const _modelLabel = String.fromEnvironment(
    'MODEL_LABEL',
    defaultValue: 'int8-v6',
  );

  bool get isReady => _interpreter != null && _vocab != null;
  String get modelVersion => _modelVersion;

  /// 키워드 필터만 실행 (모델 추론 없음, <10ms) — partial STT용
  int quickScan(String text) => _keywordFilter(text);

  // ── 초기화 ──────────────────────────────────────────────────
  Future<void> initialize() async {
    debugPrint('[Analyzer] initialize() 시작');
    await Future.wait([_loadVocab(), _loadModel()]);
    debugPrint('[Analyzer] initialize() 완료');
  }

  Future<void> _loadVocab() async {
    final raw = await rootBundle.loadString('assets/vocab.txt');
    final lines = raw.split('\n');
    _vocab = {};
    for (var i = 0; i < lines.length; i++) {
      final word = lines[i].trim();
      if (word.isNotEmpty) _vocab![word] = i;
    }
    debugPrint('[Analyzer] vocab 로드 완료: ${_vocab!.length}개');
  }

  static InterpreterOptions get _cpuOptions =>
      InterpreterOptions()..threads = 2;

  Future<void> _loadModel() async {
    try {
      _interpreter = await Interpreter.fromAsset(
        'assets/$_modelFile',
        options: _cpuOptions,
      );
      _interpreter!.allocateTensors();
      _modelVersion = _modelLabel;
      debugPrint('[Analyzer] 모델 로드 성공 ($_modelLabel)');
      // 텐서 정보 출력 (타입/형태 확인용)
      for (var i = 0; i < _interpreter!.getInputTensors().length; i++) {
        final t = _interpreter!.getInputTensors()[i];
        debugPrint('[Analyzer] 입력텐서[$i]: ${t.name} shape=${t.shape} type=${t.type}');
      }
      for (var i = 0; i < _interpreter!.getOutputTensors().length; i++) {
        final t = _interpreter!.getOutputTensors()[i];
        debugPrint('[Analyzer] 출력텐서[$i]: ${t.name} shape=${t.shape} type=${t.type}');
      }
    } catch (e) {
      _modelVersion = '없음 (키워드 필터만)';
      debugPrint('[Analyzer] 모델 로드 실패 ($_modelLabel): $e');
    }
  }

  void dispose() {
    _interpreter?.close();
    _interpreter = null;
    _vocab = null;
  }

  // ── 분석 진입점 ────────────────────────────────────────────
  /// [text]: 누적된 전체 통화 텍스트
  PhishingResult analyze(String text) {
    if (text.trim().isEmpty) return PhishingResult.safe();

    final keywordScore = _keywordFilter(text);
    debugPrint('[Analyzer] keywordScore=$keywordScore, isReady=$isReady');

    if (keywordScore < _filterThreshold) {
      debugPrint('[Analyzer] 필터 미통과 → safe');
      return PhishingResult.safe(keywordScore: keywordScore);
    }

    if (!isReady) {
      debugPrint('[Analyzer] 필터 통과($keywordScore) but 모델 미준비 → triggered=false');
      return PhishingResult(
        keywordScore: keywordScore,
        probs: [0, 0, 0],
        triggered: false,
      );
    }

    final wordCount = text.trim().split(RegExp(r'\s+')).length;

    try {
      final probs = _runInference(text);
      debugPrint('[Analyzer] 추론 완료 → probs=${probs.map((p) => p.toStringAsFixed(2)).toList()} wordCount=$wordCount');
      return PhishingResult(
        keywordScore: keywordScore,
        probs: probs,
        triggered: true,
        wordCount: wordCount,
      );
    } catch (e, st) {
      debugPrint('[Analyzer] 추론 오류: $e');
      debugPrint('[Analyzer] 스택트레이스: $st');
      return PhishingResult(keywordScore: keywordScore, probs: [0, 0, 0], triggered: false, wordCount: wordCount);
    }
  }

  // ── 1단계: 키워드 필터 (NLU/pipeline/filter.py 동기화) ──────
  // 고위험: 피싱에서만 사용되거나 단독으로도 강한 신호 (15점)
  static const _keywords = <String, int>{
    // 기관사칭
    '검찰': 15, '검사': 15, '검사님': 15, '수사관': 15, '수사과': 15,
    '수사팀': 15, '사무관': 15, '조사관': 15, '지검': 15, '경찰청': 15,
    '사이버수사대': 15, '중앙수사부': 15, '세무서': 15, '서울중앙지검': 15, '공단': 15,
    '금융감독원': 15, '금감원': 15, '공문': 15, '사건조회': 15,
    '나의사건': 15, '소환': 15, '피의자': 15, '사건번호': 15,
    '녹취': 15, '제3자': 15,
    '법무부': 15, '국가정보원': 15, '감사원': 15, '보건복지부': 15, '소비자청': 15, '금융정보분석원': 15,

    // 금전요구
    '계좌이체': 15, '안전계좌': 15, '국가안전계좌': 15, '공탁금': 15,
    '환급': 15, '대포통장': 15, '통장매입': 15,
    '환치기': 15, '합의금': 15, '동결': 15, '양도': 15,
    '수거': 15, '봉투': 15, '대환': 15, 'FIU': 15,

    // 개인정보
    '주민번호': 15, '주민등록번호': 15, 'OTP': 15, '카드번호': 15,
    '비밀번호': 15, '계좌번호': 15, '공인인증서': 15, '보안카드': 15,
    '신분증': 15, '앞면촬영': 15, '인증번호': 15, '개인정보유출': 15,
    '실명인증': 15, '실명확인': 15, '본인확인': 15,
    'CVC': 15, '유효기간': 15, '카드뒷면': 15, '명의': 15,

    // 기술적 위협
    '팀뷰어': 15, '원격제어': 15, '악성코드': 15, '해킹': 15,
    '앱설치': 15, '보안업데이트': 15, '삭제후재설치': 15,
    '출처불명링크': 15, 'URL클릭': 15, '파밍': 15,
    '주소창': 15, '인터넷주소': 15, '공식홈페이지': 15,

    // 심리적 압박
    '구속영장': 15, '범죄연루': 15, '비밀수사': 15,
    '통화내용녹음': 15, '재판출두': 15, '소환장': 15,

    // 고립 및 기망
    '외부연락차단': 15, '안전한장소': 15, '영상통화거부': 15,
    '지정질문': 15, '가족목소리': 15,
  };

  // 저위험: 정상 대화에서도 등장하는 단어, 복수 조합 시 신호 (7점)
  static const _weakKeywords = <String, int>{
    // 기관사칭
    '형사': 7, '경찰': 7, '법원': 7, '국세청': 7, '수사': 7, '조사': 7, '한국은행': 7,

    // 금전요구
    '송금': 7, '이체': 7, '입금': 7, '현금': 7, '출금': 7, '인출': 7,
    '통장': 7, '계좌': 7, '자산': 7, '예금': 7, '대출': 7,
    '카카오페이': 7, '카카오뱅크': 7, '상환': 7, '가족사고': 7,
    '신용점수': 7, '임대': 7, '채무': 7, '연체': 7,

    // 개인정보
    '신용카드': 7, '유출': 7, '앞면': 7, '비번': 7, '패스워드': 7, '여권번호': 7, '생년월일': 7,

    // 기술적 위협
    '삭제': 7, '설치': 7, '링크': 7, '이상징후': 7,

    // 심리적 압박
    '연루': 7, '불법거래': 7, '금융사기': 7, '이상거래': 7,
    '보안조치': 7, '계좌보호': 7, '거래정지': 7,
    '2차피해': 7, '긴급상황': 7, '신용불량': 7,

    // 고립 및 기망
    '모텔': 7, '투숙': 7, '고립': 7,

    // 기관 관련
    '금융권': 7, '공공기관': 7,
  };

  int _keywordFilter(String text) {
    // STT가 복합어에 공백을 삽입하는 경우 대비 (예: "안전 계좌" → "안전계좌")
    final normalized = text.replaceAll(RegExp(r'\s+'), '');
    var score = 0;
    _keywords.forEach((kw, pts) {
      if (text.contains(kw) || normalized.contains(kw)) score += pts;
    });
    _weakKeywords.forEach((kw, pts) {
      if (text.contains(kw) || normalized.contains(kw)) score += pts;
    });
    // URL 패턴 감지 (30점)
    if (text.contains('www')) score += 30;
    if (RegExp(r'[a-zA-Z]+\d+[a-zA-Z]*\.[a-zA-Z]{2,}').hasMatch(text)) score += 30;
    return score;
  }

  // ── 2단계: WordPiece 토크나이저 ───────────────────────────
  List<int> _tokenize(String text) {
    final vocab = _vocab!;
    final tokens = <int>[];

    for (final word in text.split(RegExp(r'\s+'))) {
      if (word.isEmpty) continue;
      tokens.addAll(_wordPiece(word, vocab));
      if (tokens.length >= _maxLength - 2) break;
    }

    final truncated = tokens.take(_maxLength - 2).toList();
    final inputIds = [_clsId, ...truncated, _sepId];
    while (inputIds.length < _maxLength) { inputIds.add(_padId); }

    return inputIds;
  }

  List<int> _wordPiece(String word, Map<String, int> vocab) {
    if (vocab.containsKey(word)) return [vocab[word]!];

    final subTokens = <int>[];
    var start = 0;
    while (start < word.length) {
      var end = word.length;
      int? curId;
      while (start < end) {
        final substr = (start == 0 ? '' : '##') + word.substring(start, end);
        if (vocab.containsKey(substr)) {
          curId = vocab[substr];
          break;
        }
        end--;
      }
      if (curId == null) return [_unkId];
      subTokens.add(curId);
      start = end;
    }
    return subTokens;
  }

  // ── 3단계: TFLite 추론 ────────────────────────────────────
  List<double> _runInference(String text) {
    final inputIds = _tokenize(text);
    final attentionMask = inputIds.map((id) => id != _padId ? 1 : 0).toList();
    final tokenTypeIds = List.filled(_maxLength, 0);

    // v6 모델: int32 텐서 (128×4=512B)
    // v5 모델: int64 텐서 (128×8=1024B) — Int64List 사용했었음
    final output = [List.filled(3, 0.0)];

    // 텐서 순서: [0]=attention_mask, [1]=input_ids, [2]=token_type_ids
    _interpreter!.runForMultipleInputs(
      [
        Int32List.fromList(attentionMask).buffer.asUint8List(),
        Int32List.fromList(inputIds).buffer.asUint8List(),
        Int32List.fromList(tokenTypeIds).buffer.asUint8List(),
      ],
      {0: output},
    );

    // Sigmoid
    return output[0].map((logit) => 1.0 / (1.0 + math.exp(-logit))).toList();
  }
}

// ── 결과 모델 ──────────────────────────────────────────────
class PhishingResult {
  final int keywordScore;
  final List<double> probs; // [기관사칭, 금전요구, 개인정보]
  final bool triggered;
  final int wordCount;

  static const _labels = ['기관사칭', '금전요구', '개인정보'];
  static const _probThreshold = 0.5;
  // 누적 단어 수가 이 값 미만이면 warningLevel 최대 2 (주황)로 제한
  static const _minWordsForHighAlert = 30;

  PhishingResult({
    required this.keywordScore,
    required this.probs,
    required this.triggered,
    this.wordCount = 0,
  });

  factory PhishingResult.safe({int keywordScore = 0}) =>
      PhishingResult(keywordScore: keywordScore, probs: [0, 0, 0], triggered: false);

  List<String> get detectedLabels => [
    for (var i = 0; i < probs.length; i++)
      if (probs[i] >= _probThreshold) _labels[i],
  ];

  double get maxProb {
    if (probs.isEmpty) return 0;
    final active = probs.where((p) => p >= _probThreshold).toList();
    final base = probs.reduce((a, b) => a > b ? a : b);
    if (active.length <= 1) return base;
    // 복합 탐지 보정: 0.5 이상 라벨 추가 1개당 +5% (최대 1.0)
    return (base + (active.length - 1) * 0.05).clamp(0.0, 1.0);
  }

  int get riskPercent {
    if (!triggered) return (keywordScore / 3).clamp(0, 30).toInt();
    final modelRisk = (maxProb * 100).toInt();
    final keywordFloor = (keywordScore / 3).clamp(0, 30).toInt();
    return math.max(modelRisk, keywordFloor);
  }

  int get warningLevel {
    final r = riskPercent;
    // 누적 텍스트가 짧으면 한 문장만으로 확신 불가 → 최대 2 (경고)
    final maxLevel = wordCount < _minWordsForHighAlert ? 2 : 3;
    if (r >= 61) return maxLevel;
    if (r >= 31) return 2;
    if (r >= 11) return 1;
    return 0;
  }
}
