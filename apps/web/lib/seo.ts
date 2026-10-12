import type { Metadata } from "next";

const DEFAULT_SITE_URL = "https://clastio.online";

export function normalizeSiteOrigin(value?: string): string {
  try {
    const url = new URL(value?.trim() || DEFAULT_SITE_URL);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return DEFAULT_SITE_URL;
    return url.origin;
  } catch {
    return DEFAULT_SITE_URL;
  }
}

export const SITE_URL = normalizeSiteOrigin(process.env.NEXT_PUBLIC_SITE_URL);

export function siteUrl(path = "/"): string {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\")) {
    throw new Error("Site URLs must use a local absolute path");
  }
  const url = new URL(path, SITE_URL);
  if (url.origin !== SITE_URL) throw new Error("Site URLs must stay on the configured origin");
  url.pathname = url.pathname.replace(/\/+$/, "") || "/";
  url.search = "";
  url.hash = "";
  return url.href;
}

// These are crawl controls; account authentication remains the privacy boundary.
// The root metadata defaults to noindex and public pages opt in with pageMetadata.
export const PRIVATE_PATHS = [
  "/activity", "/admin", "/api", "/assistant", "/auth", "/billing", "/books",
  "/calendar", "/copilot", "/curriculum", "/dashboard", "/demo-classes", "/digital-library",
  "/forgot-password", "/lesson-planners", "/lessons", "/login", "/media", "/notifications",
  "/onboarding", "/projects", "/reset-password", "/rewards", "/settings", "/signup", "/support",
  "/teacher-memory", "/templates", "/tutorials", "/verify-email", "/whatsapp",
  "/400", "/401", "/403", "/404", "/409", "/429", "/500", "/503", "/maintenance", "/offline",
  "/browser-not-supported", "/permission-required", "/session-expired", "/account-suspended",
  "/account-deactivated", "/account-deleted", "/delete-account", "/data-export-request",
  "/verification-success", "/verification-failed", "/link-expired", "/email-unsubscribe", "/notification-preferences",
  "/payment-success", "/payment-failed", "/subscription-expired", "/trial-expired", "/usage-limit",
  "/upgrade-required", "/billing-portal", "/checkout", "/subscription-cancelled",
];

// Public client-rendered pages need these read-only resources to render for crawlers.
export const PUBLIC_CRAWL_ENDPOINTS = ["/api/v1/billing/plans$", "/api/v1/legal$", "/api/v1/legal/", "/api/v1/public/config$", "/api/v1/status$"];

// Familiar policy addresses resolve to one published canonical document.
export const PUBLIC_POLICY_ALIASES = [
  { source: "/privacy", destination: "/legal/privacy" },
  { source: "/terms", destination: "/legal/terms" },
  { source: "/cookies", destination: "/legal/cookie" },
  { source: "/refund-policy", destination: "/legal/refund" },
  { source: "/acceptable-use", destination: "/legal/acceptable_use" },
];

export const SOCIAL_IMAGE = {
  url: siteUrl("/brand/social-card.png"),
  width: 1200,
  height: 630,
  type: "image/png",
  alt: "Clastio — lesson planning and editable PowerPoints for UAE teachers",
};

export function pageMetadata(title: string, description: string, path: string): Metadata {
  const url = siteUrl(path);
  const brandedTitle = /\bclastio\b/i.test(title) ? title : `${title} | Clastio`;
  return { title: { absolute: brandedTitle }, description, alternates: { canonical: url },
    openGraph: { title: brandedTitle, description, url, siteName: "Clastio", type: "website", locale: "en_AE", images: [SOCIAL_IMAGE] },
    twitter: { card: "summary_large_image", title: brandedTitle, description, images: [{ url: SOCIAL_IMAGE.url, alt: SOCIAL_IMAGE.alt }] },
    robots: { index: true, follow: true, googleBot: { index: true, follow: true, "max-image-preview": "large", "max-snippet": -1 } },
  };
}

export function siteGraph() {
  return { "@context": "https://schema.org", "@graph": [
    { "@type": "Organization", "@id": `${SITE_URL}/#organization`, name: "Clastio", url: siteUrl(),
      logo: siteUrl("/brand/clastio-original.png") },
    { "@type": "WebSite", "@id": `${SITE_URL}/#website`, name: "Clastio", url: siteUrl(),
      inLanguage: "en", publisher: { "@id": `${SITE_URL}/#organization` } },
    { "@type": "SoftwareApplication", "@id": `${SITE_URL}/#application`, name: "Clastio",
      applicationCategory: "EducationalApplication", operatingSystem: "Web", url: siteUrl(),
      description: "AI teaching assistant for lesson planning, editable PowerPoints, worksheets, quizzes and teacher-controlled memory.",
      publisher: { "@id": `${SITE_URL}/#organization` } },
  ] };
}

export function jsonLd(value: unknown) { return JSON.stringify(value).replace(/</g, "\\u003c"); }
