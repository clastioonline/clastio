/** Accept only paths on this origin, including their query and fragment. */
export function safeInternalPath(value: string | null | undefined, fallback = "/dashboard"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return fallback;
  try {
    const url = new URL(value, "https://app.invalid");
    return url.origin === "https://app.invalid" ? `${url.pathname}${url.search}${url.hash}` : fallback;
  } catch { return fallback; }
}

/** Staff land on a page their verified permissions allow. */
export function adminLandingPath(permissions: string[] = []): string {
  const routes: [string, string][] = [
    ["analytics.view", "/admin"], ["users.view", "/admin/users"], ["billing.view", "/admin/billing"],
    ["api_usage.view", "/admin/api-usage"], ["support.manage", "/admin/support"],
    ["security.view", "/admin/security"], ["system.logs.view", "/admin/system"],
    ["settings.modify", "/admin/settings"], ["legal.manage", "/admin/legal"],
  ];
  return routes.find(([permission]) => permissions.includes(permission))?.[1] || "/settings";
}
