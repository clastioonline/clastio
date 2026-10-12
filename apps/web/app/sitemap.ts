import type { MetadataRoute } from "next";
import { teacherGuides } from "@/lib/teacher-guides";
import { publicPages } from "@/lib/public-pages";
import { supportPages } from "@/lib/support-pages";
import { siteUrl } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  const pages = ["/", "/pricing", "/solutions", ...publicPages.map((page) => page.path),
    "/contact", "/legal", ...supportPages.map((page) => page.path),
    "/status", "/legal/terms", "/legal/privacy", "/legal/acceptable_use", "/legal/cookie", "/legal/refund"];
  const entries = new Map<string, MetadataRoute.Sitemap[number]>();
  for (const path of pages) {
    const url = siteUrl(path);
    entries.set(url, { url });
  }
  for (const guide of teacherGuides) {
    const url = siteUrl(`/solutions/${guide.slug}`);
    // A real editorial review date is useful. Request/build time would falsely
    // signal content changes; omit dates for pages without a known update date.
    entries.set(url, { url, lastModified: guide.reviewedAt });
  }
  return [...entries.values()];
}
