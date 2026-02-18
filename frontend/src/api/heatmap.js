import { fetchJson } from "./client";
export async function fetchHeatmap({ date, hour, mode, lat, lon, signal }) {
    const search = new URLSearchParams({
        date,
        hour: String(hour),
        mode,
    });
    if (typeof lat === "number" && typeof lon === "number") {
        search.set("lat", lat.toString());
        search.set("lon", lon.toString());
    }
    return fetchJson(`/heatmap?${search.toString()}`, { signal });
}
