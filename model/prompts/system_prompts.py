"""[더 이상 사용하지 않음 — DEPRECATED]

런타임 프롬프트는 backend/app/core/personas.py 한 곳에서 관리합니다.
  - 1-1 세계관 advisory : build_world_prompt()
  - 1-2 대화            : get_author_prompt()
  - 1-3 초안(소설 변환)  : NOVEL_SYSTEM / build_novel_system()

프롬프트 설계 문서: docs/프롬프트_설계.md

이 model/prompts/ 디렉터리는 학습/실험용 프롬프트 보관 용도로만 사용하세요.
(기존 build_system_prompt 는 `app.core.personas.PERSONAS` 깨진 참조였어서 제거됨)
"""
