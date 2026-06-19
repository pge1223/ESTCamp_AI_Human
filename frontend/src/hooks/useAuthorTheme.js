import { useEffect } from 'react';

const STORAGE_KEY = 'authorId';

/**
 * 작가 id를 받아 <html data-author="authorN"> 을 적용하고 localStorage에 저장한다.
 * CSS는 index.css의 [data-author="authorN"] 토큰을 따라가므로, 이 속성 하나로 전 화면 테마가 바뀐다.
 * 새로고침 시에도 테마가 유지되도록, 값을 알게 될 때마다 저장한다.
 *
 * @param {number|string|null|undefined} authorId
 */
export function useAuthorTheme(authorId) {
  useEffect(() => {
    if (authorId === null || authorId === undefined || authorId === '') return;
    document.documentElement.setAttribute('data-author', `author${authorId}`);
    localStorage.setItem(STORAGE_KEY, String(authorId));
  }, [authorId]);
}

/**
 * location.state ?? localStorage 순서로 authorId를 복원한다(새로고침 대비).
 * chat/read 페이지는 세션 로드 후 session.author_id(진짜 값)로 덮어쓰는 것을 권장.
 *
 * @param {number|string|null|undefined} stateAuthorId  location.state?.authorId
 * @returns {number|null}
 */
export function resolveAuthorId(stateAuthorId) {
  if (stateAuthorId !== null && stateAuthorId !== undefined && stateAuthorId !== '') {
    return Number(stateAuthorId);
  }
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) return Number(stored);
  // main.jsx가 hover 시 저장하는 'selectedTheme'(="author3") 도 fallback으로 인정
  const theme = localStorage.getItem('selectedTheme');
  const m = theme && theme.match(/author(\d+)/);
  return m ? Number(m[1]) : null;
}
