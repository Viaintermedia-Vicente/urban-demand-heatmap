const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");
const API_BASE = BASE || "/api";
export async function fetchJson(path, init) {
    const normalized = path.startsWith("/") ? path : `/${path}`;
    const response = await fetch(`${API_BASE}${normalized}`, {
        headers: {
            "Content-Type": "application/json",
            ...(init?.headers || {}),
        },
        ...init,
    });
    if (!response.ok) {
        const message = await safeJsonMessage(response);
        throw new Error(message || `Request failed with status ${response.status}`);
    }
    return (await response.json());
}
async function safeJsonMessage(response) {
    try {
        const data = (await response.json());
        return data?.detail;
    }
    catch {
        return undefined;
    }
}
