import re
from dataclasses import dataclass, field

# 고위험 키워드 — 피싱에서만 사용되거나 단독으로도 강한 신호 (15점)
PHISHING_KEYWORDS: dict[str, list[str]] = {
    "기관사칭": [
        "검찰", "검사", "검사님", "수사관", "금감원", "금융감독원",
        "경찰청", "사이버수사대", "중앙수사부", "세무서",
        "소득세과", "법인팀", "첨단범죄수사팀", "서울중앙지검",
        "지검", "공단",
        "수사과", "사무관", "조사관", "수사팀",
        "공문", "사건조회", "나의사건", "소환",
        "피의자", "사건번호",
        "녹취", "제3자",
        "법무부", "국가정보원", "감사원", "보건복지부", "소비자청", "금융정보분석원",
    ],
    "금전요구": [
        "계좌이체", "안전계좌", "공탁금", "환급", "국가안전계좌",
        "대포통장", "통장매입", "환치기", "합의금",
        "동결", "양도", "대환",
        "FIU", "수거", "봉투",
    ],
    "개인정보": [
        "주민번호", "주민등록번호", "otp", "카드번호", "비밀번호",
        "계좌번호", "공인인증서", "보안카드", "신분증",
        "앞면촬영", "인증번호", "대표자번호", "개인정보유출",
        "실명인증", "실명확인", "본인확인",
        "CVC", "유효기간", "카드뒷면",
        "명의",
    ],
    "기술적위협": [
        "팀뷰어", "원격제어", "악성코드", "해킹", "앱설치", "보안업데이트",
        "삭제후재설치", "공식홈페이지", "출처불명링크", "URL클릭", "파밍",
        "주소창", "인터넷주소",
    ],
    "심리적압박": [
        "비밀수사", "통화내용녹음", "끊으면범죄인정", "재판출두", "구속영장",
        "범죄연루", "소환장",
    ],
    "고립및기망": [
        "안전한장소", "외부연락차단",
        "AI목소리", "가족목소리", "영상통화거부", "지정질문"
    ]
}

# 저위험 키워드 — 정상 대화에서도 등장하는 단어, 복수 조합 시 신호 (7점)
PHISHING_KEYWORDS_WEAK: dict[str, list[str]] = {
    "기관사칭": ["형사", "경찰", "법원", "국세청", "수사", "조사", "한국은행"],
    "금전요구": [
        "송금", "이체", "입금", "현금", "출금", "인출",
        "통장", "계좌", "자산", "예금", "대출",
        "카카오페이", "카카오뱅크", "상환", "가족사고",
        "신용점수", "임대", "채무", "연체",
    ],
    "개인정보": ["신용카드", "유출", "앞면", "비번", "패스워드", "여권번호", "생년월일"],
    "기술적위협": ["삭제", "설치", "링크", "이상징후"],
    "심리적압박": [
        "연루", "불법거래", "금융사기", "다급함", "의심스러운",
        "이상거래", "보안조치", "계좌보호", "거래정지",
        "2차피해", "긴급상황", "신용불량",
    ],
    "고립및기망": ["모텔", "투숙", "고립"],
    "기관관련": ["금융권", "공공기관"],
}

# 의심 URL 패턴: 숫자가 섞인 도메인(ykiscs24.kr) 또는 발화 중 "www" 언급
# _normalize가 점(.)을 제거하므로 반드시 원본 텍스트에 적용
_URL_RE = re.compile(
    r'\bwww\b'                                           # 발화 중 "www" 단독
    r'|[a-zA-Z가-힣]+\d+[a-zA-Z0-9가-힣]*\.[a-zA-Z]{2,}',  # 숫자 포함 도메인
    re.IGNORECASE,
)

WINDOW_SIZE = 5   # 한 윈도우에 포함할 세그먼트 수
STRIDE = 2        # 윈도우 이동 간격

# 공백/구두점을 제거해 검색 정확도를 높이기 위한 패턴
_PUNCT = re.compile(r"[\s\-·,\.!?。、]")


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text)


FILTER_THRESHOLD = 15  # Dart _filterThreshold와 동기화
_KEYWORD_SCORE = 15
_WEAK_SCORE = 7
_URL_SCORE = 30


@dataclass
class WindowResult:
    start_idx: int
    end_idx: int
    text: str
    score: int = 0
    matched_categories: dict[str, list[str]] = field(default_factory=dict)
    weak_categories: dict[str, list[str]] = field(default_factory=dict)
    is_suspicious: bool = False


class SlidingWindowFilter:
    def __init__(self, window_size: int = WINDOW_SIZE, stride: int = STRIDE):
        self.window_size = window_size
        self.stride = stride

    def _match_keywords(self, text: str) -> tuple[dict[str, list[str]], dict[str, list[str]], int]:
        normalized = _normalize(text).lower()
        matched: dict[str, list[str]] = {}
        weak: dict[str, list[str]] = {}
        score = 0

        for category, keywords in PHISHING_KEYWORDS.items():
            hits = [kw for kw in keywords if kw.lower() in normalized]
            if hits:
                matched[category] = hits
                score += len(hits) * _KEYWORD_SCORE

        for category, keywords in PHISHING_KEYWORDS_WEAK.items():
            hits = [kw for kw in keywords if kw.lower() in normalized]
            if hits:
                weak[category] = hits
                score += len(hits) * _WEAK_SCORE

        # URL은 normalize가 점을 제거하므로 원본 텍스트에서 검출
        url_hits = _URL_RE.findall(text)
        if url_hits:
            matched["URL피싱"] = url_hits
            score += len(url_hits) * _URL_SCORE

        return matched, weak, score

    def apply(self, segments) -> list[WindowResult]:
        results: list[WindowResult] = []
        n = len(segments)

        if n == 0:
            return results

        for i in range(0, max(1, n - self.window_size + 1), self.stride):
            window = segments[i : i + self.window_size]
            text = " ".join(seg.text for seg in window)
            matched, weak, score = self._match_keywords(text)
            results.append(
                WindowResult(
                    start_idx=i,
                    end_idx=min(i + self.window_size, n) - 1,
                    text=text,
                    score=score,
                    matched_categories=matched,
                    weak_categories=weak,
                    is_suspicious=score >= FILTER_THRESHOLD,
                )
            )
        return results
