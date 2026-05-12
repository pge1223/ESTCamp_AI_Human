import 'dart:ui';
import 'package:flutter/material.dart';
import '../models/call_record.dart';
import '../models/analysis_result.dart';
import 'call_screen.dart';

const _kPrimary      = Color(0xFF3B82F6);
const _kPrimaryLight = Color(0xFF60A5FA);
const _kText         = Color(0xFF111827);
const _kTextSub      = Color(0xFF6B7280);
const _kTextHint     = Color(0xFF9CA3AF);

const _levelColors = [
  Color(0xFF16A34A),
  Color(0xFFD97706),
  Color(0xFFEA580C),
  Color(0xFFDC2626),
];

class HomeScreen extends StatefulWidget {
  final List<CallRecord> records;
  final void Function(AnalysisResult) onResult;

  const HomeScreen({super.key, required this.records, required this.onResult});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  late AnimationController _pulseCtrl;
  late AnimationController _entryCtrl;
  late AnimationController _chartCtrl;
  late List<Animation<double>> _sectionAnims;

  // 통계 계산
  bool _isToday(DateTime dt) {
    final now = DateTime.now();
    return dt.year == now.year && dt.month == now.month && dt.day == now.day;
  }

  int get _totalCalls   => widget.records.length;
  int get _dangerCalls  => widget.records.where((r) => r.warningLevel == 3).length;
  int get _warnCalls    => widget.records.where((r) => r.warningLevel == 1 || r.warningLevel == 2).length;
  int get _safeCalls    => widget.records.where((r) => r.warningLevel == 0).length;
  int get _avgRisk      => _totalCalls == 0 ? 0 : widget.records.map((r) => r.riskScore).reduce((a, b) => a + b) ~/ _totalCalls;
  int get _fakeVoice    => widget.records.where((r) => r.isFakeVoice).length;
  int get _detectedToday => widget.records.where((r) => _isToday(r.timestamp) && r.warningLevel >= 1).length;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 2000))
      ..repeat();
    _entryCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..forward();
    _chartCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 1000));
    _sectionAnims = List.generate(6, (i) => CurvedAnimation(
      parent: _entryCtrl,
      curve: Interval((i * 0.1).clamp(0, 0.6), (i * 0.1 + 0.5).clamp(0, 1), curve: Curves.easeOut),
    ));
    Future.delayed(const Duration(milliseconds: 300), () {
      if (mounted) _chartCtrl.forward();
    });
  }

  @override
  void dispose() {
    _pulseCtrl.dispose();
    _entryCtrl.dispose();
    _chartCtrl.dispose();
    super.dispose();
  }

  void _startAnalysis() async {
    final result = await Navigator.of(context).push<AnalysisResult>(
      MaterialPageRoute(builder: (_) => const CallScreen()),
    );
    if (result != null) widget.onResult(result);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
        children: [
          // 상단 바
          Row(children: [
            Container(
              width: 34, height: 34,
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_kPrimary, _kPrimaryLight]),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.shield, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
            const Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Vaia', style: TextStyle(color: _kText, fontWeight: FontWeight.bold, fontSize: 20)),
                Text('보이스피싱 탐지', style: TextStyle(color: _kTextSub, fontSize: 11)),
              ]),
            ),
            Stack(alignment: Alignment.center, children: [
              IconButton(icon: const Icon(Icons.notifications_outlined, color: _kTextSub), onPressed: () {}),
              if (_detectedToday > 0)
                Positioned(
                  right: 10, top: 10,
                  child: Container(width: 8, height: 8,
                      decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle)),
                ),
            ]),
          ]),
          const SizedBox(height: 28),

          // ▶ 분석 시작 버튼
          _FadeSlide(
            animation: _sectionAnims[0],
            child: Center(
              child: Column(children: [
                GestureDetector(
                  onTap: _startAnalysis,
                  child: AnimatedBuilder(
                    animation: _pulseCtrl,
                    builder: (_, _) {
                      final t = _pulseCtrl.value;
                      return SizedBox(
                        width: 260, height: 260,
                        child: Stack(alignment: Alignment.center, children: [
                          // 파동 링 3개 — 순서대로 퍼지며 사라짐
                          ...List.generate(3, (i) {
                            final phase = (t + i / 3.0) % 1.0;
                            final size = 130.0 + phase * 130.0;
                            final alpha = (1.0 - phase) * 0.22;
                            return Container(
                              width: size, height: size,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: _kPrimary.withValues(alpha: alpha),
                                  width: 2.0,
                                ),
                              ),
                            );
                          }),
                          // 버튼 본체
                          Container(
                            width: 130, height: 130,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              gradient: const LinearGradient(
                                colors: [_kPrimary, _kPrimaryLight],
                                begin: Alignment.topLeft,
                                end: Alignment.bottomRight,
                              ),
                              boxShadow: [
                                BoxShadow(
                                  color: _kPrimary.withValues(alpha: 0.45),
                                  blurRadius: 32,
                                  offset: const Offset(0, 8),
                                ),
                              ],
                            ),
                            child: const Icon(Icons.play_arrow_rounded, color: Colors.white, size: 64),
                          ),
                        ]),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 16),
                const Text('분석 시작',
                    style: TextStyle(color: _kText, fontSize: 18, fontWeight: FontWeight.bold)),
                const SizedBox(height: 4),
                const Text('버튼을 눌러 통화 분석을 시작하세요',
                    style: TextStyle(color: _kTextSub, fontSize: 13)),
              ]),
            ),
          ),
          const SizedBox(height: 32),

          // ── 통계 섹션 ──────────────────────────────────────────
          _FadeSlide(
            animation: _sectionAnims[1],
            child: _SummaryCard(
                total: _totalCalls, danger: _dangerCalls,
                avgRisk: _avgRisk, fakeVoice: _fakeVoice),
          ),
          const SizedBox(height: 14),

          _FadeSlide(
            animation: _sectionAnims[2],
            child: _RiskDistribution(
                safe: _safeCalls, warn: _warnCalls,
                danger: _dangerCalls, total: _totalCalls, chartCtrl: _chartCtrl),
          ),
          const SizedBox(height: 14),

          _FadeSlide(
            animation: _sectionAnims[3],
            child: _WeeklyTrend(records: widget.records, chartCtrl: _chartCtrl),
          ),
          const SizedBox(height: 14),

          _FadeSlide(
            animation: _sectionAnims[4],
            child: _DetectionRate(
                dangerCalls: _dangerCalls, totalCalls: _totalCalls, chartCtrl: _chartCtrl),
          ),
        ],
      ),
    );
  }
}


// ── 공통 ──────────────────────────────────────────────────────

class _FadeSlide extends StatelessWidget {
  final Animation<double> animation;
  final Widget child;
  const _FadeSlide({required this.animation, required this.child});

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (_, _) => Opacity(
        opacity: animation.value.clamp(0.0, 1.0),
        child: Transform.translate(offset: Offset(0, 18 * (1 - animation.value)), child: child),
      ),
    );
  }
}

class _GlassCard extends StatelessWidget {
  final Widget child;
  final EdgeInsets padding;
  const _GlassCard({required this.child, required this.padding});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE2E8F0)),
            boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 12, offset: const Offset(0, 2))],
          ),
          child: child,
        ),
      ),
    );
  }
}

// ── 전체 요약 카드 ─────────────────────────────────────────────

class _SummaryCard extends StatelessWidget {
  final int total, danger, avgRisk, fakeVoice;
  const _SummaryCard({required this.total, required this.danger, required this.avgRisk, required this.fakeVoice});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1E40AF), Color(0xFF1E5FD8), Color(0xFF3B82F6)],
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white.withValues(alpha: 0.15)),
        boxShadow: [BoxShadow(color: const Color(0xFF3B82F6).withValues(alpha: 0.35), blurRadius: 28, offset: const Offset(0, 8))],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('전체 요약', style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 12, letterSpacing: 0.5)),
        const SizedBox(height: 4),
        TweenAnimationBuilder<int>(
          tween: IntTween(begin: 0, end: total),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOut,
          builder: (_, val, _) => Text('총 $val건 분석',
              style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.bold)),
        ),
        const SizedBox(height: 16),
        Row(children: [
          _SummaryItem(label: '위험 탐지', value: danger, unit: '건', color: const Color(0xFFEF4444)),
          Container(width: 1, height: 32, color: Colors.white.withValues(alpha: 0.2), margin: const EdgeInsets.symmetric(horizontal: 16)),
          _SummaryItem(label: '평균 위험점수', value: avgRisk, unit: '점', color: Colors.white),
          Container(width: 1, height: 32, color: Colors.white.withValues(alpha: 0.2), margin: const EdgeInsets.symmetric(horizontal: 16)),
          _SummaryItem(label: '합성 음성', value: fakeVoice, unit: '건', color: const Color(0xFFFBBF24)),
        ]),
      ]),
    );
  }
}

class _SummaryItem extends StatelessWidget {
  final String label, unit;
  final int value;
  final Color color;
  const _SummaryItem({required this.label, required this.value, required this.unit, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: TextStyle(color: Colors.white.withValues(alpha: 0.6), fontSize: 11)),
        const SizedBox(height: 2),
        TweenAnimationBuilder<int>(
          tween: IntTween(begin: 0, end: value),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOut,
          builder: (_, val, _) => RichText(
            text: TextSpan(children: [
              TextSpan(text: '$val', style: TextStyle(color: color, fontSize: 20, fontWeight: FontWeight.bold)),
              TextSpan(text: unit, style: TextStyle(color: color.withValues(alpha: 0.7), fontSize: 12)),
            ]),
          ),
        ),
      ]),
    );
  }
}

// ── 위험도 분포 ───────────────────────────────────────────────

class _RiskDistribution extends StatelessWidget {
  final int safe, warn, danger, total;
  final AnimationController chartCtrl;
  const _RiskDistribution({required this.safe, required this.warn, required this.danger, required this.total, required this.chartCtrl});

  @override
  Widget build(BuildContext context) {
    final items = [
      (label: '안전',    count: safe,   color: _levelColors[0]),
      (label: '주의/경고', count: warn,   color: _levelColors[1]),
      (label: '위험',    count: danger, color: _levelColors[3]),
    ];
    return _GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('위험도 분포', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: _kText)),
        const SizedBox(height: 16),
        AnimatedBuilder(
          animation: chartCtrl,
          builder: (_, _) {
            final progress = CurvedAnimation(parent: chartCtrl, curve: Curves.easeOut).value;
            return Column(
              children: items.map((item) {
                final ratio = total == 0 ? 0.0 : item.count / total;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Row(children: [
                    SizedBox(width: 60, child: Text(item.label, style: const TextStyle(fontSize: 12, color: _kTextSub))),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Stack(children: [
                        Container(height: 10, decoration: BoxDecoration(color: const Color(0xFFEEF2FF), borderRadius: BorderRadius.circular(5))),
                        FractionallySizedBox(
                          widthFactor: (ratio * progress).clamp(0.0, 1.0),
                          child: Container(height: 10, decoration: BoxDecoration(color: item.color, borderRadius: BorderRadius.circular(5))),
                        ),
                      ]),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 32,
                      child: Text('${item.count}건', textAlign: TextAlign.right,
                          style: TextStyle(fontSize: 12, color: item.color, fontWeight: FontWeight.bold)),
                    ),
                  ]),
                );
              }).toList(),
            );
          },
        ),
      ]),
    );
  }
}

// ── 이번 주 통화 수 ───────────────────────────────────────────

class _WeeklyTrend extends StatelessWidget {
  final List<CallRecord> records;
  final AnimationController chartCtrl;
  const _WeeklyTrend({required this.records, required this.chartCtrl});

  @override
  Widget build(BuildContext context) {
    const days = ['월', '화', '수', '목', '금', '토', '일'];
    final counts = List.filled(7, 0);
    final now = DateTime.now();
    final today = now.weekday - 1;
    final weekStart = now.subtract(Duration(days: today));

    for (final r in records) {
      final isThisWeek = !r.timestamp.isBefore(DateTime(weekStart.year, weekStart.month, weekStart.day));
      if (isThisWeek) counts[r.timestamp.weekday - 1]++;
    }
    final maxCount = counts.reduce((a, b) => a > b ? a : b).clamp(1, 999);

    return _GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('이번 주 통화 수', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: _kText)),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: _kPrimary.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(20)),
            child: const Text('전체', style: TextStyle(color: _kPrimary, fontSize: 11, fontWeight: FontWeight.w600)),
          ),
        ]),
        const SizedBox(height: 18),
        AnimatedBuilder(
          animation: chartCtrl,
          builder: (_, _) => Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: List.generate(7, (i) {
              final isToday = i == today;
              final ratio = counts[i] / maxCount;
              final delay = i / 7 * 0.5;
              final progress = ((chartCtrl.value - delay) / (1 - delay)).clamp(0.0, 1.0);
              final easedProgress = Curves.easeOut.transform(progress);
              final barHeight = (70 * ratio * easedProgress + 4).clamp(4.0, 74.0);
              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 3),
                  child: Column(children: [
                    SizedBox(
                      height: 16,
                      child: counts[i] > 0 && progress > 0
                          ? Opacity(
                              opacity: easedProgress,
                              child: Text('${counts[i]}', textAlign: TextAlign.center,
                                  style: TextStyle(fontSize: 10, color: isToday ? _kPrimary : _kTextSub, fontWeight: FontWeight.bold)),
                            )
                          : null,
                    ),
                    const SizedBox(height: 2),
                    Container(
                      height: barHeight,
                      decoration: BoxDecoration(
                        gradient: isToday ? const LinearGradient(colors: [_kPrimary, _kPrimaryLight], begin: Alignment.bottomCenter, end: Alignment.topCenter) : null,
                        color: isToday ? null : const Color(0xFFDDE3EF),
                        borderRadius: BorderRadius.circular(5),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(days[i], style: TextStyle(
                        fontSize: 11,
                        color: isToday ? _kPrimary : _kTextHint,
                        fontWeight: isToday ? FontWeight.bold : FontWeight.normal)),
                  ]),
                ),
              );
            }),
          ),
        ),
      ]),
    );
  }
}

// ── 위험 탐지율 ───────────────────────────────────────────────

class _DetectionRate extends StatelessWidget {
  final int dangerCalls, totalCalls;
  final AnimationController chartCtrl;
  const _DetectionRate({required this.dangerCalls, required this.totalCalls, required this.chartCtrl});

  @override
  Widget build(BuildContext context) {
    final rate = totalCalls == 0 ? 0.0 : dangerCalls / totalCalls;
    return _GlassCard(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('위험 탐지율', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: _kText)),
        const SizedBox(height: 16),
        Row(children: [
          Expanded(
            child: AnimatedBuilder(
              animation: chartCtrl,
              builder: (_, _) {
                final progress = CurvedAnimation(parent: chartCtrl, curve: Curves.easeOut).value;
                return Stack(children: [
                  Container(height: 12, decoration: BoxDecoration(color: const Color(0xFFEEF2FF), borderRadius: BorderRadius.circular(6))),
                  FractionallySizedBox(
                    widthFactor: (rate * progress).clamp(0.0, 1.0),
                    child: Container(
                      height: 12,
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [Color(0xFFF97316), Color(0xFFEF4444)]),
                        borderRadius: BorderRadius.circular(6),
                      ),
                    ),
                  ),
                ]);
              },
            ),
          ),
          const SizedBox(width: 12),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: rate * 100),
            duration: const Duration(milliseconds: 1000),
            curve: Curves.easeOut,
            builder: (_, val, _) => Text('${val.toStringAsFixed(1)}%',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFDC2626))),
          ),
        ]),
        const SizedBox(height: 8),
        Text('전체 $totalCalls건 중 위험 $dangerCalls건 탐지',
            style: const TextStyle(color: _kTextSub, fontSize: 12)),
      ]),
    );
  }
}
