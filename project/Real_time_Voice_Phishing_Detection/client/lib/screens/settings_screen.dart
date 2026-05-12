import 'dart:ui';
import 'package:flutter/material.dart';

const _kPrimary = Color(0xFF3B82F6);
const _kText = Color(0xFF111827);
const _kTextSub = Color(0xFF6B7280);

class SettingsScreen extends StatelessWidget {
  final double textScale;
  final ValueChanged<double> onScaleSelect;
  const SettingsScreen({super.key, required this.textScale, required this.onScaleSelect});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: ListView(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 100),
        children: [
          Row(children: [
            Container(
              width: 34, height: 34,
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_kPrimary, Color(0xFF60A5FA)]),
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.settings_rounded, color: Colors.white, size: 18),
            ),
            const SizedBox(width: 10),
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('설정', style: TextStyle(color: _kText, fontWeight: FontWeight.bold, fontSize: 20)),
              Text('앱 환경설정', style: TextStyle(color: _kTextSub, fontSize: 11)),
            ]),
          ]),
          const SizedBox(height: 24),
          Text('접근성', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: _kTextSub, letterSpacing: 0.5)),
          const SizedBox(height: 10),
          _GlassCard(
            child: _SettingsRow(
              icon: Icons.text_fields_rounded,
              label: '글씨 크기',
              value: textScale == 0.9 ? '작게' : textScale == 1.3 ? '크게' : '보통',
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => _TextSizeScreen(
                    current: textScale,
                    onSelect: onScaleSelect,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;
  final VoidCallback onTap;
  const _SettingsRow({required this.icon, required this.label, required this.value, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Row(children: [
        Container(
          padding: const EdgeInsets.all(7),
          decoration: BoxDecoration(color: const Color(0xFFEFF6FF), borderRadius: BorderRadius.circular(9)),
          child: Icon(icon, color: _kPrimary, size: 16),
        ),
        const SizedBox(width: 12),
        Expanded(child: Text(label, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: _kText))),
        Text(value, style: TextStyle(fontSize: 13, color: _kTextSub)),
        const SizedBox(width: 4),
        const Icon(Icons.chevron_right_rounded, color: Color(0xFFD1D5DB), size: 20),
      ]),
    );
  }
}

class _GlassCard extends StatelessWidget {
  final Widget child;
  const _GlassCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: const Color(0xFFE2E8F0)),
          ),
          child: child,
        ),
      ),
    );
  }
}

class _TextSizeScreen extends StatelessWidget {
  final double current;
  final ValueChanged<double> onSelect;
  const _TextSizeScreen({required this.current, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    final options = [
      (label: '작게', scale: 0.9, iconSize: 14.0),
      (label: '보통', scale: 1.0, iconSize: 18.0),
      (label: '크게', scale: 1.3, iconSize: 24.0),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded, color: Color(0xFF111827), size: 18),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('글씨 크기', style: TextStyle(color: Color(0xFF111827), fontWeight: FontWeight.bold, fontSize: 17)),
      ),
      body: Padding(
        padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
        child: Column(children: [
          Row(children: options.map((o) {
            final selected = current == o.scale;
            return Expanded(
              child: GestureDetector(
                onTap: () {
                  onSelect(o.scale);
                  Navigator.pop(context);
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 180),
                  margin: const EdgeInsets.symmetric(horizontal: 5),
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  decoration: BoxDecoration(
                    color: selected ? _kPrimary : Colors.white,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: selected ? _kPrimary : const Color(0xFFE2E8F0)),
                    boxShadow: selected ? [BoxShadow(color: _kPrimary.withValues(alpha: 0.25), blurRadius: 12, offset: const Offset(0, 4))] : [],
                  ),
                  child: Column(children: [
                    Icon(Icons.text_fields_rounded, size: o.iconSize, color: selected ? Colors.white : _kTextSub),
                    const SizedBox(height: 8),
                    Text(o.label, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: selected ? Colors.white : _kTextSub)),
                    if (selected) ...[
                      const SizedBox(height: 6),
                      const Icon(Icons.check_rounded, color: Colors.white, size: 16),
                    ],
                  ]),
                ),
              ),
            );
          }).toList()),
        ]),
      ),
    );
  }
}
