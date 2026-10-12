/** Public contact details supplied by the owner on 12 October 2026. */
export const PUBLIC_BRAND = "Clastio";
export const PUBLIC_SUPPORT_EMAIL = "Support@clastio.online";
export const SUPPORT_MAILTO = `mailto:${PUBLIC_SUPPORT_EMAIL}`;

export function supportEmailFor(subject: string): string {
  return `${SUPPORT_MAILTO}?subject=${encodeURIComponent(subject.slice(0, 160))}`;
}
