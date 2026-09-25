import { MarketingFooter, MarketingNav } from "@/components/marketing";
import { PricingTable } from "@/components/pricing-table";

export const metadata = { title: "Pricing" };

const faqs = [
  { q: "What is a credit?", a: "Credits measure what you generate. One slide is 1 credit and a worksheet is 4, for example. A full 10-slide lesson with its quiz uses about 13 credits." },
  { q: "Can I cancel any time?", a: "Yes. Cancelling keeps your plan until the end of the billing period, and your lessons and files stay yours." },
  { q: "Is my data safe?", a: "Your uploads are stored privately and never modified. We don't need student personal data, and you can export or delete everything." },
  { q: "Which curricula are supported?", a: "British (UK National Curriculum / IGCSE), CBSE, ICSE, American, IB, UAE MoE and the UAE AI curriculum." },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen">
      <MarketingNav />
      <section className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-semibold tracking-tight text-ink">Simple plans for busy teachers</h1>
          <p className="mx-auto mt-3 max-w-2xl text-muted">Start free. Upgrade when the assistant is saving you hours every week.</p>
        </div>
        <PricingTable />
        <div className="mx-auto mt-16 grid max-w-4xl gap-6 md:grid-cols-2">
          {faqs.map((f) => (
            <div key={f.q} className="rounded-2xl border border-line bg-surface p-5">
              <h3 className="font-semibold text-ink">{f.q}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.a}</p>
            </div>
          ))}
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}
