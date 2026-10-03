import Link from "next/link";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { publicPages } from "@/lib/public-pages";
import { jsonLd, SITE_URL } from "@/lib/seo";

export function PublicInfoPage({ page }: { page: typeof publicPages[number] }) {
  const url = `${SITE_URL}${page.path}`;
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]">
    <LandingNav />
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd({"@context": "https://schema.org", "@type": "WebPage", name: page.title, description: page.description, url, inLanguage: "en"})}} />
    <main id="main-content" className="mx-auto max-w-4xl px-5 py-14 sm:px-8">
      <Link href="/" className="text-sm text-brand-700 hover:underline">Clastio home</Link>
      <h1 className="mt-5 text-4xl font-semibold tracking-tight sm:text-5xl">{page.title}</h1>
      <p className="mt-6 text-lg leading-relaxed text-[var(--l-muted)]">{page.introduction}</p>
      <nav aria-label="On this page" className="mt-8 rounded-2xl bg-[var(--l-card)] p-6 ring-1 ring-black/10">
        <ul className="space-y-3">{page.sections.map((section, i) => <li key={section.heading}><a className="focus-ring text-brand-700 hover:underline" href={`#answer-${i}`}>{section.heading}</a></li>)}</ul>
      </nav>
      {page.sections.map((section, i) => <section key={section.heading} id={`answer-${i}`} className="mt-10 scroll-mt-6"><h2 className="text-2xl font-semibold">{section.heading}</h2><p className="mt-3 text-lg leading-relaxed text-[var(--l-muted)]">{section.text}</p></section>)}
      <aside className="mt-12 border-t border-[var(--l-line)] pt-8"><h2 className="text-xl font-semibold">Explore next</h2><ul className="mt-4 space-y-3">{page.links.map((link) => <li key={link.href}><Link className="text-brand-700 hover:underline" href={link.href}>{link.label}</Link></li>)}</ul></aside>
      <Link href="/signup" className="mt-8 inline-flex rounded-full bg-[#141414] px-6 py-3 font-semibold text-white">Start your seven-day trial</Link>
    </main>
    <LandingFooter />
  </div>;
}
