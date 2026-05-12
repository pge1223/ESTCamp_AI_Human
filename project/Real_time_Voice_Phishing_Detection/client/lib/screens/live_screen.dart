import 'package:flutter/material.dart';
import '../models/analysis_result.dart';
import 'call_screen.dart';

class LiveScreen extends StatefulWidget {
  final AnalysisResult? result;
  final bool isProtectionOn;
  final void Function(AnalysisResult)? onResult;

  const LiveScreen({
    super.key,
    required this.result,
    required this.isProtectionOn,
    this.onResult,
  });

  @override
  State<LiveScreen> createState() => _LiveScreenState();
}

class _LiveScreenState extends State<LiveScreen> {
  static const _levelColors = [
    Color(0xFF16A34A),
    Color(0xFFD97706),
    Color(0xFFEA580C),
    Color(0xFFDC2626),
  ];
  static const _levelBgColors = [
    Color(0xFFF0FDF4),
    Color(0xFFFFFBEB),
    Color(0xFFFFF7ED),
    Color(0xFFFFF1F2),
  ];
  static const _levelLabels = ['안전', '주의', '경고', '위험'];
  static const _levelIcons = [
    Icons.check_circle_rounded,
    Icons.warning_amber_rounded,
    Icons.warning_amber_rounded,
    Icons.dangerous_rounded,
  ];

  // 시뮬레이션용 샘플 파일 목록 (assets/audio/ 에 추가한 WAV 파일명)
  static const _sampleCalls = [
    (file: 'sample.wav', name: '보이스피싱 사례 1', number: '02-0000-0000'),
  ];

  Future<void> _openCallScreen(String file, String name, String number) async {
    final result = await Navigator.of(context).push<AnalysisResult>(
      MaterialPageRoute(
        fullscreenDialog: true,
        builder: (_) => CallScreen(
          audioAsset: file,
          callerName: name,
          callerNumber: number,
        ),
      ),
    );
    if (result != null) widget.onResult?.call(result);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('통화 분석', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF1E293B))),
          const SizedBox(height: 20),
          if (!widget.isProtectionOn)
            _buildOffCard()
          else if (widget.result == null)
            _buildWaitingCard()
          else
            _buildResultCard(widget.result!),
        ],
      ),
    );
  }

  Widget _buildOffCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: const Column(children: [
        Icon(Icons.shield_outlined, size: 48, color: Color(0xFF94A3B8)),
        SizedBox(height: 12),
        Text('보호가 꺼져 있습니다', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF64748B))),
        SizedBox(height: 6),
        Text('홈 화면에서 보호를 켜주세요', style: TextStyle(fontSize: 13, color: Color(0xFF94A3B8))),
      ]),
    );
  }

  Widget _buildWaitingCard() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(24),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.7),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: const Column(children: [
            Icon(Icons.phone_in_talk_rounded, size: 48, color: Color(0xFF3B82F6)),
            SizedBox(height: 12),
            Text('통화 대기 중',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF475569))),
            SizedBox(height: 6),
            Text('아래 시뮬레이션을 눌러 분석을 시작하세요',
                style: TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
          ]),
        ),
        const SizedBox(height: 16),
        const Text('마이크 직접 테스트',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF1E293B))),
        const SizedBox(height: 10),
        _SimCallCard(
          name: '실시간 마이크 입력',
          number: '직접 말하기',
          onTap: () => _openCallScreen('', '실시간 테스트', '마이크'),
        ),
        const SizedBox(height: 20),
        const Text('보이스피싱 시뮬레이션',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: Color(0xFF1E293B))),
        const SizedBox(height: 10),
        ..._sampleCalls.map((call) => Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: _SimCallCard(
            name: call.name,
            number: call.number,
            onTap: () => _openCallScreen(call.file, call.name, call.number),
          ),
        )),
      ],
    );
  }

  Widget _buildResultCard(AnalysisResult r) {
    final level = r.warningLevel.clamp(0, 3);
    final color = _levelColors[level];
    final bgColor = _levelBgColors[level];
    final label = _levelLabels[level];
    final icon = _levelIcons[level];

    return Column(children: [
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: 0.3)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(width: 8),
            Text(label, style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: color)),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(20)),
              child: Text('${r.riskScore}점', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color)),
            ),
          ]),
          if (r.isFakeVoice) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
              decoration: BoxDecoration(color: const Color(0xFFDC2626).withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12)),
              child: const Text('합성 음성 감지됨', style: TextStyle(fontSize: 12, color: Color(0xFFDC2626), fontWeight: FontWeight.bold)),
            ),
          ],
          if (r.detectedLabels.isNotEmpty) ...[
            const SizedBox(height: 12),
            Wrap(
              spacing: 6,
              children: r.detectedLabels.map((l) => Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12), border: Border.all(color: color.withValues(alpha: 0.3))),
                child: Text(l, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
              )).toList(),
            ),
          ],
        ]),
      ),
      const SizedBox(height: 12),
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.mic_rounded, size: 14, color: Color(0xFF3B82F6)),
            SizedBox(width: 6),
            Text('인식된 텍스트', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF64748B))),
          ]),
          const SizedBox(height: 8),
          Text('"${r.text}"', style: const TextStyle(fontSize: 14, color: Color(0xFF1E293B), height: 1.5)),
        ]),
      ),
      if (r.explanation.isNotEmpty) ...[
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.7),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Row(children: [
              Icon(Icons.smart_toy_rounded, size: 14, color: Color(0xFF8B5CF6)),
              SizedBox(width: 6),
              Text('AI 분석', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF64748B))),
            ]),
            const SizedBox(height: 8),
            Text(r.explanation, style: const TextStyle(fontSize: 13, color: Color(0xFF374151), height: 1.5)),
          ]),
        ),
      ],
    ]);
  }
}

class _SimCallCard extends StatelessWidget {
  final String name;
  final String number;
  final VoidCallback onTap;
  const _SimCallCard({required this.name, required this.number, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white.withValues(alpha: 0.7),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Row(children: [
          Container(
            width: 40, height: 40,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              color: Color(0xFFEFF6FF),
            ),
            child: const Icon(Icons.phone_rounded, color: Color(0xFF3B82F6), size: 20),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14, color: Color(0xFF1E293B))),
              const SizedBox(height: 2),
              Text(number, style: const TextStyle(fontSize: 12, color: Color(0xFF94A3B8))),
            ]),
          ),
          const Icon(Icons.play_circle_rounded, color: Color(0xFF3B82F6), size: 28),
        ]),
      ),
    );
  }
}
