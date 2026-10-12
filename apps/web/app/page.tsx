import LandingPage from "@/components/landing-page";
import { jsonLd, pageMetadata, siteGraph } from "@/lib/seo";
import { teacherGuides } from "@/lib/teacher-guides";
export const metadata = pageMetadata("AI PowerPoint maker and lesson planner for UAE teachers | Clastio", "Create editable teaching PPTs from your notes and school design. Plan British curriculum lessons with your objectives. Compare AED plans and start on Free.", "/");
const featuredSlugs = ["ai-ppt-maker-for-teachers-uae", "british-curriculum-lesson-planning", "gcse-igcse-lesson-presentations", "turn-teaching-notes-into-powerpoint", "how-to-choose-ai-presentation-maker-for-teachers", "ai-lesson-planning-costs-and-credits"];
export default function HomePage() {
  // Keep full source notes, FAQs and article bodies out of the homepage client bundle.
  const featuredGuides = featuredSlugs.flatMap(slug => {
    const guide = teacherGuides.find(item => item.slug === slug);
    return guide ? [{ slug: guide.slug, title: guide.title, description: guide.description }] : [];
  });
  return <><script type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd(siteGraph())}} /><LandingPage featuredGuides={featuredGuides} /></>;
}
