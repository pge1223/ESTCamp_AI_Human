import { API_BASE_URL } from './apiBase';

export async function getTaste(chatId, userId) {
  const res = await fetch(`${API_BASE_URL}/chats/${chatId}/taste?user_id=${encodeURIComponent(userId)}`);
  if (!res.ok) return { works: [], taste_profile: {} };
  return res.json();
}

export async function analyzeTaste(chatId, payload) {
  const res = await fetch(`${API_BASE_URL}/chats/${chatId}/taste/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('취향 분석 실패');
  return res.json();
}
