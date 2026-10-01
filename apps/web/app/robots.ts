import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: ["/", "/pricing", "/legal/", "/status"], disallow: ["/api/", "/activity", "/admin", "/dashboard", "/settings", "/billing", "/support", "/notifications"] }],
    sitemap: `${SITE}/sitemap.xml`,
  };
}
