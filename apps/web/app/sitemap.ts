import type { MetadataRoute } from "next";
import { teacherGuides } from "@/lib/teacher-guides";
import { publicPages } from "@/lib/public-pages";
import { SITE_URL } from "@/lib/seo";
export default function sitemap(): MetadataRoute.Sitemap {
  const pages = ["", "/pricing", "/solutions", ...publicPages.map((page) => page.path), ...teacherGuides.map((guide) => `/solutions/${guide.slug}`), "/status", "/legal/terms", "/legal/privacy", "/legal/acceptable_use", "/legal/cookie", "/legal/refund"];
  return pages.map((path) => ({ url: `${SITE_URL}${path}`, changeFrequency: path ? "monthly" : "weekly", priority: path === "" ? 1 : path.startsWith("/solutions") ? 0.8 : 0.5 }));
}
