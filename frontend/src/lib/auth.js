// src/lib/auth.js
import { createAuthClient } from '@neondatabase/neon-js/auth';
import { API_BASE_URL } from './apiBase';

export const authClient = createAuthClient(
    import.meta.env.VITE_NEON_AUTH_URL
);

export async function syncCurrentUser() {
    const session = await authClient.getSession();
    const user = session.data?.user;

    if (!user) {
        return null;
    }

    const response = await fetch(`${API_BASE_URL}/users/me`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            id: user.id,
            email: user.email,
            nickname: user.name || user.email,
        }),
    });

    if (!response.ok) {
        throw new Error("사용자 동기화 실패");
    }

    return response.json();
}
