import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { pageMetadata } from "@/lib/seo";

const titles: Record<string, string> = {
  terms: "Terms and Conditions", privacy: "Privacy Policy", acceptable_use: "Acceptable Use Policy",
  cookie: "Cookie Policy", refund: "Refund Policy",
};
type Props = { params: Promise<{ type: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { type } = await params;
  const title = Object.hasOwn(titles, type) ? titles[type] : null;
  if (!title) notFound();
  return pageMetadata(`Clastio ${title}`, `Read Clastio's ${title} and the current published document version.`, `/legal/${type}`);
}

export default async function LegalLayout({ children, params }: Props & { children: React.ReactNode }) {
  const { type } = await params;
  if (!Object.hasOwn(titles, type)) notFound();
  return children;
}
