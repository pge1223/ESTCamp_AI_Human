import { API_BASE_URL } from './apiBase';

const BASE = `${API_BASE_URL}/mypage`;

export async function getProfile(userId) {
    const res = await fetch(`${BASE}/profile?user_id=${userId}`);
    if (!res.ok) throw new Error('프로필 조회 실패');
    return res.json();
}

export async function getWorks(userId) {
    const res = await fetch(`${BASE}/works?user_id=${userId}`);
    if (!res.ok) throw new Error('작품 목록 조회 실패');
    return res.json();
}

export async function getWorkDetail(userId, sessionId) {
    const res = await fetch(`${BASE}/works/${sessionId}?user_id=${userId}`);
    if (!res.ok) throw new Error('작품 상세 조회 실패');
    return res.json();
}

export async function getWiki(userId, sessionId) {
    const res = await fetch(`${BASE}/works/${sessionId}/wiki?user_id=${userId}`);
    if (!res.ok) throw new Error('설정집 조회 실패');
    return res.json();
}

// 등장인물 관계도 — 사용자가 직접 입력한 관계 저장. relations=[{from, to, label}]
export async function saveRelations(userId, sessionId, relations) {
    const res = await fetch(`${BASE}/works/${sessionId}/relations?user_id=${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(relations),
    });
    if (!res.ok) throw new Error('관계도 저장 실패');
    return res.json();
}

export async function getRecent(userId) {
    const res = await fetch(`${BASE}/recent?user_id=${userId}`);
    if (!res.ok) throw new Error('최근 작업 조회 실패');
    return res.json();
}

export async function getSentences(userId) {
    const res = await fetch(`${BASE}/sentences?user_id=${userId}`);
    if (!res.ok) throw new Error('문장 보관함 조회 실패');
    return res.json();
}

export async function saveSentence({ userId, content, label, sessionId }) {
    const res = await fetch(`${BASE}/sentences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, content, label, session_id: sessionId }),
    });
    if (!res.ok) throw new Error('문장 저장 실패');
    return res.json();
}

export async function deleteSentence(userId, sentenceId) {
    const res = await fetch(`${BASE}/sentences/${sentenceId}?user_id=${userId}`, {
        method: 'DELETE',
    });
    if (!res.ok) throw new Error('문장 삭제 실패');
}

export async function getAuthorRecords(userId) {
    const res = await fetch(`${BASE}/author-records?user_id=${userId}`);
    if (!res.ok) throw new Error('AI 작가 기록 조회 실패');
    return res.json();
}

export async function getAchievements(userId) {
    const res = await fetch(`${BASE}/achievements?user_id=${userId}`);
    if (!res.ok) throw new Error('업적 조회 실패');
    return res.json();
}

export async function getStats(userId) {
    const res = await fetch(`${BASE}/stats?user_id=${userId}`);
    if (!res.ok) throw new Error('창작 통계 조회 실패');
    return res.json();
}

// 오답노트 — 자주 틀린 맞춤법(error_profile) 자주 틀리는 순. /mypage 아닌 /users 경로.
export async function getErrorNotebook(userId) {
    const res = await fetch(`${API_BASE_URL}/users/${userId}/error-notebook`);
    if (!res.ok) return [];   // 404(유저 없음) 등은 빈 노트로
    const data = await res.json();
    return data.notebook ?? [];
}

// 오답노트 항목 1개 삭제 → 갱신된 노트 반환
export async function deleteErrorNotebookEntry(userId, original) {
    const res = await fetch(`${API_BASE_URL}/users/${userId}/error-notebook`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ original }),
    });
    if (!res.ok) throw new Error('삭제 실패');
    const data = await res.json();
    return data.notebook ?? [];
}

export async function getDashboard(userId) {
    const res = await fetch(`${BASE}/dashboard?user_id=${userId}`);
    if (!res.ok) throw new Error('대시보드 조회 실패');
    return res.json();
}

export async function getTasteProfile(userId) {
    const res = await fetch(`${BASE}/taste?user_id=${userId}`);
    if (!res.ok) return { selected_works: [], taste_profile: {} };
    return res.json();
}

export async function setupTasteProfile(userId, selectedWorks) {
    const res = await fetch(`${BASE}/taste/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, selected_works: selectedWorks }),
    });
    if (!res.ok) throw new Error('취향 분석 실패');
    return res.json();
}
