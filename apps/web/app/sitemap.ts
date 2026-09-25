import type { MetadataRoute } from "next";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export default function sitemap(): MetadataRoute.Sitemap {
  const pages = ["", "/pricing", "/signup", "/login", "/status", "/legal/terms", "/legal/privacy", "/legal/acceptable_use", "/legal/cookie", "/legal/refund"];
  return pages.map((p) => ({ url: `${SITE}${p}`, changeFrequency: p ? "monthly" : "weekly", priority: p ? 0.5 : 1 }));
}
