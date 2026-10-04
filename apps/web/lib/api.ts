// Thin API client. All calls go to /api/v1 on this origin (proxied to FastAPI), with the session cookie.

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  requestId?: string;
  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

type Options = {
  method?: string;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  /** Send an Idempotency-Key so a retried request (double click, flaky network) is processed only once.
   *  Pass a string to reuse the same key across your own retries. */
  idempotent?: boolean | string;
};

export function newIdempotencyKey() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export async function api<T = any>(path: string, opts: Options = {}): Promise<T> {
  const init: RequestInit = {
    method: opts.method || (opts.body !== undefined || opts.form ? "POST" : "GET"),
    credentials: "include",
    signal: opts.signal,
    headers: {},
  };
  if (opts.idempotent) {
    (init.headers as Record<string, string>)["idempotency-key"] = typeof opts.idempotent === "string" ? opts.idempotent : newIdempotencyKey();
  }
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
    if (res.status === 402 && typeof window !== "undefined") {
      // A plan limit was reached: the app shell offers an upgrade instead of a dead-end error.
      window.dispatchEvent(new CustomEvent("clastio:limit", { detail: { message: err?.message, details: err?.details } }));
    }
    if (res.status === 503 && err?.code === "maintenance" && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("clastio:maintenance", { detail: { message: err?.message } }));
    }
    const requestId = err?.requestId || res.headers.get("x-request-id") || undefined;
    let message = err?.message || res.statusText || "Request failed";
    if (res.status >= 500 && requestId) message = `${message} (ref ${requestId})`;
    throw new ApiError(res.status, err?.code || "http_error", message, err?.details, requestId);
  }
  if (init.method !== "GET" && typeof window !== "undefined") {
    window.dispatchEvent(new Event("clastio:work-started"));
  }
  if ((path === "/auth/logout" || path === "/auth/logout-all") && typeof navigator !== "undefined" && "serviceWorker" in navigator) {
    navigator.serviceWorker.controller?.postMessage({ type: "CLASTIO_SIGNED_OUT" });
  }
  if ((path === "/auth/logout" || path === "/auth/logout-all") && process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && typeof window !== "undefined") {
    const clerk = (window as unknown as { Clerk?: { signOut: () => Promise<void> } }).Clerk;
    await clerk?.signOut();
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
  try {
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
          let data: unknown = dataLines.join("\n");
          try {
            data = JSON.parse(data as string);
          } catch {} // Plain-text SSE data is valid too.
          onEvent({ event, data });
        }
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
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
