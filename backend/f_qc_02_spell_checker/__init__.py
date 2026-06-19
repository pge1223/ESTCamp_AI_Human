"""F-QC-02 한국어 맞춤법·문법 검사 독립 모듈."""
from .checker import check_korean_grammar, check_korean_grammar_status

__all__ = ["check_korean_grammar", "check_korean_grammar_status"]
