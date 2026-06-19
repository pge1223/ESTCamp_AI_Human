# F-QC-02 맞춤법·문법 검사

> 담당: 윤정 | 독립 모듈 — 다른 백엔드 코드와 분리

## 폴더 구성

| 파일 | 설명 |
|------|------|
| `checker.py` | `check_korean_grammar(text)` 함수 |
| `test_results.txt` | 로컬 테스트 결과 |
| `README.md` | 이 문서 |

## 설치

```bash
cd backend
pip install requests
```

## 사용법

```python
from f_qc_02_spell_checker import check_korean_grammar

corrected = check_korean_grammar("이거슨 테스트 문장 임니다.")
```

## 로컬 테스트

```bash
cd backend
python -m f_qc_02_spell_checker.checker
```

## 특징

- 함수 1개 (`check_korean_grammar`) — 팀 요구사항
- 네이버 맞춤법 API passportKey **자동 추출·갱신**
- API 실패 시 **원문 반환** (서비스 중단 방지)
- 한 번에 최대 **500자**
