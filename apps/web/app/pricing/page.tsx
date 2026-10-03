import { LandingFooter, LandingNav } from "@/components/marketing";
import { PricingTable } from "@/components/pricing-table";

export const metadata = { title: "Pricing" };

const faqs = [
  { q: "How does the free trial work?", a: "Every new account starts with a free trial of a paid plan, with no card needed. When it ends you move to the Free plan automatically, and everything you made stays yours. Upgrade from inside the app whenever you're ready." },
  { q: "What is a credit?", a: "Credits measure what you generate. One slide is 1 credit and a worksheet is 4, for example. At the default rates, ten slides plus a quiz use 13 credits; chapter planning and other resources add to that. The app shows current rates before generation." },
  { q: "Can I cancel any time?", a: "Yes. Cancelling keeps your plan until the end of the billing period, and your lessons and files stay yours." },
  { q: "How do I pay?", a: "By card and local payment methods through our payment partner, which handles VAT invoices for you. Schools can ask for an invoice instead." },
  { q: "Is my data safe?", a: "Your uploads are stored privately and never modified. We don't need student personal data, and you can export or delete everything." },
  { q: "Which curricula are supported?", a: "British (UK National Curriculum / IGCSE), CBSE, ICSE, American, IB, UAE MoE and the UAE AI curriculum." },
];

export default function PricingPage() {
  return (
    <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]">
      <div className="bg-[var(--l-hero)] pb-16">
        <LandingNav />
        <div className="mx-auto max-w-3xl px-4 pt-14 text-center sm:px-6">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Simple plans for busy teachers</h1>
          <p className="mx-auto mt-4 max-w-xl text-[var(--l-muted)]">Start a seven-day trial with limited allowances, then choose the plan that fits how much you teach. Prices are in AED; checkout confirms taxes and discounts.</p>
        </div>
      </div>
      <section className="mx-auto -mt-8 max-w-6xl px-4 sm:px-6">
        <PricingTable mode="public" />
        <p className="mt-8 text-center text-sm text-[var(--l-muted)]">Planning a department rollout? Explore a small teacher-led pilot and confirm the account, billing and integration requirements your school needs.</p>
      </section>
      <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6">
        <h2 className="mb-6 text-center text-3xl font-bold tracking-tight">Questions</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {faqs.map((f) => (
            <div key={f.q} className="rounded-3xl bg-[var(--l-card)] p-6">
              <h3 className="font-semibold">{f.q}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-[var(--l-muted)]">{f.a}</p>
            </div>
          ))}
        </div>
      </section>
      <LandingFooter />
    </div>
  );
}
