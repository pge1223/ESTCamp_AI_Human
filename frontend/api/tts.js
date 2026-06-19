// Vercel 서버리스 함수 — 작가 리액션 음성(TTS).
// ElevenLabs 키를 Cloud Run에 못 올리는 제약 우회: 키는 여기(Vercel 서버사이드 env)에만 두고,
// 브라우저 → /api/tts → ElevenLabs 로 프록시한다. (키는 클라이언트로 절대 안 나감)
//
// Vercel 대시보드 Environment Variables 에 설정 필요(서버사이드, VITE_ 접두사 X):
//   ELEVENLABS_API_KEY_1, ELEVENLABS_API_KEY_2

// 작가(페르소나) → ElevenLabs voice_id  (backend/app/services/tts.py 와 동일)
const VOICE_MAP = {
  baekya: 'XTqHG68XyHm3iAxC18O2',
  charoun: 'x1VfcAsjwQX6oXjHOffX',
  hanyeoreum: 'DheTGeQX8ACNXdfZwHSe',
  kimdohyeon: 'icPpEDRQnftyC8bLxQht',
};

// 작가 → 사용할 API 키 env 이름 (계정 2개로 분리)
//   키1: 차로운·한여름  /  키2: 백야·김도현
const KEY_ENV_MAP = {
  baekya: 'ELEVENLABS_API_KEY_2',
  charoun: 'ELEVENLABS_API_KEY_1',
  hanyeoreum: 'ELEVENLABS_API_KEY_1',
  kimdohyeon: 'ELEVENLABS_API_KEY_2',
};

const MODEL_ID = 'eleven_multilingual_v2'; // 한국어 지원

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'POST only' });
    return;
  }

  const { text, character_id } = req.body || {};
  const persona = String(character_id || '').trim();
  const clean = String(text || '').trim().slice(0, 300); // 리액션은 짧음 — 길이 가드

  const voiceId = VOICE_MAP[persona];
  const apiKey = process.env[KEY_ENV_MAP[persona] || 'ELEVENLABS_API_KEY_1'];

  // 키/보이스/텍스트 없으면 조용히 스킵(204) → 프론트는 음성 없이 진행
  if (!clean || !voiceId || !apiKey) {
    res.status(204).end();
    return;
  }

  try {
    const r = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
      {
        method: 'POST',
        headers: { 'xi-api-key': apiKey, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: clean,
          model_id: MODEL_ID,
          voice_settings: { stability: 0.5, similarity_boost: 0.75 },
        }),
      }
    );

    if (!r.ok) {
      const detail = await r.text().catch(() => '');
      res.status(502).json({ error: 'tts_failed', status: r.status, detail: detail.slice(0, 200) });
      return;
    }

    const buf = Buffer.from(await r.arrayBuffer());
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).send(buf);
  } catch (e) {
    res.status(502).json({ error: 'tts_exception', detail: String(e).slice(0, 200) });
  }
}
