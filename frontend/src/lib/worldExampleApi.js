import { API_BASE_URL } from './apiBase';

export async function getRandomWorldExamples(authorId, count = 1) {
    const response = await fetch(
        `${API_BASE_URL}/world-examples/random/${authorId}?count=${count}`
    );

    if (!response.ok) {
        throw new Error("세계관 예시를 불러오는데 실패했습니다.");
    }

    return response.json();
}