import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from pipeline.classifier import KoELECTRAClassifier
from pipeline.filter import PHISHING_KEYWORDS, PHISHING_KEYWORDS_WEAK, _URL_RE, _normalize

WINDOW_WORDS      = 100  # 슬라이딩 윈도우 크기 (단어 수)
SCORE_PER_HIT     = 15   # 고위험 키워드 1건당 점수
SCORE_WEAK_HIT    = 7    # 저위험 키워드 1건당 점수
URL_SCORE         = 30   # URL 패턴 1건당 점수 (강한 신호)
ELECTRA_THRESHOLD = 15   # KoELECTRA 실행 기준 점수

# 한 통화 세션 동안 유지되는 상태
_full_text: str = ""
_word_buffer: list[str] = []
_classifier: KoELECTRAClassifier | None = None


def _get_classifier() -> KoELECTRAClassifier:
    global _classifier
    if _classifier is None:
        _classifier = KoELECTRAClassifier()
    return _classifier


def _keyword_score(text: str) -> int:
    """현재 윈도우 텍스트의 키워드 점수 합산."""
    normalized = _normalize(text).lower()
    total = 0
    for keywords in PHISHING_KEYWORDS.values():
        for kw in keywords:
            if kw.lower() in normalized:
                total += SCORE_PER_HIT
    for keywords in PHISHING_KEYWORDS_WEAK.values():
        for kw in keywords:
            if kw.lower() in normalized:
                total += SCORE_WEAK_HIT
    # URL은 normalize가 점(.)을 제거하므로 원본 텍스트에서 검출
    total += len(_URL_RE.findall(text)) * URL_SCORE
    return total


def reset() -> None:
    """새 통화 시작 시 호출 — 누적 상태 초기화."""
    global _full_text, _word_buffer
    _full_text = ""
    _word_buffer = []


def analyze(text: str) -> dict:
    """
    STT 텍스트 청크를 받아 위험도를 반환.

    Returns:
        danger_level  : float 0.0~1.0 (KoELECTRA 미실행 시 0.0)
        categories    : list[str]  ["기관사칭", "금전요구", "개인정보"] 중 탐지된 항목
        keyword_score : int        이번 윈도우의 키워드 점수
        triggered     : bool       KoELECTRA 실행 여부
    """
    global _full_text, _word_buffer

    # 1. 누적
    _full_text = (_full_text + " " + text).strip()
    _word_buffer.extend(text.split())

    # 2. 슬라이딩 윈도우 키워드 스코어링 (<10ms)
    window_text = " ".join(_word_buffer[-WINDOW_WORDS:])
    score = _keyword_score(window_text)

    # 3. KoELECTRA 추론 — 31점 이상일 때만 실행 (~80ms)
    if score >= ELECTRA_THRESHOLD:
        result = _get_classifier().classify(_full_text)
        return {
            "danger_level": result.risk_score,
            "categories": result.detected,
            "keyword_score": score,
            "triggered": True,
        }

    # 4. 미달 → 위험도 없음
    return {
        "danger_level": 0.0,
        "categories": [],
        "keyword_score": score,
        "triggered": False,
    }


