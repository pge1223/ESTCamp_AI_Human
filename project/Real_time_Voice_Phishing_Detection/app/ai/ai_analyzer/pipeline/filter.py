import re
from dataclasses import dataclass, field

# 1차 필터 키워드 사전
PHISHING_KEYWORDS: dict[str, list[str]] = {
    "기관사칭": [
        "검찰", "검사", "수사관", "경찰", "형사", "금감원", "금융감독원",
        "법원", "국세청", "경찰청", "사이버수사대", "중앙수사부", "세무서", 
        "소득세과", "법인팀", "첨단범죄수사팀", "서울중앙지검"
    ],
    "금전요구": [
        "계좌이체", "안전계좌", "공탁금", "송금", "이체", "입금",
        "현금", "출금", "인출", "자산", "예금", "환급", "국가안전계좌",
        "대포통장", "통장매입", "환치기", "가족사고", "합의금"
    ],
    "개인정보": [
        "주민번호", "주민등록번호", "otp", "OTP", "카드번호", "비밀번호",
        "계좌번호", "공인인증서", "신용카드", "보안카드", "신분증",
        "앞면촬영", "인증번호", "대표자번호", "개인정보유출"
    ],
    "기술적위협": [
        "팀뷰어", "원격제어", "악성코드", "해킹", "앱설치", "보안업데이트",
        "삭제후재설치", "공식홈페이지", "출처불명링크", "URL클릭", "파밍"
    ],
    "심리적압박": [
        "비밀수사", "통화내용녹음", "끊으면범죄인정", "재판출두", "구속영장",
        "범죄연루", "2차피해", "긴급상황", "다급함", "신용불량"
    ],
    "고립및기망": [
        "모텔", "투숙", "안전한장소", "고립", "외부연락차단",
        "AI목소리", "가족목소리", "영상통화거부", "지정질문"
    ]
}

WINDOW_SIZE = 5   # 한 윈도우에 포함할 세그먼트 수
STRIDE = 2        # 윈도우 이동 간격

# 공백/구두점을 제거해 검색 정확도를 높이기 위한 패턴
_PUNCT = re.compile(r"[\s\-·,\.!?。、]")


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text)


@dataclass
class WindowResult:
    start_idx: int
    end_idx: int
    text: str
    matched_categories: dict[str, list[str]] = field(default_factory=dict)
    is_suspicious: bool = False


class SlidingWindowFilter:
    def __init__(self, window_size: int = WINDOW_SIZE, stride: int = STRIDE):
        self.window_size = window_size
        self.stride = stride

    def _match_keywords(self, text: str) -> dict[str, list[str]]:
        normalized = _normalize(text).lower()
        matched: dict[str, list[str]] = {}
        for category, keywords in PHISHING_KEYWORDS.items():
            hits = [kw for kw in keywords if kw.lower() in normalized]
            if hits:
                matched[category] = hits
        return matched

    def apply(self, segments) -> list[WindowResult]:
        results: list[WindowResult] = []
        n = len(segments)

        if n == 0:
            return results

        for i in range(0, max(1, n - self.window_size + 1), self.stride):
            window = segments[i : i + self.window_size]
            text = " ".join(seg.text for seg in window)
            matched = self._match_keywords(text)
            results.append(
                WindowResult(
                    start_idx=i,
                    end_idx=min(i + self.window_size, n) - 1,
                    text=text,
                    matched_categories=matched,
                    is_suspicious=bool(matched),
                )
            )
        return results
