# 개발 로그

## 2026.05.07 pge

- STT 교체 (Whisper → Android SpeechRecognizer)
  - `whisper_flutter_new` 의존성 제거, `speech_to_text` 패키지로 대체
  - `CallScreen` SpeechRecognizer 기반으로 재작성, 실시간 마이크 입력 지원
  - `LiveScreen` 마이크 직접 테스트 버튼 추가

- Android 빌드 설정
  - `ndk abiFilters` arm64-v8a 고정
  - `tensorflow-lite-select-tf-ops 2.14.0` 추가
  - `RECORD_AUDIO` 권한 추가
  - `foojay-resolver-convention` 플러그인 추가

- TFLite 분석 서비스 개선
  - 텐서 입력 순서 수정 (attention_mask → input_ids → token_type_ids)
  - `Int64List` 변환 적용 (int32 오입력 버그 수정)
  - 키워드 필터 공백 정규화 ("안전 계좌" → "안전계좌" 처리)
  - `--dart-define` 기반 모델 파일 주입 방식으로 변경
