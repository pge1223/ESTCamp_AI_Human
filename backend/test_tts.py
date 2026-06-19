import httpx
import json
import base64
import time
import uuid

BASE = "http://localhost:8000/api/v1/chats"

def test_tts(persona_id: str, content: str):
    session_id = f"test-tts-{persona_id}-{uuid.uuid4().hex[:8]}"

    r = httpx.post(f"{BASE}/{session_id}/messages", json={
        "content": content,
        "character_id": persona_id,
        "mode": "author",
    })
    print(f"메시지 전송: {r.status_code}")

    audio_b64 = None  # ← 여기서 미리 선언

    # timeout=30 → timeout=60으로 변경
    with httpx.stream("GET", f"{BASE}/{session_id}/stream", params={
        "content": content,
        "character_id": persona_id,
        "mode": "author",
    }, timeout=60) as resp:
        for line in resp.iter_lines():
            if line.startswith("event:"):
                print(f"이벤트: {line}")
            if line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    if "audio" in data:
                        audio_b64 = data["audio"]  # ← 저장
                        print(f"✅ audio 필드 있음! 길이: {len(audio_b64)}자")
                    if "narration" in data:
                        print(f"narration: {data['narration'][:50]}")
                except:
                    pass

    # with 블록 끝난 후 저장
    if audio_b64:
        audio_bytes = base64.b64decode(audio_b64)
        with open("output.mp3", "wb") as f:
            f.write(audio_bytes)
        print("✅ output.mp3 저장 완료!")

if __name__ == "__main__":
    test_tts("baekya", "비가 오는 밤, 카페에서 우연히 마주쳤다.")