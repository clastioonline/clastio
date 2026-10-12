export type SystemTone = "neutral" | "success" | "warn" | "danger";
export type SystemAction = { href: string; label: string };
export type SystemPageDefinition = {
  slug: string;
  code?: string;
  title: string;
  description: string;
  status: number;
  tone: SystemTone;
  primaryAction: SystemAction;
  secondaryAction?: SystemAction;
  hints?: string[];
};

export const systemPages: SystemPageDefinition[] = [
  { slug: "400", code: "400", title: "This request needs a quick check", status: 400, tone: "warn",
    description: "The link or request looks incomplete. Open a fresh page and try again.",
    primaryAction: { href: "/", label: "Go home" }, secondaryAction: { href: "/help", label: "Find help" },
    hints: ["Check that a copied link has not been cut off.", "Start again from the page where you began this action."] },
  { slug: "401", code: "401", title: "Sign in to continue", status: 401, tone: "neutral",
    description: "Open your Clastio account to access your lessons and teaching resources.",
    primaryAction: { href: "/login", label: "Sign in" }, secondaryAction: { href: "/", label: "Go home" },
    hints: ["Use the same email and sign-in method as your existing account.", "After signing in, open the resource from your dashboard."] },
  { slug: "403", code: "403", title: "This page is not available to this account", status: 403, tone: "warn",
    description: "Your account may not have access to this resource. Check which account you are using before trying again.",
    primaryAction: { href: "/dashboard", label: "Open dashboard" }, secondaryAction: { href: "/contact", label: "Contact support" },
    hints: ["Private lessons belong to their teacher's account.", "Return to your own library rather than resubmitting this link."] },
  { slug: "404", code: "404", title: "We could not find this page", status: 404, tone: "neutral",
    description: "This link may be out of date, or the address may be incomplete. Choose a useful starting point below.",
    primaryAction: { href: "/solutions", label: "Explore teaching guides" }, secondaryAction: { href: "/", label: "Go home" },
    hints: ["Check the spelling of the page address.", "If you were opening a saved lesson, find it again from your dashboard."] },
  { slug: "409", code: "409", title: "Refresh before making this change", status: 409, tone: "warn",
    description: "This request conflicts with the latest saved version or work already in progress.",
    primaryAction: { href: "/activity", label: "Check activity" }, secondaryAction: { href: "/dashboard", label: "Open dashboard" },
    hints: ["Let an existing update finish before submitting another one.", "Refresh the lesson and review its latest version before changing it."] },
  { slug: "429", code: "429", title: "Please wait a moment", status: 429, tone: "warn",
    description: "Too many requests arrived close together. Wait briefly before trying again.",
    primaryAction: { href: "/status", label: "Check service status" }, secondaryAction: { href: "/", label: "Go home" },
    hints: ["Avoid repeatedly submitting the same generation or checkout.", "Work submitted earlier may still be running in the background."] },
  { slug: "500", code: "500", title: "We could not load this page", status: 500, tone: "danger",
    description: "Try loading the page again. If the problem continues, contact support with the time it happened and any reference shown.",
    primaryAction: { href: "/", label: "Go home" }, secondaryAction: { href: "/contact", label: "Contact support" },
    hints: ["Check Activity before repeating a generation request.", "A page error does not confirm that a payment or generation completed."] },
  { slug: "503", code: "503", title: "Please try again shortly", status: 503, tone: "warn",
    description: "The requested service cannot be reached right now. Check current service notices before trying again.",
    primaryAction: { href: "/status", label: "Check service status" }, secondaryAction: { href: "/help", label: "Find help" },
    hints: ["Avoid submitting the same payment or generation several times.", "When access returns, check your account for the result of an earlier request."] },
  { slug: "maintenance", title: "Check the current service notice", status: 503, tone: "neutral",
    description: "The teaching workspace may be paused during maintenance. The status page has current notices; this page does not indicate an app-wide outage.",
    primaryAction: { href: "/status", label: "Check live status" }, secondaryAction: { href: "/", label: "Go home" },
    hints: ["Keep any tab with unsaved work open.", "Check the latest notice before retrying your teaching task."] },
  { slug: "offline", title: "Reconnect to keep teaching", status: 503, tone: "neutral",
    description: "Check your connection, then reopen Clastio. Keep any tab with unsaved work open until you are connected.",
    primaryAction: { href: "/", label: "Try opening Clastio" }, secondaryAction: { href: "/status", label: "Check service status" },
    hints: ["Private lessons and account tools need a connection.", "Generation submitted before the connection dropped may still be running. Check Activity after reconnecting."] },
  { slug: "browser-not-supported", title: "Use a current browser", status: 200, tone: "neutral",
    description: "The teaching workspace needs JavaScript and a current browser. Update your browser or try another supported browser before opening the app.",
    primaryAction: { href: "/login", label: "Open sign in" }, secondaryAction: { href: "/help", label: "Find help" },
    hints: ["Enable JavaScript for Clastio in your browser settings.", "If school settings block a feature, ask your administrator before changing them."] },
  { slug: "permission-required", title: "Allow the permission you need", status: 403, tone: "neutral",
    description: "Your browser has not allowed an optional feature. Review this site's permissions; you can continue using other Clastio tools.",
    primaryAction: { href: "/settings", label: "Open settings" }, secondaryAction: { href: "/help", label: "Find help" },
    hints: ["Grant only permissions for features you choose to use.", "Device notifications are optional and may also need to be enabled by your administrator."] },
];

export function systemPageForSlug(slug: string): SystemPageDefinition | undefined {
  return systemPages.find(page => page.slug === slug);
}

export const SYSTEM_STATE_CSS = `
.sys-page{--sys-bg:var(--color-canvas,#f5f8f6);--sys-surface:var(--color-surface,#fff);--sys-ink:var(--color-ink,#173526);--sys-muted:var(--color-muted,#526b5d);--sys-line:var(--color-line,#dce6df);--sys-brand:var(--color-brand-600,#1b7446);box-sizing:border-box;min-height:100vh;padding:26px 24px;color:var(--sys-ink);background:var(--sys-bg);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:16px;line-height:1.65}
.sys-page *{box-sizing:border-box}.sys-brand,.sys-nav a,.sys-footer a{color:inherit;text-decoration:none}.sys-page a:focus-visible,.sys-page button:focus-visible{outline:3px solid #61a681;outline-offset:4px}.sys-wrap{width:min(960px,100%);margin:0 auto}.sys-header{display:flex;align-items:center;justify-content:space-between;gap:18px;flex-wrap:wrap}.sys-brand{display:inline-flex;align-items:center;gap:11px;font-size:25px;font-weight:760;letter-spacing:-.7px}.sys-brand img{width:44px;height:44px;border-radius:12px;background:#fff}.sys-nav{display:flex;flex-wrap:wrap;gap:20px;font-size:14px;color:var(--sys-muted)}.sys-nav a:hover,.sys-footer a:hover{text-decoration:underline}.sys-card{margin:72px 0 30px;padding:46px;border:1px solid var(--sys-line);border-radius:28px;background:var(--sys-surface);box-shadow:0 12px 45px #14372608}.sys-badge{display:inline-flex;align-items:center;gap:9px;padding:7px 13px;border-radius:20px;background:#e9f3ec;color:#1b7446;font-size:13px;font-weight:700;letter-spacing:.25px}.sys-badge[data-tone=warn]{background:#fff1d9;color:#805315}.sys-badge[data-tone=danger]{background:#fee9e5;color:#9b3226}.sys-badge[data-tone=success]{background:#e4f6ea;color:#17623a}.sys-card h1{max-width:760px;margin:23px 0 17px;font-size:clamp(29px,4.4vw,43px);line-height:1.2;letter-spacing:-1.2px}.sys-description{max-width:700px;margin:0;color:var(--sys-muted);font-size:17px;line-height:1.7}.sys-actions{display:flex;flex-wrap:wrap;align-items:center;gap:13px;margin:28px 0 0}.sys-action{display:inline-flex;align-items:center;justify-content:center;min-height:46px;padding:10px 19px;border:1px solid var(--sys-line);border-radius:24px;background:var(--sys-surface);color:var(--sys-ink);text-decoration:none;font:inherit;font-size:15px;font-weight:650;cursor:pointer}.sys-action.sys-primary{background:var(--sys-brand);color:white;border-color:var(--sys-brand)}.sys-action:hover{filter:brightness(.96)}.sys-content{margin-top:24px}.sys-hints{margin:31px 0 0;padding:23px 24px;border:1px solid var(--sys-line);border-radius:17px;background:var(--sys-bg)}.sys-hints h2{margin:0 0 12px;font-size:15px}.sys-hints ul{margin:0;padding-left:19px;color:var(--sys-muted);font-size:14px}.sys-hints li+li{margin-top:8px}.sys-reference{margin:21px 0 0;font-size:13px;color:var(--sys-muted);overflow-wrap:anywhere}.sys-footer{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;color:var(--sys-muted);font-size:13px}.sys-footer-links{display:flex;flex-wrap:wrap;gap:18px}
@media(max-width:600px){.sys-page{padding:19px 16px}.sys-card{margin-top:40px;padding:28px 23px;border-radius:23px}.sys-card h1{letter-spacing:-.8px}.sys-description{font-size:16px}.sys-hints{padding:20px}.sys-actions{gap:10px}.sys-action{max-width:100%;text-align:center}.sys-nav{gap:15px}}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]) .sys-page{--sys-bg:var(--color-canvas,#111e16);--sys-surface:var(--color-surface,#17271d);--sys-ink:var(--color-ink,#edf5ef);--sys-muted:var(--color-muted,#aec2b4);--sys-line:var(--color-line,#33473a);--sys-brand:var(--color-brand-600,#237b4b)}}
:root[data-theme=dark] .sys-page{--sys-bg:var(--color-canvas,#111e16);--sys-surface:var(--color-surface,#17271d);--sys-ink:var(--color-ink,#edf5ef);--sys-muted:var(--color-muted,#aec2b4);--sys-line:var(--color-line,#33473a);--sys-brand:var(--color-brand-600,#237b4b)}
`;

export function safeSystemHref(href: string): string {
  return /^\/(?!\/)/.test(href) && !/[\\\u0000-\u001f]/.test(href) ? href : "/";
}

export function escapeSystemHtml(value: string): string {
  const entities: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return value.replace(/[&<>"']/g, character => entities[character]);
}

// Proxy can return this public, data-free document with the actual HTTP status.
// It uses the same catalog/classes as the React error and account layouts.
export function renderSystemPageHtml(page: SystemPageDefinition, themeScript = ""): string {
  const esc = escapeSystemHtml;
  const link = (action: SystemAction, primary = false) => `<a class="sys-action${primary ? " sys-primary" : ""}" href="${esc(safeSystemHref(action.href))}">${esc(action.label)}</a>`;
  const hints = page.hints?.length ? `<aside class="sys-hints"><h2>What you can do</h2><ul>${page.hints.map(hint => `<li>${esc(hint)}</li>`).join("")}</ul></aside>` : "";
  return `<!doctype html><html lang="en" data-skin="forest"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="description" content="${esc(page.description)}"><title>${esc(page.title)} | Clastio</title><link rel="icon" href="/brand/favicon.png"><style>${SYSTEM_STATE_CSS}</style>${themeScript ? `<script>${themeScript}</script>` : ""}</head><body style="margin:0"><main class="sys-page"><div class="sys-wrap"><header class="sys-header"><a class="sys-brand" href="/" aria-label="Clastio home"><img src="/brand/favicon.png" width="44" height="44" alt="">Clastio</a><nav class="sys-nav" aria-label="Help navigation"><a href="/help">Help</a><a href="/contact">Contact</a><a href="/status">Status</a></nav></header><section class="sys-card" aria-labelledby="sys-title"><span class="sys-badge" data-tone="${esc(page.tone)}">${esc(page.code ? `${page.code} · Clastio` : "Clastio")}</span><h1 id="sys-title">${esc(page.title)}</h1><p class="sys-description">${esc(page.description)}</p><div class="sys-actions">${link(page.primaryAction, true)}${page.secondaryAction ? link(page.secondaryAction) : ""}</div>${hints}</section><footer class="sys-footer"><span>Your teaching, in your own design.</span><nav class="sys-footer-links" aria-label="Useful links"><a href="/solutions">Teaching guides</a><a href="/legal/privacy">Privacy</a><a href="/">Home</a></nav></footer></div></main></body></html>`;
}
