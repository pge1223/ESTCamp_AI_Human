import { API_BASE_URL } from './apiBase';

export async function getDashboard(startDate, endDate) {
    const response = await fetch(
        `${API_BASE_URL}/api-logs/dashboard?start_date=${startDate}&end_date=${endDate}`,
        {
            method: "GET",
            headers: {
                "Content-Type": "application/json",
            },
        }
    );

    return response.json();
}