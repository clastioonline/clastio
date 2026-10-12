import { teacherGuides } from "@/lib/teacher-guides";
import { publicPages } from "@/lib/public-pages";
import { supportPages } from "@/lib/support-pages";
import { siteUrl } from "@/lib/seo";

export const dynamic = "force-static";

export function GET() {
  const text = [
    "# Clastio",
    "> An AI teaching assistant for UAE teachers: lesson planning, editable PowerPoints and classroom resources from a teacher's materials and school design. British curriculum workflows are a focus; teachers supply their actual objectives and specification.",
    "## Public resources",
    `- [Home](${siteUrl()}): Product overview`,
    `- [Pricing](${siteUrl("/pricing")}): Current plans, allowances and optional trial availability`,
    `- [Teacher guides](${siteUrl("/solutions")}): Practical planning workflows and choosing a tool`,
    ...publicPages.map((page) => `- [${page.title}](${siteUrl(page.path)}): ${page.description}`),
    ...teacherGuides.map((guide) => `- [${guide.title}](${siteUrl(`/solutions/${guide.slug}`)}): ${guide.description}${guide.reviewedAt ? ` Reviewed ${guide.reviewedAt}.` : ""}`),
    "## Policies and service status",
    `- [Contact Clastio](${siteUrl("/contact")}): Support email and the account support workflow`,
    `- [Published policies](${siteUrl("/legal")}): Current documents and their version history`,
    ...supportPages.map((page) => `- [${page.title}](${siteUrl(page.path)}): ${page.description}`),
    ...[["terms", "Terms and conditions"], ["privacy", "Privacy policy"], ["acceptable_use", "Acceptable use"],
      ["cookie", "Cookie policy"], ["refund", "Refund policy"]].map(([type, title]) => `- [${title}](${siteUrl(`/legal/${type}`)})`),
    `- [Service status](${siteUrl("/status")})`,
    "## Product limits",
    "Teachers inspect generated material and approve a PPT version before preparing the next lesson. Curriculum certification, factual accuracy, AI detector outcomes and search rankings are not guaranteed. British year groups and examination specifications must be supplied and checked by the teacher. Referenced books are not a promise that every textbook PDF is available or licensed for sharing. Prices and integrations depend on current configuration.",
    "## Access",
    "This file is an informational directory of public pages, not a ranking mechanism or authorization to access teacher data. Teacher memories, uploaded files and signed-in resources require authenticated access. Crawl preferences are described in robots.txt; private resource access remains controlled by the application.",
  ].join("\n\n") + "\n";
  return new Response(text, {headers: {"Content-Type": "text/plain; charset=utf-8",
    "Cache-Control": "public, max-age=3600", "X-Robots-Tag": "noindex"}});
}
