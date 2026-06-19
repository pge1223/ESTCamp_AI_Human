/** 첫 장면(오프닝) 생성 API — 언제든 삭제 가능한 독립 모듈 */
import { API_BASE_URL } from './apiBase';

export async function generateOpeningScene(chatId) {
  const res = await fetch(`${API_BASE_URL}/chats/${chatId}/opening`);
  if (!res.ok) return '';
  const data = await res.json();
  return data.narration || '';
}
