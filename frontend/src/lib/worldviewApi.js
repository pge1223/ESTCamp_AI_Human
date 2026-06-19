import { API_BASE_URL } from './apiBase';
import { authClient } from './auth';

async function getCurrentUserId() {
  const session = await authClient.getSession();
  return session.data?.user?.id || null;
}

// 테스트용 더미 user_id (인증 구현 전까지 고정)
// PostgreSQL users 테이블에 이 UUID 행이 존재해야 World FK 통과
const DUMMY_USER_ID = "00000000-0000-0000-0000-000000000001";

/**
 * 세계관 + 캐릭터 일괄 저장
 * @param {{ world: object, characters: object[] }} payload
 * @returns {Promise<string>} 생성된 world_id (UUID)
 */
export async function createWorldview({ world, characters, authorId }) {
  const userId = await getCurrentUserId();

  // 1. 세계관 생성
  const worldRes = await fetch(`${API_BASE_URL}/worlds/?user_id=${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(world),
  });
  if (!worldRes.ok) {
    const err = await worldRes.json().catch(() => ({}));
    throw new Error(err.detail || "세계관 생성 실패");
  }
  const { id: worldId } = await worldRes.json();

  // 2. 캐릭터 생성 (병렬) — 응답이 입력 순서대로 보존되므로 protagonist_id 추적 가능
  const created = await Promise.all(
    characters.map(async (char) => {
      const charRes = await fetch(`${API_BASE_URL}/worlds/${worldId}/characters/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          name: char.name,
          role: char.role,
          personality: char.personality,
          prompt: char.system_prompt,
          address_rules: (char.address_rules || []).filter(r => r.target_name && r.address),
          is_ai_controlled: true,
        }),
      });
      if (!charRes.ok) {
        const err = await charRes.json().catch(() => ({}));
        throw new Error(err.detail || `캐릭터 '${char.name}' 생성 실패`);
      }
      return { char, data: await charRes.json() };
    })
  );

  // 입력 순서상 첫 protagonist를 주인공으로
  const protagonistId =
    created.find(({ char }) => char.role === 'protagonist')?.data.id ?? null;

  if (!protagonistId) throw new Error("주인공(protagonist) 캐릭터를 1명 이상 등록해 주세요.");

  // 3. 세션 생성 — world_id + user_id + protagonist_id 연결
  const sessionRes = await fetch(`${API_BASE_URL}/sessions/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      world_id: worldId,
      user_id: userId,
      protagonist_id: protagonistId,
      author_id: authorId ?? null,
    }),
  });
  if (!sessionRes.ok) {
    const err = await sessionRes.json().catch(() => ({}));
    throw new Error(err.detail || "세션 생성 실패");
  }
  const { id: sessionId } = await sessionRes.json();

  return { worldId, sessionId };
}

/**
 * 세션 단건 조회 — world_id 등 세션 메타 확인용
 * @param {string} sessionId
 * @returns {Promise<object>} SessionResponse
 */
export async function getSession(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
  if (!res.ok) throw new Error('세션 조회 실패');
  return res.json();
}

/**
 * 세션 목록 조회 (소설 목록 페이지용)
 * @returns {Promise<object[]>} SessionListItem[]
 */
export async function getSessions() {
  const userId = await getCurrentUserId();
  // 인증이 아직 안 잡혔으면 user_id=null 로 조회돼 422 → '작품 없음' 오인. 명확히 에러로 던져 재시도시킨다.
  if (!userId) throw new Error('로그인 정보를 불러오는 중입니다.');

  const res = await fetch(`${API_BASE_URL}/sessions/?user_id=${userId}`);
  if (!res.ok) throw new Error('세션 목록 조회 실패');
  return res.json();
}

/**
 * 세계관 단건 조회
 * @param {string} worldId
 * @returns {Promise<object>} WorldResponse
 */
export async function getWorld(worldId) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}`);
  if (!res.ok) throw new Error('세계관 조회 실패');
  return res.json();
}

/**
 * 세계관에 속한 캐릭터 목록 조회
 * @param {string} worldId
 * @returns {Promise<object[]>} CharacterResponse[]
 */
export async function getCharacters(worldId) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}/characters/`);
  if (!res.ok) throw new Error('캐릭터 조회 실패');
  return res.json();
}

/**
 * 세계관 수정 (부분 업데이트 — 보낸 필드만 반영)
 * @param {string} worldId
 * @param {{title?:string, description?:string, genre?:string, setting?:string, rules?:string}} patch
 * @returns {Promise<object>} WorldResponse
 */
export async function updateWorld(worldId, patch) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '세계관 수정 실패');
  }
  return res.json();
}

/**
 * 추리 설정 — 숨겨진 사실 LLM 자동 생성 (차로운 전용)
 * @param {string} worldId
 */
export async function generateHiddenFacts(worldId) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}/hidden-facts/generate`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '숨겨진 사실 생성 실패');
  }
  return res.json();
}

/**
 * 캐릭터 추가 (수정 화면에서 신규 인물 등록)
 * @param {string} worldId
 * @param {{name:string, role:string, personality?:string, prompt?:string}} char
 * @returns {Promise<object>} CharacterResponse
 */
export async function createCharacter(worldId, char) {
  const userId = await getCurrentUserId();
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}/characters/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      name: char.name,
      role: char.role,
      personality: char.personality ?? '',
      prompt: char.prompt ?? '',
      is_ai_controlled: true,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `캐릭터 '${char.name}' 추가 실패`);
  }
  return res.json();
}

/**
 * 캐릭터 수정 (부분 업데이트 — 이름 변경은 호출부에서 정책상 제한)
 * @param {string} worldId
 * @param {string} characterId
 * @param {{name?:string, role?:string, personality?:string, prompt?:string}} patch
 * @returns {Promise<object>} CharacterResponse
 */
export async function updateCharacter(worldId, characterId, patch) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}/characters/${characterId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '캐릭터 수정 실패');
  }
  return res.json();
}

/**
 * 캐릭터 삭제 (수정 화면에서 신규 인물 취소용)
 * @param {string} worldId
 * @param {string} characterId
 */
export async function deleteCharacter(worldId, characterId) {
  const res = await fetch(`${API_BASE_URL}/worlds/${worldId}/characters/${characterId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '캐릭터 삭제 실패');
  }
}

/**
 * 세션 삭제
 * @param {string} sessionId
 */
export async function deleteSession(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(`세션 삭제 실패 (${res.status}): ${body.detail ?? res.statusText}`);
  }
}

/**
 * 세션의 대화 이력 조회 (이어쓰기 복원용)
 * @param {string} sessionId
 * @returns {Promise<object[]>} DialogueResponse[]
 */
export async function getDialogues(sessionId) {
  const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}/dialogues/`);
  if (!res.ok) throw new Error('대화 이력 조회 실패');
  return res.json();
}
