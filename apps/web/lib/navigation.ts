/** Accept only paths on this origin, including their query and fragment. */
export function safeInternalPath(value: string | null | undefined, fallback = "/dashboard"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || /[\\\u0000-\u0020]/.test(value)) return fallback;
  try {
    const url = new URL(value, "https://app.invalid");
    return url.origin === "https://app.invalid" ? `${url.pathname}${url.search}${url.hash}` : fallback;
  } catch { return fallback; }
}

/** A sign-in return must also avoid authentication loops and raw API endpoints. */
export function safeSignInReturnPath(value: string | null | undefined): string {
  const path = safeInternalPath(value);
  return /^\/(?:auth|api|login|signup|session-expired)(?:\/|\?|#|$)/.test(path) ? "/dashboard" : path;
}

export function clerkCallbackPath(value: string | null | undefined): string {
  return `/auth/clerk?next=${encodeURIComponent(safeSignInReturnPath(value))}`;
}

export function postSignInPath(user: { role: string; permissions?: string[]; onboarding_completed: boolean }, next?: string | null): string {
  if (user.role === "admin") return adminLandingPath(user.permissions);
  return user.onboarding_completed ? safeSignInReturnPath(next) : "/onboarding";
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
