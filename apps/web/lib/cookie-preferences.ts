export const COOKIE_PREFERENCES_EVENT = "clastio:open-cookie-preferences";
let requested = false;

/** Keep an early click until the lazily loaded dialog has mounted. */
export function requestCookiePreferences() {
  if (typeof window === "undefined") return;
  requested = true;
  window.dispatchEvent(new Event(COOKIE_PREFERENCES_EVENT));
}

export function consumeCookiePreferencesRequest(): boolean {
  const pending = requested;
  requested = false;
  return pending;
}
