// 작가 리액션 음성 재생 — /api/tts(Vercel 서버리스 함수) 프록시 호출.
// 호출은 같은 오리진(/api/tts)이라 Cloud Run/CORS 무관. 키는 서버사이드(Vercel env)에만 있음.

let currentAudio = null; // 직전 리액션 음성 — 새 음성 오면 취소(겹침 방지)

/**
 * 리액션 텍스트를 작가 목소리로 재생. 실패/키없음/음성off면 조용히 무시(본 흐름 안 막음).
 * @param {string} text  리액션 한 줄
 * @param {string} characterId  작가 페르소나 id (baekya|charoun|hanyeoreum|kimdohyeon)
 */
export async function speakReaction(text, characterId) {
  const bgmVolume = Number(localStorage.getItem('reaction_video_volume') ?? 0.3);

  const clean = (text || '').trim();
  if (!clean || !characterId) return;

  try {
    const res = await fetch('/api/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: clean, character_id: characterId }),
    });
    // 204(키없음/스킵) 또는 오류면 음성 없이 진행
    if (!res.ok || res.status === 204) return;

    const blob = await res.blob();
    if (!blob.size) return;

    stopReaction(); // 직전 음성 끊고 새 것 재생
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.volume = Math.min(1, bgmVolume);
    audio.onended = audio.onerror = () => URL.revokeObjectURL(url);
    currentAudio = audio;
    // 사용자 제스처(전송 직후) 컨텍스트라 자동재생 허용됨. 막히면 조용히 무시.
    await audio.play().catch(() => { });
  } catch {
    /* 네트워크/함수 오류 → 음성 생략 */
  }
}

/** 재생 중인 리액션 음성 정지(겹침 방지·페이지 이탈 시). */
export function stopReaction() {
  if (currentAudio) {
    try { currentAudio.pause(); } catch { /* noop */ }
    currentAudio = null;
  }
}

/** narration에서 50자 내외로 자연스럽게 추출. */
export function extractFirstSentence(narration, maxChars = 50) {
  const clean = (narration || '').trim();
  if (!clean) return '';

  // 한국어 문장부호 기준으로 문장 분리
  const sentences = clean
    .split(/(?<=[.!?。！？…]|[다요죠까네군요]\.)\s*/g)
    .filter(Boolean);

  let result = '';

  for (const sentence of sentences) {
    if ((result + sentence).length <= maxChars) {
      result += sentence + ' ';
    } else {
      break;
    }
  }

  return result.trim() || sentences[0] || clean.slice(0, maxChars);
}