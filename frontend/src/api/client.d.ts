export declare function fetchJson<T>(path: string, init?: RequestInit & {
    signal?: AbortSignal;
}): Promise<T>;
