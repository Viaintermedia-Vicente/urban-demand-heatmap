const API_BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export async function fetchJson<T>(
  path: string,
  init?: RequestInit & { signal?: AbortSignal }
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
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

  return (await response.json()) as T;
}

async function safeJsonMessage(response: Response): Promise<string | undefined> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data?.detail;
  } catch {
    return undefined;
  }
}
