import type { Metadata } from "next";

const TITLES: Record<string, string> = {
  terms: "Terms & Conditions", privacy: "Privacy Policy", acceptable_use: "Acceptable Use Policy",
  cookie: "Cookie Policy", refund: "Refund Policy", dmca: "Copyright Policy",
};

export async function generateMetadata({ params }: { params: Promise<{ type: string }> }): Promise<Metadata> {
  const { type } = await params;
  return { title: TITLES[type] || "Legal", description: `Clastio ${TITLES[type] || "legal document"}.` };
}

export default function LegalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
