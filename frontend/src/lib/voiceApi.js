import { API_BASE_URL } from './apiBase';
import { authClient } from './auth';

async function getCurrentUserId() {
  const session = await authClient.getSession();
  return session.data?.user?.id || null;
}

export async function saveVoiceProfile({ userSamples, guideAnswers, optionalContext }) {
  const userId = await getCurrentUserId();
  if (!userId) throw new Error('로그인이 필요합니다.');

  const res = await fetch(`${API_BASE_URL}/users/${userId}/voice-profile`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_samples: userSamples,
      guide_answers: guideAnswers,
      optional_context: optionalContext,
    }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '말투 프로파일 저장 실패');
  }

  return res.json();
}

export async function getVoiceProfile() {
  const userId = await getCurrentUserId();
  if (!userId) return null;

  const res = await fetch(`${API_BASE_URL}/users/${userId}/voice-profile`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.voice_profile;
}
