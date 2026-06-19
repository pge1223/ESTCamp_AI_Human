"""
F-QC-02: 한국어 맞춤법·문법 검사 독립 모듈

사용:
    from f_qc_02_spell_checker import check_korean_grammar

    corrected = check_korean_grammar("이거슨 테스트 문장 임니다.")

로컬 테스트:
    python -m f_qc_02_spell_checker.checker
"""
from __future__ import annotations

import html
import json
import logging
import re
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SPELLER_URL = "https://m.search.naver.com/p/csearch/ocontent/util/SpellerProxy"
_PASSPORT_KEY_PAGE = (
    "https://search.naver.com/search.naver"
    "?where=nexearch&sm=top_sug.pre&fbm=0&acr=1"
    "&acq=%EB%A7%9E%EC%B6%94&qdt=0&ie=utf8&query=%EB%A7%9E%EC%B6%A4%EB%B2%95%EA%B2%80%EC%82%AC%EA%B8%B0"
)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://search.naver.com/",
}
_MAX_LENGTH = 500
_TIMEOUT_SEC = 10

_passport_key: Optional[str] = None


def _extract_passport_key() -> Optional[str]:
    """네이버 맞춤법 검사 페이지에서 passportKey를 추출."""
    try:
        response = requests.get(
            _PASSPORT_KEY_PAGE,
            headers=_HEADERS,
            timeout=_TIMEOUT_SEC,
        )
        response.raise_for_status()
        match = re.search(r"passportKey=([a-f0-9]+)", response.text)
        return match.group(1) if match else None
    except requests.RequestException as exc:
        logger.warning("passportKey 추출 실패: %s", exc)
        return None


def _get_passport_key(refresh: bool = False) -> Optional[str]:
    global _passport_key
    if refresh or not _passport_key:
        _passport_key = _extract_passport_key()
    return _passport_key


def _parse_speller_response(response_text: str) -> str:
    """JSONP 응답에서 교정문(notag_html) 추출."""
    match = re.search(r"jQuery\d+_\d+\((\{.*\})\);", response_text, re.DOTALL)
    if not match:
        start = response_text.find("({")
        end = response_text.rfind("})")
        if start == -1 or end == -1:
            raise ValueError("맞춤법 API 응답 형식 오류")
        payload = response_text[start + 1 : end + 1]
    else:
        payload = match.group(1)

    data = json.loads(payload)
    message = data.get("message", {})
    if "error" in message:
        raise ValueError(message["error"])
    result = message.get("result")
    if not result:
        raise ValueError("맞춤법 검사 결과 없음")

    corrected = result.get("notag_html") or result.get("html", "")
    corrected = re.sub(r"<[^>]+>", "", corrected)
    corrected = html.unescape(corrected)  # &quot; &amp; 등 HTML 엔티티 복원
    return corrected.strip()


def _call_speller_api(text: str, passport_key: str) -> str:
    params = {
        "passportKey": passport_key,
        "_callback": "jQuery11240248871280810548_1736152095925",
        "q": text,
        "where": "nexearch",
        "color_blindness": 0,
    }
    response = requests.get(
        _SPELLER_URL,
        params=params,
        headers=_HEADERS,
        timeout=_TIMEOUT_SEC,
    )
    response.raise_for_status()
    return _parse_speller_response(response.text)


def check_korean_grammar_status(text: str) -> tuple[str, bool]:
    """한국어 맞춤법을 검사해 **(교정문, 검사기 동작여부 ok)** 를 반환.

    - ok=False = **검사기 자체가 못 돎**(passportKey 추출 실패=네이버 페이지 변경/차단,
      또는 API/파싱 최종 실패). → 원문 그대로 + "검사 안 됨"을 호출부가 알 수 있다.
    - ok=True  = 정상 검사(교정문). 빈 입력·500자 초과 skip은 '실패는 아니므로' True.
    - **fail-open**: 어떤 경우든 교정문 자리엔 항상 원문을 반환(서비스 중단 방지).
    """
    if not text or not text.strip():
        return text, True

    if len(text) > _MAX_LENGTH:
        logger.warning("맞춤법 검사: %d자 — 상한 %d자, 원문 반환", len(text), _MAX_LENGTH)
        return text, True

    passport_key = _get_passport_key()
    if not passport_key:
        logger.warning("맞춤법 검사: passportKey 없음 — 검사기 동작 실패(원문 반환)")
        return text, False

    try:
        return _call_speller_api(text, passport_key), True
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        logger.warning("맞춤법 검사 1차 실패 (%s) — key 갱신 후 재시도", exc)

    passport_key = _get_passport_key(refresh=True)
    if not passport_key:
        logger.warning("맞춤법 검사: key 갱신 실패 — 검사기 동작 실패(원문 반환)")
        return text, False

    try:
        return _call_speller_api(text, passport_key), True
    except (requests.RequestException, ValueError, json.JSONDecodeError) as exc:
        logger.warning("맞춤법 검사 최종 실패 (%s) — 검사기 동작 실패(원문 반환)", exc)
        return text, False


def check_korean_grammar(text: str) -> str:
    """교정문만 반환(하위호환 래퍼). 실패 시 원문(fail-open)."""
    return check_korean_grammar_status(text)[0]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    samples = [
        "이거슨 팀원들이 시키는 마춤법 검사기 테스트 문장 임니다.",
        "아버지가방에들어가신다.",
        "오늘 날씨가 참 좋네요. 산책하기 딱 좋을 것 같아요.",
    ]

    print("=== F-QC-02 맞춤법 검사 테스트 ===\n")
    for sentence in samples:
        corrected = check_korean_grammar(sentence)
        print("[원본]", sentence)
        print("[교정]", corrected)
        print()
