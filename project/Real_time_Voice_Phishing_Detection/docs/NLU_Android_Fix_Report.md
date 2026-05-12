# Android 온디바이스 NLU 추론 수정 리포트

> 작성일: 2026-05-07
> 대상 파일: `client/lib/services/phishing_analyzer_service.dart`
> 모델: `assets/model_int8_no_erf.tflite` (KoELECTRA int8 양자화)
> 라이브러리: `tflite_flutter: ^0.12.1`

---

## 1. 최초 증상

실기기(Samsung S918N, Android) 테스트에서 위험 퍼센티지가 **최대 13~16%** 에서 멈추고 오르지 않음.

로그:
```
[Analyzer] keywordScore=40, isReady=true
[Analyzer] 추론 오류: Bad state: failed precondition
[UI] keyword=40 risk=13% triggered=false labels=[]
```

`triggered=false` 상태에서는 BERT 추론 결과 대신 키워드 점수 기반의 최대 30% 상한 로직만 작동함:
```dart
// PhishingResult.riskPercent
if (!triggered) return (keywordScore / 3).clamp(0, 30).toInt();
return (maxProb * 100).toInt();
```

---

## 2. 문제 1: TFLite 추론 실패 (`Bad state: failed precondition`)

### 원인 분석

스택트레이스:
```
#0  checkState (package:quiver/check.dart:74:5)
#1  Interpreter.invoke (package:tflite_flutter/src/interpreter.dart:164:5)
#2  Interpreter.runInference (package:tflite_flutter/src/interpreter.dart:214:5)
#3  Interpreter.runForMultipleInputs (...)
#4  PhishingAnalyzerService._runInference (...)
```

네이티브 TFLite 로그:
```
E/tflite: tflite/kernels/gather.cc:160 indices_has_only_positive_elements was not true.
E/tflite: gather index out of bounds
E/tflite: Node number 9 (GATHER) failed to invoke.
```

**GATHER op (임베딩 룩업) 에서 인덱스 범위 초과 발생.**

### 근본 원인: `tflite_flutter 0.12.x` int64 Big Endian 버그

`tflite_flutter/src/util/byte_conversion_utils.dart` 내부:

```dart
// Int64 변환 코드 (버그 있음)
if (tensorType.value == TfLiteType.kTfLiteInt64) {
  if (o is int) {
    var buffer = Uint8List(8).buffer;
    var bdata = ByteData.view(buffer);
    bdata.setInt64(0, o, Endian.big);  // ← Big Endian! 잘못됨
    return buffer.asUint8List();
  }
}
```

ARM/x86 아키텍처는 **Little Endian**이므로, int64 토큰 ID가 바이트 순서 역전되어 전달됨.

예시:
- 토큰 ID `1001` (0x00000000000003E9)
- Big Endian 저장: `00 00 00 00 00 00 03 E9`
- TFLite가 Little Endian으로 읽으면: `0xE903000000000000` = 약 16경 → 임베딩 테이블 범위 초과

### 수정 방법

`List<Int64List>` 대신 **직접 Little Endian으로 인코딩한 `Uint8List`** 를 전달.

`tflite_flutter`의 `setTo(Uint8List)` 경로는 변환 없이 바이트를 그대로 사용:
```dart
// byte_conversion_utils.dart
static Uint8List convertObjectToBytes(Object o, TensorType tensorType) {
  if (o is Uint8List) return o;  // ← 변환 없이 즉시 반환
  ...
}
```

```dart
// 수정된 _runInference()
List<double> _runInference(String text) {
  final inputIds = _tokenize(text);
  final attentionMask = inputIds.map((id) => id != _padId ? 1 : 0).toList();
  final tokenTypeIds = List.filled(_maxLength, 0);

  // int64 → Uint8List (Little Endian) 직접 변환
  Uint8List toInt64LE(List<int> values) {
    final bd = ByteData(values.length * 8);
    for (int i = 0; i < values.length; i++) {
      bd.setInt64(i * 8, values[i], Endian.little);  // ← Little Endian
    }
    return bd.buffer.asUint8List();
  }

  _interpreter!.allocateTensors();

  final output = [List.filled(3, 0.0)];
  _interpreter!.runForMultipleInputs(
    [toInt64LE(attentionMask), toInt64LE(inputIds), toInt64LE(tokenTypeIds)],
    {0: output},
  );

  return output[0].map((logit) => 1.0 / (1.0 + math.exp(-logit))).toList();
}
```

### 수정 후 로그
```
[Analyzer] 추론 완료 → probs=[1.00, 0.01, 0.02]
[UI] keyword=50 risk=99% triggered=true labels=[기관사칭]
```

---

## 3. 문제 2: 빌드 시 모델 파일 미지정

### 원인

`_modelFile`이 `--dart-define`으로 주입되는 환경변수로 정의됨:

```dart
static const _modelFile = String.fromEnvironment(
  'MODEL_FILE',
  defaultValue: 'model_dynamic_range_quant.tflite',  // 존재하지 않는 파일
);
```

`--dart-define` 없이 빌드하면 기본값 `model_dynamic_range_quant.tflite` 사용 → 로드 실패 → `isReady=false`.

### 수정 방법

빌드 명령에 반드시 `--dart-define` 플래그 포함:

```bash
flutter build apk --debug \
  --target-platform android-arm64 \
  --dart-define=MODEL_FILE=model_int8_no_erf.tflite \
  --dart-define=MODEL_LABEL=int8
```

### 수정 후 로그
```
[Analyzer] 모델 로드 성공 (int8)
[Analyzer] 입력텐서[0]: serving_default_attention_mask:0 shape=[1, 128] type=int64
[Analyzer] 입력텐서[1]: serving_default_input_ids:0 shape=[1, 128] type=int64
[Analyzer] 입력텐서[2]: serving_default_token_type_ids:0 shape=[1, 128] type=int64
[Analyzer] 출력텐서[0]: StatefulPartitionedCall:0 shape=[1, 3] type=float32
[Analyzer] vocab 로드 완료: 35000개
```

---

## 4. 문제 3: 키워드 필터 사전 미동기화

### 원인

`phishing_analyzer_service.dart`의 키워드 사전이 `NLU/pipeline/filter.py`에 비해 대폭 누락됨.

| 카테고리 | Python (filter.py) | Dart (수정 전) |
|---|---|---|
| 기관사칭 | 33개 | 13개 |
| 금전요구 | 29개 | 8개 |
| 개인정보 | 24개 | 10개 |
| 기술적위협 | 17개 | 5개 |
| 심리적압박 | 16개 | 3개 |
| 고립및기망 | 9개 | **0개 (카테고리 없음)** |

**실제 피싱 통화 텍스트 예시 (탐지 실패 케이스):**
```
"명의로 되신 우리은행하고의 통장이 발견..."
→ "명의"(filter.py: 개인정보), "통장"(filter.py: 금전요구) 모두 Dart 사전에 없음
→ keywordScore=10 (계좌 단어 하나만 매칭) < threshold=15 → BERT 미실행
```

### 수정 방법

`filter.py`의 전체 키워드를 Dart 사전에 동기화. 단어 중요도에 따라 점수 부여:
- **15점**: 피싱 고유 핵심 키워드 (검찰, 명의, 구속영장 등)
- **10점**: 일반적이지만 맥락상 의심 키워드 (통장, 조사, 고립 등)

```dart
static const _keywords = <String, int>{
  // 기관사칭
  '검찰': 15, '검사': 15, '검사님': 15, '수사관': 15, '수사과': 15,
  '수사팀': 15, '사무관': 15, '조사관': 15, '지검': 15, '경찰청': 15,
  '경찰': 15, '형사': 15, '법원': 15, '국세청': 15, '사이버수사대': 15,
  '중앙수사부': 15, '세무서': 15, '서울중앙지검': 15, '공단': 15,
  '금융감독원': 15, '금감원': 15, '공문': 15, '사건조회': 15,
  '나의사건': 15, '소환': 15, '피의자': 15, '사건번호': 15,
  '녹취': 15, '제3자': 15,
  '조사': 10,

  // 금전요구
  '계좌이체': 15, '안전계좌': 15, '국가안전계좌': 15, '공탁금': 15,
  '송금': 15, '이체': 15, '입금': 15, '현금': 15, '출금': 15,
  '인출': 15, '환급': 15, '대포통장': 15, '통장매입': 15,
  '환치기': 15, '합의금': 15, '동결': 15, '양도': 15,
  '수거': 15, '봉투': 15, '대환': 15, 'FIU': 15,
  '통장': 10, '계좌': 10, '자산': 10, '예금': 10, '대출': 10,
  '카카오페이': 10, '카카오뱅크': 10, '상환': 10, '가족사고': 10,

  // 개인정보
  '주민번호': 15, '주민등록번호': 15, 'OTP': 15, '카드번호': 15,
  '비밀번호': 15, '계좌번호': 15, '공인인증서': 15, '보안카드': 15,
  '신분증': 15, '앞면촬영': 15, '인증번호': 15, '개인정보유출': 15,
  '실명인증': 15, '실명확인': 15, '본인확인': 15,
  'CVC': 15, '유효기간': 15, '카드뒷면': 15, '명의': 15,
  '신용카드': 10, '유출': 10, '앞면': 10, '비번': 10,
  '패스워드': 10, '분실': 10,

  // 기술적 위협
  '팀뷰어': 15, '원격제어': 15, '악성코드': 15, '해킹': 15,
  '앱설치': 15, '보안업데이트': 15, '삭제후재설치': 15,
  '출처불명링크': 15, 'URL클릭': 15, '파밍': 15,
  '주소창': 15, '인터넷주소': 15, '공식홈페이지': 15,
  '삭제': 10, '설치': 10, '링크': 10, '이상징후': 10,

  // 심리적 압박
  '구속영장': 15, '범죄연루': 15, '비밀수사': 15,
  '통화내용녹음': 15, '재판출두': 15, '소환장': 15,
  '연루': 10, '불법거래': 10, '금융사기': 10, '이상거래': 10,
  '보안조치': 10, '계좌보호': 10, '거래정지': 10,
  '2차피해': 10, '긴급상황': 10, '신용불량': 10,

  // 고립 및 기망 (신규)
  '외부연락차단': 15, '안전한장소': 15, '영상통화거부': 15,
  '지정질문': 15, '가족목소리': 15,
  '모텔': 10, '투숙': 10, '고립': 10,

  // 기관 관련 (일반)
  '금융권': 10, '공공기관': 10,
};
```

### 수정 후 동일 텍스트 결과
```
"명의로 되신 우리은행하고의 통장이 발견..."
→ 명의(15) + 통장(10) + 통장(10) = score=35 ≥ threshold=15 → BERT 실행
[Analyzer] 추론 완료 → probs=[0.44, 0.05, 0.99]
[UI] keyword=35 risk=98% triggered=true labels=[개인정보]
```

---

## 5. 위험도 단조 증가 보장

통화 중 슬라이딩 윈도우 특성상 키워드가 윈도우에서 벗어나면 risk %가 낮아지는 문제.

### 수정 위치

`client/lib/screens/call_screen.dart` — `_updateWarningLevel()`:

```dart
// 수정 전
setState(() {
  _warningLevel = result.warningLevel;
  _riskPercent = result.riskPercent;
});

// 수정 후: 수치는 오직 증가만 허용
setState(() {
  if (result.warningLevel > _warningLevel) _warningLevel = result.warningLevel;
  if (result.riskPercent > _riskPercent) _riskPercent = result.riskPercent;
  if (result.riskPercent > _peakRiskPercent) _peakRiskPercent = result.riskPercent;
  for (final l in result.detectedLabels) {
    if (!_detectedLabels.contains(l)) _detectedLabels.add(l);
  }
});
```

---

## 6. 최종 확인 로그 (PID 17738)

```
[Analyzer] initialize() 시작
[Analyzer] 모델 로드 성공 (int8)
[Analyzer] vocab 로드 완료: 35000개

[UI] 분석 텍스트(42단어): "...명의로 되신 우리은행... 통장이 발견..."
[Analyzer] keywordScore=35, isReady=true
[Analyzer] 추론 완료 → probs=[0.45, 0.04, 0.98]
[UI] keyword=35 risk=98% triggered=true labels=[개인정보]

[UI] 분석 텍스트(67단어): "...통장이 발견되시다가..."
[Analyzer] keywordScore=35, isReady=true
[Analyzer] 추론 완료 → probs=[0.44, 0.05, 0.99]
[UI] keyword=35 risk=98% triggered=true labels=[개인정보]
```

---

## 7. 변경 파일 요약

| 파일 | 변경 내용 |
|---|---|
| `client/lib/services/phishing_analyzer_service.dart` | int64 LE 인코딩 수정, 키워드 사전 filter.py 동기화 |
| `client/lib/screens/call_screen.dart` | 위험도 단조 증가 보장 |
| 빌드 명령 | `--dart-define=MODEL_FILE=model_int8_no_erf.tflite` 필수 추가 |

---

## 8. 알려진 제한 사항

- `tflite_flutter 0.12.x`의 int64 Big Endian 버그는 라이브러리 자체 버그로, 업스트림 수정 전까지 `Uint8List` 우회 방식 유지 필요
- 키워드 필터 threshold(`_filterThreshold = 15`)는 단일 고가치 키워드 1개로 BERT를 실행시킴. 오탐률 모니터링 권장
- `삭제`(10점), `설치`(10점), `링크`(10점) 등 일반 단어 포함 — threshold 15이상이므로 단독으로는 미발동
