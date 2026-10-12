/** Server-side public GET only. Never forward the visitor's session or auth headers. */
export async function fetchPublicJson(path: string, maxBytes = 1024 * 1024): Promise<{ status: number; data: unknown }> {
  if (!/^\/api\/v1\/(?:legal(?:\/[a-z_]+)?(?:\?version=[A-Za-z0-9.%_-]+)?|public\/config)$/.test(path)) throw new Error("Unsupported public resource path");
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 3000);
  try {
    const base = new URL(process.env.API_URL || "http://localhost:8000");
    if (!["http:", "https:"].includes(base.protocol) || base.username || base.password) return { status: 0, data: null };
    const response = await fetch(new URL(path, base), { headers: { accept: "application/json" }, credentials: "omit", redirect: "error", cache: "no-store", signal: controller.signal });
    if (!response.ok || !response.body || !response.headers.get("content-type")?.includes("application/json") || Number(response.headers.get("content-length")) > maxBytes) {
      await response.body?.cancel();
      return { status: response.ok ? 0 : response.status, data: null };
    }
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let size = 0, text = "";
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > maxBytes) { await reader.cancel(); return { status: 0, data: null }; }
        text += decoder.decode(value, { stream: true });
      }
      text += decoder.decode();
    } finally { reader.releaseLock(); }
    return { status: response.status, data: JSON.parse(text) };
  } catch { return { status: 0, data: null }; }
  finally { clearTimeout(timer); }
}
