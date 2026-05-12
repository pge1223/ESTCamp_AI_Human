import 'dart:ui';
import 'package:flutter/material.dart';
import '../models/call_record.dart';

const _kPrimary = Color(0xFF3B82F6);
const _kText = Color(0xFF111827);
const _kTextSub = Color(0xFF6B7280);
const _kTextHint = Color(0xFF9CA3AF);

const _levelColors = [
  Color(0xFF16A34A),
  Color(0xFFD97706),
  Color(0xFFEA580C),
  Color(0xFFDC2626),
];
const _levelIcons = [
  Icons.check_circle_rounded,
  Icons.warning_amber_rounded,
  Icons.warning_amber_rounded,
  Icons.dangerous_rounded,
];

class HistoryScreen extends StatefulWidget {
  final List<CallRecord> records;
  const HistoryScreen({super.key, required this.records});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  String _searchQuery = '';
  int _selectedFilter = 0;

  List<CallRecord> get _filtered {
    return widget.records.where((r) {
      final matchSearch = _searchQuery.isEmpty || r.text.contains(_searchQuery);
      final matchFilter = _selectedFilter == 0 ||
          (_selectedFilter == 1 && r.warningLevel == 3) ||
          (_selectedFilter == 2 && (r.warningLevel == 1 || r.warningLevel == 2)) ||
          (_selectedFilter == 3 && r.warningLevel == 0);
      return matchSearch && matchFilter;
    }).toList();
  }

  int _countByLevel(int level) => widget.records.where((r) {
        if (level == 1) return r.warningLevel == 3;
        if (level == 2) return r.warningLevel == 1 || r.warningLevel == 2;
        return r.warningLevel == 0;
      }).length;

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;
    final dangerCount = _countByLevel(1);
    final cautionCount = _countByLevel(2);
    final safeCount = _countByLevel(3);

    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
            child: Row(children: [
              Container(
                width: 34, height: 34,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [_kPrimary, Color(0xFF60A5FA)]),
                  borderRadius: BorderRadius.circular(9),
                ),
                child: const Icon(Icons.history_rounded, color: Colors.white, size: 18),
              ),
              const SizedBox(width: 10),
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('통화 이력', style: TextStyle(color: _kText, fontWeight: FontWeight.bold, fontSize: 20)),
                Text('AI 분석 결과 기록', style: TextStyle(color: _kTextSub, fontSize: 11)),
              ]),
            ]),
          ),
          Expanded(
            child: widget.records.isEmpty
                ? _buildEmpty()
                : Column(
                    children: [
                      Padding(
                        padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
                        child: Column(children: [
                          _GlassTextField(
                            onChanged: (v) => setState(() => _searchQuery = v),
                            hint: '번호, 키워드로 검색...',
                          ),
                          const SizedBox(height: 12),
                          Row(children: [
                            _StatBadge(count: dangerCount, label: '위험', color: const Color(0xFFDC2626)),
                            const SizedBox(width: 10),
                            _StatBadge(count: cautionCount, label: '주의', color: const Color(0xFFEA580C)),
                            const SizedBox(width: 10),
                            _StatBadge(count: safeCount, label: '안전', color: const Color(0xFF16A34A)),
                          ]),
                          const SizedBox(height: 12),
                          SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(children: [
                              _FilterChip(label: '전체 ${widget.records.length}', selected: _selectedFilter == 0, onTap: () => setState(() => _selectedFilter = 0)),
                              const SizedBox(width: 8),
                              _FilterChip(label: '위험 $dangerCount', selected: _selectedFilter == 1, onTap: () => setState(() => _selectedFilter = 1)),
                              const SizedBox(width: 8),
                              _FilterChip(label: '주의 $cautionCount', selected: _selectedFilter == 2, onTap: () => setState(() => _selectedFilter = 2)),
                              const SizedBox(width: 8),
                              _FilterChip(label: '안전 $safeCount', selected: _selectedFilter == 3, onTap: () => setState(() => _selectedFilter = 3)),
                            ]),
                          ),
                        ]),
                      ),
                      const SizedBox(height: 12),
                      Expanded(
                        child: filtered.isEmpty
                            ? Center(child: Text('검색 결과가 없습니다', style: TextStyle(color: _kTextHint)))
                            : ListView.separated(
                                padding: const EdgeInsets.fromLTRB(20, 0, 20, 100),
                                itemCount: filtered.length,
                                separatorBuilder: (_, _) => const SizedBox(height: 8),
                                itemBuilder: (_, i) => _RecordTile(
                                  record: filtered[i],
                                  levelColor: _levelColors[filtered[i].warningLevel],
                                  levelIcon: _levelIcons[filtered[i].warningLevel],
                                ),
                              ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildEmpty() {
    return Center(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.history_rounded, size: 60, color: _kTextHint),
        const SizedBox(height: 12),
        Text('통화 이력이 없습니다', style: TextStyle(color: _kTextSub, fontSize: 15)),
        const SizedBox(height: 4),
        Text('통화가 끝나면 자동으로 분석 결과가 저장됩니다', style: TextStyle(color: _kTextHint, fontSize: 12)),
      ]),
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
      borderRadius: BorderRadius.circular(14),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: padding,
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: child,
        ),
      ),
    );
  }
}

class _GlassTextField extends StatelessWidget {
  final ValueChanged<String> onChanged;
  final String hint;
  const _GlassTextField({required this.onChanged, required this.hint});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: TextField(
            onChanged: onChanged,
            style: TextStyle(color: _kText, fontSize: 13),
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(color: _kTextHint, fontSize: 13),
              prefixIcon: Icon(Icons.search, color: _kTextHint, size: 20),
              filled: false,
              contentPadding: const EdgeInsets.symmetric(vertical: 0),
              border: InputBorder.none,
            ),
          ),
        ),
      ),
    );
  }
}

class _StatBadge extends StatelessWidget {
  final int count;
  final String label;
  final Color color;
  const _StatBadge({required this.count, required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: color.withValues(alpha: 0.2)),
            ),
            child: Column(children: [
              Text('$count', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: color)),
              Text(label, style: TextStyle(fontSize: 12, color: color.withValues(alpha: 0.8))),
            ]),
          ),
        ),
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _FilterChip({required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: BoxDecoration(
          color: selected ? _kPrimary : const Color(0xFFF8FAFC),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: selected ? _kPrimary : const Color(0xFFE2E8F0)),
        ),
        child: Text(label, style: TextStyle(
          color: selected ? Colors.white : _kTextSub,
          fontSize: 13,
          fontWeight: selected ? FontWeight.bold : FontWeight.normal,
        )),
      ),
    );
  }
}

class _RecordTile extends StatefulWidget {
  final CallRecord record;
  final Color levelColor;
  final IconData levelIcon;
  const _RecordTile({required this.record, required this.levelColor, required this.levelIcon});

  @override
  State<_RecordTile> createState() => _RecordTileState();
}

class _RecordTileState extends State<_RecordTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final r = widget.record;
    return _GlassCard(
      padding: EdgeInsets.zero,
      child: Column(children: [
        ListTile(
          leading: Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              color: widget.levelColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(widget.levelIcon, color: widget.levelColor, size: 20),
          ),
          title: Row(children: [
            Expanded(
              child: Text(r.text,
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: _kText),
                  maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: widget.levelColor.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(r.levelLabel, style: TextStyle(color: widget.levelColor, fontSize: 10, fontWeight: FontWeight.bold)),
            ),
          ]),
          subtitle: Text(
            '${r.durationString} · ${r.timestamp.month}.${r.timestamp.day} ${r.timestamp.hour.toString().padLeft(2, '0')}:${r.timestamp.minute.toString().padLeft(2, '0')}',
            style: TextStyle(color: _kTextHint, fontSize: 11),
          ),
          trailing: GestureDetector(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Icon(_expanded ? Icons.expand_less : Icons.expand_more, color: _kTextHint),
          ),
        ),
        if (_expanded)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFF8FAFC),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFE2E8F0)),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('AI 분석', style: TextStyle(color: _kTextHint, fontSize: 11)),
                const SizedBox(height: 4),
                Text(r.explanation, style: TextStyle(fontSize: 13, color: _kText)),
                const SizedBox(height: 8),
                Text('위험 점수: ${r.riskScore}/100 · ${r.isFakeVoice ? "합성 음성 의심" : "정상 음성"}',
                    style: TextStyle(fontSize: 11, color: _kTextSub)),
              ]),
            ),
          ),
      ]),
    );
  }
}
