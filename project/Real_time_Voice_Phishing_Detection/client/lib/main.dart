import 'dart:convert';
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'models/call_record.dart';
import 'models/analysis_result.dart';
import 'screens/home_screen.dart';
import 'screens/history_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const VoicePhishingApp());
}

class VoicePhishingApp extends StatelessWidget {
  const VoicePhishingApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Vaia',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        scaffoldBackgroundColor: Colors.transparent,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF3B82F6), brightness: Brightness.dark),
        textTheme: GoogleFonts.notoSansKrTextTheme(ThemeData.dark().textTheme),
      ),
      home: const MainShell(),
    );
  }
}

class MainShell extends StatefulWidget {
  const MainShell({super.key});

  @override
  State<MainShell> createState() => _MainShellState();
}

class _MainShellState extends State<MainShell> {
  int _currentIndex = 0;
  final List<CallRecord> _records = [];
  double _textScale = 1.0;

  static const _prefsKey = 'call_records';

  @override
  void initState() {
    super.initState();
    _loadRecords();
  }

  Future<void> _loadRecords() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_prefsKey);
      if (raw == null) return;
      final list = jsonDecode(raw) as List<dynamic>;
      final cutoff = DateTime.now().subtract(const Duration(days: 30));
      final loaded = list
          .map((e) => CallRecord.fromJson(e as Map<String, dynamic>))
          .where((r) => r.timestamp.isAfter(cutoff))
          .toList();
      if (mounted) setState(() => _records.addAll(loaded));
    } catch (e) {
      debugPrint('[Storage] 로드 오류: $e');
    }
  }

  Future<void> _saveRecords() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefsKey, jsonEncode(_records.map((r) => r.toJson()).toList()));
    } catch (e) {
      debugPrint('[Storage] 저장 오류: $e');
    }
  }

  void _onResult(AnalysisResult result) {
    final record = CallRecord.fromResult(result, Duration.zero);
    setState(() => _records.add(record));
    _saveRecords();
  }

  @override
  Widget build(BuildContext context) {
    final screens = [
      HomeScreen(records: _records, onResult: _onResult),
      HistoryScreen(records: _records),
      SettingsScreen(textScale: _textScale, onScaleSelect: (scale) => setState(() => _textScale = scale)),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFFF0F4FF),
      extendBody: true,
      body: Stack(
        children: [
          const _AppBackground(),
          MediaQuery(
            data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(_textScale)),
            child: SafeArea(bottom: false, child: screens[_currentIndex]),
          ),
        ],
      ),
      bottomNavigationBar: _FloatingNavBar(
        currentIndex: _currentIndex,
        onTap: (i) => setState(() => _currentIndex = i),
      ),
    );
  }
}

class _AppBackground extends StatelessWidget {
  const _AppBackground();

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFFF0F4FF), Color(0xFFEEF2FF), Color(0xFFEBF0FF)],
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
            ),
          ),
        ),
        Positioned(
          top: -100, right: -80,
          child: Container(
            width: 320, height: 320,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [
                const Color(0xFF3B82F6).withValues(alpha: 0.18),
                const Color(0xFF3B82F6).withValues(alpha: 0),
              ]),
            ),
          ),
        ),
        Positioned(
          top: 280, left: -80,
          child: Container(
            width: 240, height: 240,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [
                const Color(0xFF8B5CF6).withValues(alpha: 0.14),
                const Color(0xFF8B5CF6).withValues(alpha: 0),
              ]),
            ),
          ),
        ),
        Positioned(
          bottom: 220, right: -60,
          child: Container(
            width: 220, height: 220,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [
                const Color(0xFF06B6D4).withValues(alpha: 0.12),
                const Color(0xFF06B6D4).withValues(alpha: 0),
              ]),
            ),
          ),
        ),
      ],
    );
  }
}

class _FloatingNavBar extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onTap;
  const _FloatingNavBar({required this.currentIndex, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final bottomPadding = MediaQuery.of(context).padding.bottom;
    return Container(
      color: Colors.transparent,
      padding: EdgeInsets.fromLTRB(24, 0, 24, 16 + bottomPadding),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(28),
        child: BackdropFilter(
          filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
          child: Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.7),
              borderRadius: BorderRadius.circular(28),
              border: Border.all(color: const Color(0xFFE2E8F0)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _NavItem(icon: Icons.home_rounded, label: '홈', selected: currentIndex == 0, onTap: () => onTap(0)),
                _NavItem(icon: Icons.history_rounded, label: '이력', selected: currentIndex == 1, onTap: () => onTap(1)),
                _NavItem(icon: Icons.settings_rounded, label: '설정', selected: currentIndex == 2, onTap: () => onTap(2)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;
  const _NavItem({required this.icon, required this.label, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
        decoration: BoxDecoration(
          color: selected ? const Color(0xFF3B82F6) : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: selected ? Colors.white : const Color(0xFF94A3B8), size: 20),
            AnimatedSize(
              duration: const Duration(milliseconds: 220),
              curve: Curves.easeOut,
              child: selected
                  ? Row(children: [
                      const SizedBox(width: 6),
                      Text(label, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
                    ])
                  : const SizedBox.shrink(),
            ),
          ],
        ),
      ),
    );
  }
}
