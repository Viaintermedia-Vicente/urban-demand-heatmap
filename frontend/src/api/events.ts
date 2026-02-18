import { fetchJson } from "./client";

export interface EventSummary {
  title: string;
  category: string;
  start_dt: string;
  venue_name?: string | null;
  expected_attendance?: number | null;
}

interface FetchEventsParams {
  date: string;
  fromHour: number;
  signal?: AbortSignal;
}

export async function fetchEvents({ date, fromHour, signal }: FetchEventsParams) {
  const search = new URLSearchParams({
    date,
    from_hour: String(fromHour),
  });
  return fetchJson<EventSummary[]>(`/events?${search.toString()}`, { signal });
}
