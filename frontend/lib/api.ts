const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/signals";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** Origin (scheme+host) of the backend's WS listener, derived from NEXT_PUBLIC_WS_URL. */
export function wsOrigin(): string {
  try {
    const u = new URL(WS_URL);
    return `${u.protocol}//${u.host}`;
  } catch {
    return "ws://localhost:8000";
  }
}

export function jobWsUrl(jobId: string): string {
  return `${wsOrigin()}/ws/jobs/${jobId}`;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  opts: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, headers, ...rest } = opts;
  const res = await fetch(apiUrl(path), {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
