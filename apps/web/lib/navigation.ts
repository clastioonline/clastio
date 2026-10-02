/** Accept only paths on this origin, including their query and fragment. */
export function safeInternalPath(value: string | null | undefined, fallback = "/dashboard"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return fallback;
  try {
    const url = new URL(value, "https://app.invalid");
    return url.origin === "https://app.invalid" ? `${url.pathname}${url.search}${url.hash}` : fallback;
  } catch { return fallback; }
}
