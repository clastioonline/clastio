import Link from "next/link";
import { connection } from "next/server";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { fetchPublicJson } from "@/lib/public-api";
import { legalDocumentTitles, parseLegalIndex } from "@/lib/legal-documents";
import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata("Clastio policies and privacy information", "Find published Terms, Privacy, Cookie, Refund and Acceptable Use policies, plus privacy, copyright and support information.", "/legal");
export default async function LegalIndex() {
  await connection();
  const result = await fetchPublicJson("/api/v1/legal");
  const documents = parseLegalIndex(result.data);
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav /><main id="main-content" className="mx-auto max-w-4xl px-5 py-12 sm:px-8"><h1 className="text-4xl font-semibold tracking-tight">Policies and privacy information</h1><p className="mt-5 text-lg text-[var(--l-muted)]">Read the current published policies and find the right channel for an account, privacy or copyright question.</p>
    <section className="mt-8"><h2 className="text-2xl font-semibold">Published policies</h2>{!documents.length && <p className="mt-3">The policy list is temporarily unavailable. Use the direct links below or contact support.</p>}<ul className="mt-5 grid gap-4 sm:grid-cols-2">{(documents.length ? documents : Object.entries(legalDocumentTitles).filter(([key]) => key !== "dmca").map(([type, title]) => ({ type, title, version: "" }))).map(doc => <li key={doc.type}><Link href={`/legal/${doc.type}`} className="block rounded-xl border border-[var(--l-line)] p-5"><span className="font-semibold underline">{doc.title}</span>{doc.version && <span className="mt-2 block text-sm text-[var(--l-muted)]">Published version {doc.version}</span>}</Link></li>)}</ul></section>
    <section className="mt-9"><h2 className="text-2xl font-semibold">Requests and supporting information</h2><ul className="mt-5 grid gap-3 sm:grid-cols-2">{[["/data-privacy", "Personal-data requests"], ["/data-processing", "School data-processing review"], ["/security", "Account and upload security"], ["/accessibility", "Accessibility support"], ["/copyright", "Copyright enquiries"], ["/cancellation-policy", "Cancellation and refund help"], ["/contact", "Contact Clastio"], ["/help", "Help centre"]].map(([href, title]) => <li key={href}><Link href={href} className="underline">{title}</Link></li>)}</ul></section>
    </main><LandingFooter /></div>;
}
