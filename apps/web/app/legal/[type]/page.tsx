import { cache } from "react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { Markdown } from "@/components/markdown";
import { fetchPublicJson } from "@/lib/public-api";
import { legalDocumentTitles, parseLegalDocument, validLegalVersion } from "@/lib/legal-documents";
import { pageMetadata } from "@/lib/seo";
import { PUBLIC_SUPPORT_EMAIL, supportEmailFor } from "@/lib/public-support";

type Props = { params: Promise<{ type: string }>; searchParams: Promise<{ version?: string | string[] }> };
const getDocument = cache(async (type: string, version: string | undefined) => {
  const response = await fetchPublicJson(`/api/v1/legal/${type}${version ? `?version=${encodeURIComponent(version)}` : ""}`);
  if (response.status === 404) notFound();
  const doc = parseLegalDocument(response.data, type);
  if (!doc) throw new Error("The published policy is temporarily unavailable. Please try again.");
  return doc;
});

async function load(props: Props) {
  const { type } = await props.params;
  if (!Object.hasOwn(legalDocumentTitles, type)) notFound();
  await connection();
  const query = await props.searchParams;
  if (Array.isArray(query.version) || query.version && !validLegalVersion(query.version)) notFound();
  return { type, selectedVersion: query.version, doc: await getDocument(type, query.version) };
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const { type, doc } = await load(props);
  return { ...pageMetadata(`Clastio ${doc.title}`, `Read Clastio's published ${doc.title.toLowerCase()}, version ${doc.version}.`, `/legal/${type}`),
    ...(doc.status === "archived" ? { robots: { index: false, follow: true } } : {}) };
}

export default async function LegalPage(props: Props) {
  const { type, selectedVersion, doc } = await load(props);
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav />
    <main id="main-content" className="mx-auto grid max-w-5xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[12rem_1fr]">
      <nav aria-label="Legal documents" className="space-y-1 text-sm">
        <Link href="/legal" className="block rounded-lg px-3 py-2 font-semibold underline">All policies</Link>
        {Object.entries(legalDocumentTitles).filter(([key]) => key !== "dmca" || type === "dmca").map(([key, title]) => <Link key={key} href={`/legal/${key}`} aria-current={key === type ? "page" : undefined} className={`block rounded-lg px-3 py-2 ${key === type ? "bg-[var(--l-card)] font-semibold" : "text-[var(--l-muted)] hover:underline"}`}>{title}</Link>)}
        <Link href="/data-privacy" className="block rounded-lg px-3 py-2 underline">Privacy requests</Link><Link href="/copyright" className="block rounded-lg px-3 py-2 underline">Copyright enquiries</Link><Link href="/contact" className="block rounded-lg px-3 py-2 underline">Contact</Link>
      </nav>
      <article className="min-w-0 rounded-3xl bg-[var(--l-card)] p-6 sm:p-10">
        <h1 className="text-3xl font-bold tracking-tight">{doc.title}</h1>
        <p className="mt-2 text-sm text-[var(--l-muted)]">Version {doc.version}{doc.effective_from ? ` · effective ${new Date(doc.effective_from).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Dubai" })}` : ""}{doc.status === "archived" ? " · archived version" : ""}</p>
        {doc.versions.length > 1 || selectedVersion ? <details className="mt-4 rounded-xl border border-[var(--l-line)] p-4"><summary className="cursor-pointer font-semibold">Policy versions</summary><ul className="mt-3 space-y-2"><li><Link href={`/legal/${type}`} className="underline">Current effective policy</Link></li>{doc.versions.map(item => <li key={item.version}><Link href={`/legal/${type}?version=${encodeURIComponent(item.version)}`} className="underline">Version {item.version}{item.status === "archived" ? " (archived)" : ""}</Link></li>)}</ul></details> : null}
        {doc.summary_of_changes ? <p className="mt-4 rounded-xl bg-[var(--l-bg)] p-3 text-sm"><strong>What changed:</strong> {doc.summary_of_changes}</p> : null}
        <div className="legal-doc mt-6 leading-relaxed"><Markdown text={doc.content} /></div>
        <aside className="mt-8 border-t border-[var(--l-line)] pt-5 text-sm"><p>For current policy questions or privacy requests, contact <a href={supportEmailFor("Clastio policy enquiry")} className="underline">{PUBLIC_SUPPORT_EMAIL}</a> or <Link href="/support" className="underline">open an account support ticket</Link>.</p></aside>
      </article>
    </main><LandingFooter /></div>;
}
