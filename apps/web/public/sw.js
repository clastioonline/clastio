/* Clastio keeps signed-in pages, API calls and teacher files on the network. */
const CACHE = "clastio-public-brand-v2";
const PUBLIC_ASSETS = ["/brand/favicon.png", "/brand/app-icon-512.png"];
const OFFLINE_PAGE = "/offline";
const PUBLIC_PAGES = ["/", "/pricing", "/solutions", "/how-it-works", "/for-schools", "/faq", "/help", "/contact", "/status", "/legal", "/offline", "/accessibility", "/security", "/copyright", "/data-privacy", "/data-processing", "/cancellation-policy"];

function isPublicDocument(request, url) {
  return request.mode === "navigate" && request.destination === "document" &&
    (PUBLIC_PAGES.includes(url.pathname) || url.pathname.startsWith("/solutions/") || url.pathname.startsWith("/legal/"));
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    for (const path of [...PUBLIC_ASSETS, OFFLINE_PAGE]) {
      try {
        const response = await fetch(path, { credentials: "omit", cache: "reload" });
        // Only this marked, self-contained public screen may be cached as HTML.
        // A generic 503 response, login page or authenticated redirect is excluded.
        const isOfflineScreen = path === OFFLINE_PAGE && response.status === 503 &&
          response.headers.get("X-Clastio-System-Page") === "offline" &&
          (response.headers.get("Content-Type") || "").startsWith("text/html");
        if (response.type === "basic" && (isOfflineScreen || (PUBLIC_ASSETS.includes(path) && response.ok))) await cache.put(path, response);
      } catch { /* A failed public preload must not cache an error response. */ }
    }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith("clastio-public-brand-") && name !== CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (!url.search && PUBLIC_ASSETS.includes(url.pathname)) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      return await cache.match(url.pathname) || fetch(event.request);
    })());
  } else if (isPublicDocument(event.request, url)) {
    event.respondWith((async () => {
      try {
        // Preserve real HTTP errors. Never cache the requested page's response.
        return await fetch(event.request);
      } catch (error) {
        const offline = await (await caches.open(CACHE)).match(OFFLINE_PAGE);
        if (offline) return offline;
        throw error;
      }
    })());
  }
});

self.addEventListener("push", (event) => {
  let message = {};
  try { message = event.data?.json() || {}; } catch { /* Always show a visible fallback notification. */ }
  event.waitUntil(self.registration.showNotification(String(message.title || "Clastio update").slice(0, 200), {
    body: String(message.body || "Open Clastio to see your latest update.").slice(0, 500),
    icon: "/brand/favicon.png",
    badge: "/brand/favicon.png",
    tag: String(message.tag || "clastio:update"),
    data: { url: typeof message.url === "string" ? message.url : "/notifications" },
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  let url = new URL("/notifications", self.location.origin);
  try {
    const candidate = new URL(event.notification.data?.url || "/notifications", self.location.origin);
    if (candidate.origin === self.location.origin && !candidate.username && !candidate.password) url = candidate;
  } catch { /* Ignore malformed links. */ }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const client of windows) {
      if (new URL(client.url).origin === self.location.origin && "focus" in client) {
        await client.navigate(url.href);
        return client.focus();
      }
    }
    return self.clients.openWindow(url.href);
  })());
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "CLASTIO_SIGNED_OUT") return;
  event.waitUntil((async () => {
    for (const notification of await self.registration.getNotifications()) notification.close();
  })());
});
