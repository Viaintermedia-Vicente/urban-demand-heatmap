import { fetchJson } from "./client";

export interface EventSummary {
  title: string;
  category: string;
  start_dt: string;
  end_dt?: string | null;
  venue_name?: string | null;
  expected_attendance?: number | null;
  lat?: number | null;
  lon?: number | null;
  url?: string | null;
  source?: string | null;
  city?: string | null;
  address?: string | null;
  organizer?: string | null;
  price?: string | null;
  description?: string | null;
}

interface FetchEventsParams {
  date: string;
  fromHour: number;
  city?: string | null;
  signal?: AbortSignal;
}

export async function fetchEvents({ date, fromHour, city, signal }: FetchEventsParams) {
  const search = new URLSearchParams({
    date,
    from_hour: String(fromHour),
  });
  if (city) {
    search.set("city", city);
  }
  return fetchJson<EventSummary[]>(`/events?${search.toString()}`, { signal });
}
