// Thin API client. All calls go to /api/v1 on this origin (proxied to FastAPI), with the session cookie.

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
};

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const init: RequestInit = {
    method: opts.method || (opts.body || opts.form ? "POST" : "GET"),
    credentials: "include",
    signal: opts.signal,
    headers: {},
  };
  if (opts.form) {
    init.body = opts.form;
  } else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    (init.headers as Record<string, string>)["content-type"] = "application/json";
  }
  const res = await fetch(`/api/v1${path}`, init);
  const text = await res.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(res.status, err?.code || "http_error", err?.message || res.statusText || "Request failed", err?.details);
  }
  return data as T;
}

export const fetcher = (path: string) => api(path);

export type SSEEvent = { event: string; data: any };

/** POST and read a server-sent-event stream (EventSource can't POST). */
export async function streamPost(path: string, body: unknown, onEvent: (e: SSEEvent) => void): Promise<void> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json", accept: "text/event-stream" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    let msg = "Request failed";
    try {
      msg = (await res.json())?.error?.message || msg;
    } catch {}
    throw new ApiError(res.status, "stream_error", msg);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.search(/\r?\n\r?\n/)) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx).replace(/^\r?\n\r?\n/, "");
      let event = "message";
      const dataLines: string[] = [];
      for (const line of chunk.split(/\r?\n/)) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
      }
      if (dataLines.length) {
        try {
          onEvent({ event, data: JSON.parse(dataLines.join("\n")) });
        } catch {
          onEvent({ event, data: dataLines.join("\n") });
        }
      }
    }
  }
}

export function formatDate(iso?: string | null, opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" }) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString(undefined, opts);
}

export function timeAgo(iso?: string | null) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return formatDate(iso);
}
