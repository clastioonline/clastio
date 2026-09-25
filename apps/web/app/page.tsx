import {
  ArrowRight,
  Brain,
  CalendarCheck,
  ClipboardList,
  Languages,
  MessageCircle,
  Palette,
  ScanEye,
  School,
  ShieldCheck,
  Sparkles,
  Upload,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { MarketingFooter, MarketingNav } from "@/components/marketing";

function SlideMock({ className, title, color, bar, items }: { className?: string; title: string; color: string; bar: string; items: string[] }) {
  return (
    <div className={`absolute aspect-[16/9] w-[340px] overflow-hidden rounded-xl border border-line bg-white shadow-[var(--shadow-pop)] ${className}`}>
      <div className="flex h-[18%] items-center px-4 text-[13px] font-semibold text-white" style={{ background: color }}>{title}</div>
      <div className="h-[2%]" style={{ background: bar }} />
      <div className="space-y-2 p-4">
        {items.map((it, i) => (
          <div key={i} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px] text-slate-700" style={{ background: `${color}14` }}>
            <span className="grid h-4 w-4 place-items-center rounded-full text-[9px] font-bold text-white" style={{ background: color }}>{i + 1}</span>
            {it}
          </div>
        ))}
      </div>
    </div>
  );
}

const steps = [
  { icon: Upload, title: "Upload an old deck", text: "PPTX or PDF. We read your colours, fonts, layouts, logo and header bands straight from the file." },
  { icon: WandSparkles, title: "Ask for a topic", text: "“Photosynthesis, Grade 8, 5 lessons, 10 slides each.” The planner builds a real sequence, not five copies." },
  { icon: ScanEye, title: "Quality-checked slides", text: "Every slide is measured with real font metrics and visually checked, so nothing overflows or overlaps." },
  { icon: CalendarCheck, title: "Teach and reflect", text: "Your day arrives on WhatsApp. One tap after class tells the assistant how it went, and the next lesson adapts." },
];

const features = [
  { icon: Palette, title: "Looks like you made it", text: "Generated decks reuse your own slide master, fonts and decorations. Text, shapes and diagrams stay editable." },
  { icon: Brain, title: "Remembers your classes", text: "Preferences, what each class has covered, misconceptions and reflections feed into every new lesson." },
  { icon: ClipboardList, title: "Everything for the lesson", text: "Lesson plans, teacher notes, worksheets, quizzes, homework and tests, each with a separate answer key." },
  { icon: School, title: "Inspection-ready", text: "Objectives, success criteria, differentiation for EAL learners and students of determination, and assessment for learning." },
  { icon: Languages, title: "Arabic and English", text: "Right-to-left slides and bilingual vocabulary. Supports British, CBSE, American, IB and UAE MoE curricula." },
  { icon: MessageCircle, title: "WhatsApp assistant", text: "Your plan every school morning, and you can ask for tomorrow's lessons with a message." },
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <MarketingNav />
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 end-[-10%] h-[520px] w-[520px] rounded-full bg-brand-200/40 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 start-[-10%] h-[420px] w-[420px] rounded-full bg-accent-100/60 blur-3xl" />
        <div className="relative mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-surface px-3 py-1 text-xs font-medium text-brand-700">
              <Sparkles className="h-3.5 w-3.5 text-accent-500" /> Built for UAE classrooms — ready for India
            </div>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-[3.4rem]">
              Your lessons, your slides, <span className="text-brand-600">your style</span> — prepared while you sleep.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-2">
              AI Teacher Assistant learns your slide design and your classes. It plans connected lessons, builds editable
              PowerPoints in your template and prepares every worksheet, quiz and homework task.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/signup" className="inline-flex h-12 items-center gap-2 rounded-xl bg-brand-600 px-6 font-medium text-white shadow-sm hover:bg-brand-700">
                Start free <ArrowRight className="h-4 w-4 rtl:rotate-180" />
              </Link>
              <Link href="/pricing" className="inline-flex h-12 items-center rounded-xl border border-line-strong bg-surface px-6 font-medium text-ink hover:bg-surface-2">
                See plans
              </Link>
            </div>
            <div className="mt-6 flex items-center gap-2 text-sm text-muted">
              <ShieldCheck className="h-4 w-4 text-success-500" /> No card needed · Your original files are never modified
            </div>
          </div>
          <div className="relative h-[360px] sm:h-[400px]">
            <SlideMock className="start-0 top-2 rotate-[-4deg]" title="Learning objectives" color="#0F766E" bar="#F59E0B"
              items={["Describe photosynthesis", "Name reactants and products", "Explain chlorophyll's role"]} />
            <SlideMock className="end-0 top-24 rotate-[3deg]" title="From sunlight to sugar" color="#1E3A8A" bar="#F97316"
              items={["Light absorbed", "Water split", "CO₂ fixed into glucose"]} />
            <SlideMock className="bottom-0 start-10 rotate-[-1deg]" title="Quick check" color="#7C3AED" bar="#F472B6"
              items={["A) Carbon dioxide", "B) Oxygen ✓", "C) Nitrogen"]} />
          </div>
        </div>
      </section>

      <section id="how" className="border-y border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
          <h2 className="text-center text-3xl font-semibold tracking-tight text-ink">From an old deck to a week of lessons</h2>
          <p className="mx-auto mt-3 max-w-2xl text-center text-muted">Upload once. After that, every lesson, quiz and worksheet comes out in your design system.</p>
          <div className="mt-12 grid gap-6 md:grid-cols-4">
            {steps.map((s, i) => (
              <div key={s.title} className="relative rounded-2xl border border-line bg-canvas p-5">
                <div className="absolute -top-3 start-5 rounded-full bg-brand-600 px-2 py-0.5 text-xs font-semibold text-white">Step {i + 1}</div>
                <s.icon className="mt-2 h-6 w-6 text-brand-600" />
                <h3 className="mt-3 font-semibold text-ink">{s.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted">{s.text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="features" className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <h2 className="text-3xl font-semibold tracking-tight text-ink">Not another generic slide generator</h2>
        <p className="mt-3 max-w-2xl text-muted">Built around how teachers actually work: your timetable, your classes, your curriculum and the way you like to teach.</p>
        <div className="mt-10 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((f) => (
            <div key={f.title} className="rounded-2xl border border-line bg-surface p-6 shadow-[var(--shadow-card)]">
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600"><f.icon className="h-5 w-5" /></div>
              <h3 className="mt-4 font-semibold text-ink">{f.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="schools" className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <div className="grid items-center gap-8 overflow-hidden rounded-3xl bg-brand-700 p-8 text-white sm:p-12 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <h2 className="text-3xl font-semibold tracking-tight">For departments and schools</h2>
            <p className="mt-3 max-w-xl text-brand-100">
              Shared school templates, schemes of work and question banks, curriculum coverage reports and SSO, with a data-processing
              agreement aligned with UAE PDPL.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <Link href="/signup" className="rounded-xl bg-white px-5 py-3 font-medium text-brand-700 hover:bg-brand-50">Try it yourself</Link>
            <Link href="/pricing" className="rounded-xl border border-white/30 px-5 py-3 font-medium text-white hover:bg-white/10">School pricing</Link>
          </div>
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}
