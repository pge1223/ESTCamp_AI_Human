import { API_BASE_URL } from './apiBase';

async function fetchFallback(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error('fallback 로드 실패');
  return res.json();
}

export async function getAuthors() {
  try {
    const response = await fetch(`${API_BASE_URL}/authors/`);
    if (!response.ok) throw new Error();
    return response.json();
  } catch {
    return fetchFallback('/data/authors.json');
  }
}

export async function getAuthor(authorId) {
  try {
    const response = await fetch(`${API_BASE_URL}/authors/${authorId}`);
    if (!response.ok) throw new Error();
    return response.json();
  } catch {
    const authors = await fetchFallback('/data/authors.json');
    const author = authors.find((a) => String(a.id) === String(authorId));
    if (!author) throw new Error('작가를 찾을 수 없습니다.');
    return author;
  }
}

export async function getQuestions(authorId) {
  try {
    const response = await fetch(`${API_BASE_URL}/authors/${authorId}/questions`);
    if (!response.ok) throw new Error();
    return response.json();
  } catch {
    const data = await fetchFallback('/data/questions.json');
    const questions = data[String(authorId)];
    if (!questions) throw new Error('질문을 찾을 수 없습니다.');
    return questions;
  }
}
