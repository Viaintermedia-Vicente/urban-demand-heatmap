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
export declare function fetchEvents({ date, fromHour, signal }: FetchEventsParams): Promise<EventSummary[]>;
export {};
