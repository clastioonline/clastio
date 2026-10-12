import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { findTeacherGuide, relatedTeacherGuides, teacherGuides } from "@/lib/teacher-guides";
import { jsonLd, pageMetadata, SITE_URL } from "@/lib/seo";
type Props = { params: Promise<{ slug: string }> };
export const dynamicParams = false;
export function generateStaticParams() { return teacherGuides.map(({slug}) => ({slug})); }
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params; const guide = findTeacherGuide(slug);
  if (!guide) notFound();
  return pageMetadata(guide.title, guide.description, `/solutions/${guide.slug}`);
}
export default async function TeacherGuidePage({ params }: Props) {
  const {slug} = await params; const guide = findTeacherGuide(slug); if (!guide) notFound();
  const url = `${SITE_URL}/solutions/${guide.slug}`;
  const schema = {"@context": "https://schema.org", "@graph": [
    {"@type": "Article", "@id": `${url}#article`, headline: guide.title, description: guide.description, mainEntityOfPage: url, inLanguage: "en", author: {"@type": "Organization", name: "Clastio", url: SITE_URL}, publisher: {"@type": "Organization", name: "Clastio", url: SITE_URL},
      ...(guide.reviewedAt ? { dateModified: guide.reviewedAt } : {}),
      ...(guide.sources?.length ? { citation: guide.sources.map(source => source.url.startsWith("/") ? `${SITE_URL}${source.url}` : source.url) } : {}),
      articleBody: [guide.answer, ...guide.sections.map((section) => [section.heading, section.text, ...(section.checks || []), ...(section.table?.rows.map(row => row.join(": ")) || [])].join("\n")), ...guide.steps, guide.example].join("\n")},
    {"@type": "BreadcrumbList", itemListElement: [{"@type": "ListItem", position: 1, name: "Home", item: SITE_URL}, {"@type": "ListItem", position: 2, name: "Teacher guides", item: `${SITE_URL}/solutions`}, {"@type": "ListItem", position: 3, name: guide.title, item: url}]},
  ]};
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav />
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html: jsonLd(schema)}} />
    <main id="main-content" className="mx-auto max-w-4xl px-5 py-12 sm:px-8"><nav aria-label="Breadcrumb" className="mb-7 text-sm text-[var(--l-muted)]"><Link href="/">Home</Link> / <Link href="/solutions">Teacher guides</Link></nav>
      <article><header><p className="text-sm font-semibold text-brand-700">Clastio · {guide.category || "Practical teacher guide"}</p><h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">{guide.title}</h1>
        {guide.reviewedAt && <p className="mt-3 text-sm text-[var(--l-muted)]">Updated <time dateTime={guide.reviewedAt}>{new Date(`${guide.reviewedAt}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })}</time> · Clastio workflow guide</p>}
        <p className="mt-6 rounded-2xl bg-[var(--l-card)] p-6 text-lg leading-relaxed ring-1 ring-black/10">{guide.answer}</p></header>
      <nav aria-label="On this page" className="mt-8 rounded-2xl border border-[var(--l-line)] p-5"><h2 className="font-semibold">In this guide</h2><ul className="mt-3 space-y-2">{guide.sections.map((s, i) => <li key={s.heading}><a href={`#${s.id || `section-${i}`}`} className="focus-ring text-brand-700 hover:underline">{s.heading}</a></li>)}<li><a href="#questions" className="text-brand-700 hover:underline">Common questions</a></li>{guide.sources?.length ? <li><a href="#sources" className="text-brand-700 hover:underline">Sources and further reading</a></li> : null}</ul></nav>
      {guide.sections.map((section, i) => <section id={section.id || `section-${i}`} key={section.heading} className="mt-10 scroll-mt-5"><h2 className="text-2xl font-semibold">{section.heading}</h2><p className="mt-3 text-lg leading-relaxed text-[var(--l-muted)]">{section.text}</p>
        {section.checks?.length ? <ul className="mt-4 list-disc space-y-3 ps-6 text-[var(--l-muted)]">{section.checks.map(check => <li key={check}>{check}</li>)}</ul> : null}
        {section.table && <div className="mt-5 overflow-hidden rounded-xl border border-[var(--l-line)]"><table className="w-full table-fixed border-collapse text-left text-sm"><caption className="bg-[var(--l-card)] p-4 text-left font-semibold">{section.table.caption}</caption><thead><tr>{section.table.columns.map(column => <th key={column} scope="col" className="break-words border-t border-[var(--l-line)] p-3 align-top">{column}</th>)}</tr></thead><tbody>{section.table.rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => cellIndex === 0
          ? <th key={cellIndex} scope="row" className="break-words border-t border-[var(--l-line)] p-3 align-top font-medium">{cell}</th>
          : <td key={cellIndex} className="break-words border-t border-[var(--l-line)] p-3 align-top text-[var(--l-muted)]">{cell}</td>)}</tr>)}</tbody></table></div>}
      </section>)}
      <section className="mt-10"><h2 className="text-2xl font-semibold">A workflow to try</h2><ol className="mt-4 list-decimal space-y-3 ps-6 text-lg text-[var(--l-muted)]">{guide.steps.map((step) => <li key={step}>{step}</li>)}</ol></section>
      <section className="mt-10 rounded-2xl bg-[var(--l-card)] p-6 ring-1 ring-black/10"><h2 className="text-2xl font-semibold">Example teacher prompt</h2><blockquote className="mt-4 border-s-4 border-brand-600 ps-4 text-lg leading-relaxed">{guide.example}</blockquote><Link href="/signup" className="mt-5 inline-flex rounded-full bg-[#141414] px-5 py-3 font-semibold text-white">Try the planning playground</Link></section>
      <section id="questions" className="mt-10"><h2 className="text-2xl font-semibold">Common questions</h2><dl className="mt-5 space-y-6">{guide.questions.map((q) => <div key={q.question}><dt className="text-lg font-semibold">{q.question}</dt><dd className="mt-2 leading-relaxed text-[var(--l-muted)]">{q.answer}</dd></div>)}</dl></section>
      {guide.sources?.length ? <section id="sources" className="mt-10"><h2 className="text-2xl font-semibold">Sources and further reading</h2><ul className="mt-5 space-y-5">{guide.sources.map(source => <li key={source.url}><a href={source.url} className="font-semibold text-brand-700 underline" {...(source.url.startsWith("https://") ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{source.label}</a>{source.note && <p className="mt-2 text-sm leading-relaxed text-[var(--l-muted)]">{source.note}</p>}</li>)}</ul></section> : null}
      </article><aside className="mt-12 border-t border-[var(--l-line)] pt-8"><h2 className="text-xl font-semibold">Related teacher guides</h2><ul className="mt-4 space-y-3">{relatedTeacherGuides(guide).map((g) => <li key={g.slug}><Link href={`/solutions/${g.slug}`} className="text-brand-700 hover:underline">{g.title}</Link></li>)}</ul><Link href="/pricing" className="mt-6 inline-flex underline">Check current plans and allowances</Link></aside>
    </main><LandingFooter /></div>;
}
