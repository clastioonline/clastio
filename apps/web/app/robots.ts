import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";
export default function robots(): MetadataRoute.Robots {
  return { rules: [{ userAgent: "*", allow: "/", disallow: ["/api/", "/activity", "/admin", "/dashboard", "/settings", "/billing", "/support", "/notifications", "/projects", "/assistant", "/lessons", "/calendar", "/curriculum", "/templates", "/media", "/teacher-memory", "/whatsapp", "/tutorials", "/onboarding", "/auth/", "/login", "/signup", "/reset-password", "/forgot-password", "/verify-email"] }], sitemap: `${SITE_URL}/sitemap.xml` };
}
