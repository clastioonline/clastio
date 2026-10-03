import Link from "next/link";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { teacherGuides } from "@/lib/teacher-guides";
import { pageMetadata } from "@/lib/seo";
export const metadata = pageMetadata("Teaching resources and lesson planning guides for the UAE", "Practical guides to teacher presentations, British and CBSE lesson planning, EAL support, image changes and low-credit PPT editing with Clastio.", "/solutions");
export default function SolutionsPage() {
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav /><main id="main-content" className="mx-auto max-w-6xl px-5 py-14 sm:px-8">
    <p className="text-sm font-semibold text-brand-700">Clastio teacher guides</p><h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight">Solve the planning problems that take time from teaching</h1>
    <p className="mt-5 max-w-3xl text-lg text-[var(--l-muted)]">Find a practical workflow for your next lesson, presentation or classroom adaptation. Start with the teaching goal, discuss the important details, and review the result before class.</p>
    <div className="mt-10 grid gap-5 md:grid-cols-2">{teacherGuides.map((guide) => <article key={guide.slug} className="rounded-2xl bg-[var(--l-card)] p-6 ring-1 ring-black/10"><h2 className="text-xl font-semibold"><Link href={`/solutions/${guide.slug}`} className="focus-ring hover:underline">{guide.title}</Link></h2><p className="mt-3 text-[var(--l-muted)]">{guide.description}</p><Link href={`/solutions/${guide.slug}`} className="mt-5 inline-flex font-semibold text-brand-700">Read the guide →</Link></article>)}</div>
    <Link href="/signup" className="mt-10 inline-flex rounded-full bg-[#141414] px-6 py-3 font-semibold text-white">Start your seven-day trial</Link>
  </main><LandingFooter /></div>;
}
