import { fetchJson } from "./client";

export type HeatmapMode = "heuristic" | "ml";

export interface HeatmapHotspot {
  lat: number;
  lon: number;
  score: number;
  radius_m: number;
  lead_time_min_pred?: number | null;
  attendance_factor_pred?: number | null;
}

export interface HeatmapEvent {
  id?: string | number | null;
  title: string;
  category?: string | null;
  start_dt: string | null;
  end_dt?: string | null;
  venue_name?: string | null;
  lat?: number | null;
  lon?: number | null;
  url?: string | null;
  source?: string | null;
  expected_attendance?: number | null;
  score?: number | null;
  city?: string | null;
  address?: string | null;
  organizer?: string | null;
  price?: string | null;
  description?: string | null;
}

export interface HeatmapWeather {
  temperature_c?: number;
  precipitation_mm?: number;
  rain_mm?: number;
  snowfall_mm?: number;
  cloud_cover_pct?: number;
  wind_speed_kmh?: number;
  wind_gust_kmh?: number;
  humidity_pct?: number;
  pressure_hpa?: number;
  visibility_m?: number;
  weather_code?: number;
  observed_at?: string;
  source?: string;
}

export interface HeatmapResponse {
  mode: HeatmapMode;
  target: string;
  weather?: HeatmapWeather | null;
  hotspots: HeatmapHotspot[];
}

interface FetchHeatmapParams {
  date: string;
  hour: number;
  mode: HeatmapMode;
  lat?: number;
  lon?: number;
  signal?: AbortSignal;
}

export async function fetchHeatmap({ date, hour, mode, lat, lon, signal }: FetchHeatmapParams) {
  const search = new URLSearchParams({
    date,
    hour: String(hour),
    mode,
  });
  if (typeof lat === "number" && typeof lon === "number") {
    search.set("lat", lat.toString());
    search.set("lon", lon.toString());
  }
  return fetchJson<HeatmapResponse>(`/heatmap?${search.toString()}`, { signal });
}
