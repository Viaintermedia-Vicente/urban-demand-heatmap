import { fetchJson } from "./client";
export async function fetchEvents({ date, fromHour, signal }) {
    const search = new URLSearchParams({
        date,
        from_hour: String(fromHour),
    });
    return fetchJson(`/events?${search.toString()}`, { signal });
}
