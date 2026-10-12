import Link from "next/link";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { jsonLd, pageMetadata, SITE_URL } from "@/lib/seo";
import { PUBLIC_BRAND, PUBLIC_SUPPORT_EMAIL, supportEmailFor } from "@/lib/public-support";

export const metadata = pageMetadata("Contact Clastio support", "Contact Clastio by email or an account support ticket for teaching, billing, privacy and school enquiries.", "/contact");
export default function ContactPage() {
  return <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]"><LandingNav />
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd({ "@context": "https://schema.org", "@type": "ContactPage", name: "Contact Clastio", url: `${SITE_URL}/contact`, mainEntity: { "@type": "Organization", "@id": `${SITE_URL}/#organization`, name: PUBLIC_BRAND, url: SITE_URL, contactPoint: { "@type": "ContactPoint", contactType: "customer support", email: PUBLIC_SUPPORT_EMAIL } } }) }} />
    <main id="main-content" className="mx-auto max-w-4xl px-5 py-12 sm:px-8"><h1 className="text-4xl font-semibold tracking-tight">Contact {PUBLIC_BRAND}</h1><p className="mt-5 text-lg text-[var(--l-muted)]">Ask about your account, a teaching resource, billing, privacy or a school pilot.</p>
      <div className="mt-8 grid gap-5 md:grid-cols-2"><section className="rounded-2xl bg-[var(--l-card)] p-6"><h2 className="text-2xl font-semibold">Email support</h2><p className="mt-3 leading-relaxed">Use email if you cannot sign in or need help with a privacy, copyright or school enquiry.</p><a href={supportEmailFor("Clastio support enquiry")} className="mt-5 inline-block break-all text-lg font-semibold underline">{PUBLIC_SUPPORT_EMAIL}</a></section>
      <section className="rounded-2xl bg-[var(--l-card)] p-6"><h2 className="text-2xl font-semibold">Account support</h2><p className="mt-3 leading-relaxed">Signed-in teachers can create a ticket and follow replies in the existing Support area.</p><Link href="/support" className="mt-5 inline-flex rounded-full bg-[#141414] px-5 py-3 font-semibold text-white">Open account support</Link></section></div>
      <section className="mt-9"><h2 className="text-2xl font-semibold">Include the details that help us investigate</h2><p className="mt-3 leading-relaxed text-[var(--l-muted)]">Describe what you were doing, the page, approximate time, and any job, payment or request reference. Remove personal information from screenshots. Do not send passwords, API keys, full payment-card details or identifying student records.</p></section>
      <nav aria-label="Help before contacting support" className="mt-9 grid gap-4 sm:grid-cols-2"><Link href="/help" className="rounded-xl border border-[var(--l-line)] p-4 underline">Help centre</Link><Link href="/status" className="rounded-xl border border-[var(--l-line)] p-4 underline">Service status</Link><Link href="/data-privacy" className="rounded-xl border border-[var(--l-line)] p-4 underline">Privacy requests</Link><Link href="/for-schools" className="rounded-xl border border-[var(--l-line)] p-4 underline">School pilot information</Link></nav>
    </main><LandingFooter /></div>;
}
