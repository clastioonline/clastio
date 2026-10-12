import Link from "next/link";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { jsonLd, SITE_URL } from "@/lib/seo";
import { PUBLIC_SUPPORT_EMAIL, supportEmailFor } from "@/lib/public-support";
import type { SupportPage } from "@/lib/support-pages";

export function SupportInfoPage({ page }: { page: SupportPage }) {
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd({ "@context": "https://schema.org", "@type": "WebPage", name: page.title, description: page.description, url: `${SITE_URL}${page.path}`, isPartOf: { "@id": `${SITE_URL}/#website` } }) }} />
    <main id="main-content" className="mx-auto max-w-4xl px-5 py-12 sm:px-8">
      <nav aria-label="Breadcrumb" className="mb-6 text-sm"><Link href="/" className="underline">Home</Link> / <Link href="/help" className="underline">Help and support</Link></nav>
      <h1 className="text-4xl font-semibold tracking-tight">{page.title}</h1><p className="mt-5 text-lg leading-relaxed text-[var(--l-muted)]">{page.introduction}</p>
      <nav aria-label="On this page" className="mt-7 rounded-2xl border border-[var(--l-line)] p-5"><ul className="space-y-2">{page.sections.map((section, i) => <li key={section.title}><a href={`#support-section-${i}`} className="underline">{section.title}</a></li>)}</ul></nav>
      {page.sections.map((section, i) => <section key={section.title} id={`support-section-${i}`} className="mt-9 scroll-mt-5"><h2 className="text-2xl font-semibold">{section.title}</h2><p className="mt-3 leading-relaxed text-[var(--l-muted)]">{section.text}</p>{section.links && <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2">{section.links.map(link => <li key={link.href}><Link href={link.href} className="underline">{link.label}</Link></li>)}</ul>}</section>)}
      <aside className="mt-10 rounded-2xl bg-[var(--l-card)] p-6"><h2 className="text-xl font-semibold">Need help from Clastio?</h2><p className="mt-3 break-words">Email <a href={supportEmailFor(page.title)} className="underline">{PUBLIC_SUPPORT_EMAIL}</a> or <Link href="/support" className="underline">open an account support ticket</Link>.</p><nav aria-label="Support resources" className="mt-4 flex flex-wrap gap-x-5 gap-y-2"><Link href="/contact" className="underline">Contact</Link><Link href="/legal" className="underline">Policies</Link><Link href="/status" className="underline">Service status</Link><Link href="/faq" className="underline">Product questions</Link></nav></aside>
    </main><LandingFooter /></div>;
}
