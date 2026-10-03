import LandingPage from "@/components/landing-page";
import { jsonLd, pageMetadata, SITE_URL } from "@/lib/seo";
export const metadata = pageMetadata("AI teaching assistant and PPT maker for UAE teachers", "Plan lessons, create editable teaching PowerPoints in your own design, discuss image changes and use teacher memory with Clastio. Start a seven-day trial.", "/");
export default function HomePage() {
  const schema = {"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": `${SITE_URL}/#organization`, name: "Clastio", url: SITE_URL, logo: `${SITE_URL}/brand/clastio-original.png`},
    {"@type": "WebSite", "@id": `${SITE_URL}/#website`, name: "Clastio", url: SITE_URL, inLanguage: "en", publisher: {"@id": `${SITE_URL}/#organization`}},
    {"@type": "SoftwareApplication", name: "Clastio", applicationCategory: "EducationalApplication", operatingSystem: "Web", url: SITE_URL, description: "AI teaching assistant for lesson planning, editable PowerPoints, worksheets, quizzes and teacher-controlled memory.", publisher: {"@id": `${SITE_URL}/#organization`}},
  ]};
  return <><script type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd(schema)}} /><LandingPage /></>;
}
