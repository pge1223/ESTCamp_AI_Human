# 에뮬레이터에서 TFLite float32 모델 실행하기

실기기(폰)는 float16 모델을 사용하지만, x86_64 에뮬레이터는 float16 CPU 연산을 지원하지 않아 float32 모델이 필요합니다.
float32 모델은 용량이 커서 git에 포함되지 않으며, 아래 절차로 에뮬레이터에 직접 배치합니다.

## 사전 준비

- Android 에뮬레이터 실행 중
- `model_float32.tflite` 파일 보유 (Google Drive 공유 링크 참고)

## 절차 (최초 1회)

**1. 디렉토리 생성**

```cmd
C:\Users\<사용자명>\AppData\Local\Android\sdk\platform-tools\adb.exe shell mkdir -p /sdcard/Android/data/com.voiceguard.app/files
```

**2. 모델 파일을 에뮬레이터 내부 저장소에 복사**

adb가 PATH에 등록된 경우:
```cmd
adb push <model_float32.tflite 로컬 경로> /sdcard/Android/data/com.voiceguard.app/files/model_float32.tflite
```

adb가 PATH에 없는 경우 (전체 경로 사용):
```cmd
C:\Users\<사용자명>\AppData\Local\Android\sdk\platform-tools\adb.exe push <model_float32.tflite 로컬 경로> /sdcard/Android/data/com.voiceguard.app/files/model_float32.tflite
```

**3. 파일 확인**

```cmd
C:\Users\<사용자명>\AppData\Local\Android\sdk\platform-tools\adb.exe shell ls /sdcard/Android/data/com.voiceguard.app/files/
```

`model_float32.tflite` 가 보이면 정상입니다.

**4. flutter run 실행**

```cmd
cd client
flutter run
```

로그에서 아래 메시지가 나오면 정상:
```
[Analyzer] float16 미지원: ...
[Analyzer] 모델 로드 성공 (float32 로컬)
```

## 동작 방식

| 환경 | 로드 순서 |
|------|----------|
| 실기기 (폰) | float16 asset → 성공 시 사용 |
| 에뮬레이터 | float16 실패 → float32 로컬 파일 → 없으면 키워드 필터만 동작 |

## 주의사항

- 에뮬레이터를 **완전히 재설치(wipe)** 하면 파일이 삭제되므로 adb push를 다시 해야 합니다.
- flutter run / hot restart 시에는 다시 push할 필요 없습니다.
- float32 파일은 `.gitignore`에 포함되어 있어 커밋되지 않습니다.
