import type { NextConfig } from "next";

const API_URL = process.env.API_URL || "http://localhost:8000";
const DEV = process.env.NODE_ENV !== "production";

// Next.js injects small inline scripts (and we inline the theme boot script), so scripts need 'unsafe-inline';
// Allow Turnstile and configured Clerk authentication resources alongside first-party assets.
// Headers are baked into the build. Keep the allowed authentication domains stable
// even when the publishable key is supplied only to the running service.
const clerkSources = " https://clerk.clastio.online https://*.clerk.accounts.dev https://*.protect.clerk.com https://clerk-telemetry.com https://*.clerk-telemetry.com";
const CSP = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${DEV ? " 'unsafe-eval'" : ""} https://challenges.cloudflare.com${clerkSources}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob: https:",
  "font-src 'self' data:",
  `connect-src 'self'${DEV ? " ws:" : ""}${clerkSources}${clerkSources ? " https://*.protect.clerk.com:*" : ""}`,
  `frame-src https://challenges.cloudflare.com${clerkSources}`,
  "worker-src 'self' blob:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

// Signed-in areas are private: never indexed.
const PRIVATE = ["activity", "dashboard", "projects", "assistant", "lessons", "calendar", "curriculum", "templates", "media", "teacher-memory",
  "whatsapp", "tutorials", "billing", "settings", "notifications", "support", "admin", "onboarding", "auth", "verify-email", "reset-password"];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    serverActions: { bodySizeLimit: "100mb" },
    proxyClientMaxBodySize: 104857600, // 100MB
  },
  // The Docker image sets NEXT_OUTPUT=standalone for a small self-contained server; `next start` is unaffected.
  output: process.env.NEXT_OUTPUT === "standalone" ? "standalone" : undefined,
  // The browser only ever talks to this origin; /api is proxied to FastAPI so session cookies stay first-party
  // and no API keys or backend URLs are exposed to the client.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          { key: "Content-Security-Policy", value: CSP },
          ...(DEV ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" }]),
        ],
      },
      ...PRIVATE.map((p) => ({ source: `/${p}/:path*`, headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] })),
      ...PRIVATE.map((p) => ({ source: `/${p}`, headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] })),
    ];
  },
};

export default nextConfig;
