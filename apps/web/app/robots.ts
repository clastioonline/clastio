import type { MetadataRoute } from "next";
import { PRIVATE_PATHS, PUBLIC_CRAWL_ENDPOINTS, siteUrl } from "@/lib/seo";

export default function robots(): MetadataRoute.Robots {
  // Search and training are separate choices. Preserve the existing public
  // training policy; explicit search rules must carry the private exclusions.
  const crawl = { allow: ["/", ...PUBLIC_CRAWL_ENDPOINTS], disallow: PRIVATE_PATHS };
  return { rules: [{ userAgent: "*", ...crawl }, { userAgent: "OAI-SearchBot", ...crawl }],
    sitemap: siteUrl("/sitemap.xml") };
}
