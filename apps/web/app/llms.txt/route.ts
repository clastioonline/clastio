import { teacherGuides } from "@/lib/teacher-guides";
import { SITE_URL } from "@/lib/seo";
export function GET() {
  const text = `# Clastio\n\n> An AI teaching assistant for planning lessons and editable PPTs, with teacher-controlled memory and licensed, uploaded or AI images.\n\n## Public resources\n\n- [Home](${SITE_URL}/): Product overview\n- [Pricing](${SITE_URL}/pricing): Current plans and allowances\n- [Teacher guides](${SITE_URL}/solutions): Practical planning workflows\n${teacherGuides.map((guide) => `- [${guide.title}](${SITE_URL}/solutions/${guide.slug}): ${guide.description}`).join("\n")}\n\n## Product limits\n\nTeachers review generated material before class. Curriculum approval, factual accuracy, AI detector outcomes and search ranking are not guaranteed. Image changes require clarification and confirmation. Teacher memories and signed-in resources are private.\n`;
  return new Response(text, {headers: {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600"}});
}
