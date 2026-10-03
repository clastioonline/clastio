"use client";

import {
  ArrowRight,
  Atom,
  BookOpen,
  Calculator,
  CalendarCheck,
  CircleCheck,
  Clock,
  Cpu,
  FlaskConical,
  Languages,
  MousePointer2,
  Plus,
  ScanEye,
  ShieldCheck,
  Upload,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type CSSProperties, type ReactNode } from "react";
import { ProductVideo } from "@/components/product-video";
import { LandingDetails } from "@/components/landing-details";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { cn } from "@/lib/utils";
import { teacherGuides } from "@/lib/teacher-guides";

/* Landing page. Warm neutral canvas, one playful headline, bold colour tiles with scalloped edges.
   Every number on this page is a product fact, not a marketing claim. */

type Chip = { label: string; icon: typeof Atom; bg: string; tag: string; pos: string; line?: string; cursor?: "start" | "end" };
const CHIPS: Chip[] = [
  { label: "Science 8A", icon: FlaskConical, bg: "#fde047", tag: "bg-[#3b5bdb] text-white", pos: "start-[4%] top-[14%]", cursor: "end" },
  { label: "Maths 7C", icon: Calculator, bg: "#7fd18f", tag: "bg-[var(--l-card)] text-[var(--l-ink)]", pos: "start-[16%] top-[46%]" },
  { label: "English 9B", icon: BookOpen, bg: "#fbcab8", tag: "bg-[var(--l-card)] text-[var(--l-ink)]", pos: "start-[4%] top-[76%]" },
  { label: "Physics 10", icon: Atom, bg: "#93b4ff", tag: "bg-[var(--l-card)] text-[var(--l-ink)]", pos: "end-[4%] top-[14%]" },
  { label: "Arabic 6A", icon: Languages, bg: "#ffb86b", tag: "bg-[var(--l-card)] text-[var(--l-ink)]", pos: "end-[16%] top-[46%]" },
  { label: "Computing 8", icon: Cpu, bg: "#c4b5fd", tag: "bg-[#1b7446] text-white", pos: "end-[4%] top-[76%]", cursor: "start" },
];

function ClassChip({ c }: { c: Chip }) {
  return (
    <div className={cn("absolute hidden items-center gap-2 lg:flex", c.pos, c.pos.startsWith("end") && "flex-row-reverse")}>
      <div className="grid h-16 w-16 place-items-center rounded-full border-4 border-[var(--l-card)] shadow-lg" style={{ background: c.bg }}>
        <c.icon className="h-7 w-7 text-[#141414]" aria-hidden />
      </div>
      <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium shadow-sm", c.tag)}>{c.label}</span>
      {c.cursor && <MousePointer2 className={cn("h-5 w-5 fill-current", c.cursor === "end" ? "-mt-8 text-[#3b5bdb]" : "-mt-8 -scale-x-100 text-[#1b7446]")} aria-hidden />}
    </div>
  );
}

/* Colour tile whose top edge is a row of bumps, like pills standing side by side. */
function BumpTile({ color, children, className, bumps = 4, dark = false }: { color: string; children: ReactNode; className?: string; bumps?: number; dark?: boolean }) {
  return (
    <div className={cn("relative mt-7 rounded-b-[2rem] rounded-t-none p-6 pt-4", dark ? "text-white" : "text-[#141414]", className)} style={{ background: color }}>
      <div className="absolute inset-x-0 -top-7 flex" aria-hidden>
        {Array.from({ length: bumps }).map((_, i) => (
          <span key={i} className="h-14 flex-1 rounded-t-full" style={{ background: color }} />
        ))}
      </div>
      <div className="relative">{children}</div>
    </div>
  );
}

function Tile({ color, children, className, dark = false }: { color: string; children: ReactNode; className?: string; dark?: boolean }) {
  return (
    <div className={cn("rounded-[2rem] p-6", dark ? "text-white" : "text-[#141414]", className)} style={{ background: color }}>
      {children}
    </div>
  );
}

function MiniSlide({ title, color, bar, items, className, style }: { title: string; color: string; bar: string; items: string[]; className?: string; style?: CSSProperties }) {
  return (
    <div className={cn("aspect-[16/9] w-full overflow-hidden rounded-xl bg-white shadow-lg ring-1 ring-black/5", className)} style={style}>
      <div className="flex h-[20%] items-center px-3 text-[11px] font-semibold text-white" style={{ background: color }}>{title}</div>
      <div className="h-[2.5%]" style={{ background: bar }} />
      <div className="space-y-1.5 p-3">
        {items.map((it, i) => (
          <div key={it} className="flex items-center gap-1.5 rounded px-1.5 py-1 text-[9px] text-slate-700" style={{ background: `${color}14` }}>
            <span className="grid h-3.5 w-3.5 place-items-center rounded-full text-[8px] font-bold text-white" style={{ background: color }}>{i + 1}</span>
            {it}
          </div>
        ))}
      </div>
    </div>
  );
}

function Pill({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-full bg-white/95 py-1.5 pe-1.5 ps-4 text-sm text-[#141414] shadow-sm">
      {label}
      <span className={cn("flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium", tone)}><Clock className="h-3 w-3" />{value}</span>
    </div>
  );
}

const CHECKS = [
  "Know exactly what each class has covered",
  "Carry unfinished content into the next lesson",
  "Plan around holidays, short days and Ramadan timings",
  "Get tomorrow's plan on WhatsApp before school",
];

const STEPS = [
  { icon: Upload, title: "Upload an old deck", text: "PPTX or PDF. Your colours, fonts, layouts, logo and header bands are read straight from the file." },
  { icon: WandSparkles, title: "Ask for a topic", text: "“Photosynthesis, Grade 8, 5 lessons, 10 slides each.” You get a connected sequence, not five copies." },
  { icon: ScanEye, title: "Quality-checked", text: "Slides are checked for layout issues, giving you a starting point to review before teaching." },
  { icon: CalendarCheck, title: "Teach and reflect", text: "One tap after class says how it went, and the next lesson adapts." },
];

export default function Landing() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const start = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/signup${email ? `?email=${encodeURIComponent(email)}` : ""}`);
  };

  return (
    <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]">
      {/* ------------------------------------------------------------------ hero */}
      <section className="relative bg-[var(--l-hero)] pb-24">
        <LandingNav />
        <div className="relative mx-auto max-w-6xl px-4 pt-14 sm:px-6 lg:pt-20">
          {CHIPS.map((c) => <ClassChip key={c.label} c={c} />)}
          <svg className="pointer-events-none absolute inset-0 hidden h-full w-full lg:block" aria-hidden preserveAspectRatio="none" viewBox="0 0 100 100">
            <path d="M8 24 V52 H18 M8 56 V82 H18 M92 24 V52 H82 M92 56 V82 H82" fill="none" stroke="var(--l-muted)" strokeWidth="0.15" strokeDasharray="0.8 0.8" vectorEffect="non-scaling-stroke" style={{ strokeWidth: 1.2 }} />
          </svg>
          <div className="relative mx-auto max-w-3xl text-center">
            <h1 className="text-[2.6rem] font-bold leading-[1.08] tracking-tight sm:text-6xl">
              Plan <MousePointer2 className="inline h-9 w-9 -translate-y-1 fill-[#7ed321] text-[#5aa516] sm:h-12 sm:w-12" aria-hidden />{" "}
              <span className="relative inline-block">
                Teach
                <svg className="absolute -bottom-2 start-0 w-full" viewBox="0 0 200 14" aria-hidden><path d="M3 9 C 50 2, 150 2, 197 7 M20 12 C 80 6, 140 7, 190 11" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" /></svg>
              </span>
              <br />and Shine with
              <br />
              <span className="relative mt-2 inline-block rounded-md bg-[#fbcab8] px-3 text-[#141414]">
                Clastio
                <span className="absolute -end-4 -top-4 rounded-md bg-[#e0440e] px-2 py-0.5 text-xs font-medium tracking-normal text-white sm:-end-10 sm:text-sm">AI slides</span>
                <span className="absolute -end-1 top-1 bottom-1 w-1 rounded bg-[#e0440e]" aria-hidden />
              </span>
            </h1>
            <p className="mx-auto mt-7 max-w-xl text-base leading-relaxed text-[var(--l-muted)] sm:text-lg">
              Connected lessons, editable PowerPoints in your own design, worksheets and quizzes, prepared for every class you teach.
            </p>
            <form onSubmit={start} className="mx-auto mt-8 flex max-w-md items-center gap-2 rounded-full bg-[var(--l-card)] p-1.5 shadow-lg ring-1 ring-black/5">
              <label htmlFor="hero-email" className="sr-only">Your school email</label>
              <input id="hero-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@school.ae"
                className="min-w-0 flex-1 bg-transparent px-4 text-sm text-[var(--l-ink)] outline-none placeholder:text-[var(--l-muted)]" />
              <button type="submit" className="flex h-11 shrink-0 items-center gap-2 rounded-full bg-[#141414] ps-5 pe-1.5 text-sm font-medium text-white hover:bg-black">
                Get started <span className="grid h-8 w-8 place-items-center rounded-full bg-white text-[#141414]"><ArrowRight className="h-4 w-4 rtl:rotate-180" /></span>
              </button>
            </form>
            <div className="mt-4 flex items-center justify-center gap-2 text-sm text-[var(--l-muted)]">
              <ShieldCheck className="h-4 w-4 text-[#1b7446]" /> Free to start · No card needed · Your original files are never modified
            </div>
          </div>
        </div>
        {/* Scalloped lower edge */}
        <div className="absolute inset-x-0 bottom-0 flex translate-y-1/2" aria-hidden>
          {Array.from({ length: 6 }).map((_, i) => <span key={i} className="aspect-square flex-1 rounded-full bg-[var(--l-hero)]" style={{ maxHeight: "11rem" }} />)}
        </div>
      </section>

      {/* ------------------------------------------------------------------ facts */}
      <section id="features" className="relative mx-auto max-w-6xl px-4 pt-40 sm:px-6 lg:pt-48">
        <div className="grid gap-6 lg:grid-cols-2 lg:items-end">
          <h2 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">Unlock time in<br />every lesson</h2>
          <p className="max-w-md text-[var(--l-muted)] lg:justify-self-end">
            Upload one deck you've taught with. From then on, every lesson, quiz and worksheet comes out in your design, planned
            around your classes and your curriculum.
          </p>
        </div>
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          <div className="flex flex-col gap-5">
            <BumpTile color="#3b5bdb" dark>
              <div className="text-6xl font-bold tracking-tight">19</div>
              <div className="mt-2 text-sm">Slide layouts, all editable in PowerPoint</div>
            </BumpTile>
            <Tile color="#ff6b35">
              <div className="text-6xl font-bold tracking-tight">50</div>
              <div className="mt-2 text-sm">Slides from one request: 5 lessons × 10 slides</div>
            </Tile>
          </div>
          <div className="relative min-h-[22rem] overflow-hidden rounded-[2rem] bg-[#e9e2d0] p-6">
            <MiniSlide title="Learning objectives" color="#0F766E" bar="#F59E0B" items={["Describe photosynthesis", "Name reactants and products", "Explain chlorophyll's role"]}
              className="absolute start-6 top-8 w-[78%] -rotate-3" />
            <MiniSlide title="From sunlight to sugar" color="#1E3A8A" bar="#F97316" items={["Light absorbed", "Water split", "CO₂ fixed into glucose"]}
              className="absolute end-5 top-[38%] w-[74%] rotate-2" />
            <MiniSlide title="Quick check" color="#7C3AED" bar="#F472B6" items={["A) Carbon dioxide", "B) Oxygen ✓", "C) Nitrogen"]}
              className="absolute bottom-6 start-8 w-[70%] -rotate-1" />
          </div>
          <div className="flex flex-col gap-5">
            <Tile color="#7fd18f">
              <div className="text-6xl font-bold tracking-tight">6</div>
              <div className="mt-2 text-sm">Document types: worksheets, quizzes, homework, tests, lesson plans and guides</div>
            </Tile>
            <BumpTile color="#fde047">
              <div className="text-6xl font-bold tracking-tight">2</div>
              <div className="mt-2 text-sm">Languages, English and Arabic, with right-to-left slides</div>
            </BumpTile>
          </div>
        </div>
      </section>

      {/* ------------------------------------------------------------------ progress */}
      <section id="how" className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-24 sm:px-6 lg:grid-cols-2">
        <div className="relative">
          <div className="rounded-[2rem] bg-gradient-to-br from-[#1b7446] to-[#0f3d26] p-6 pb-14 text-white shadow-xl">
            <div className="flex items-center justify-between text-sm text-white/80"><span>Grade 8 Science · 8A</span><span>This week</span></div>
            <div className="mt-3 text-2xl font-semibold">Photosynthesis</div>
            <div className="mt-5 grid h-44 grid-cols-5 items-end gap-2" aria-hidden>
              {[90, 115, 140, 70, 55].map((h, i) => (
                <div key={i} className="flex flex-col items-center gap-1.5">
                  <div className={cn("w-9 rounded-full", i < 3 ? "bg-white/90" : "bg-white/25")} style={{ height: `${h}px` }} />
                  <span className="text-xs text-white/70">L{i + 1}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-white/70">Lessons 1–3 taught, 4–5 prepared</p>
          </div>
          <div className="-mt-8 ms-auto w-[88%] space-y-2 rounded-[1.5rem] bg-[var(--l-card)] p-4 shadow-lg ring-1 ring-black/5">
            <Pill label="Lesson length" value="45 min" tone="bg-[#fde047] text-[#141414]" />
            <Pill label="Carried over" value="10 min" tone="bg-[#7fd18f] text-[#141414]" />
            <Pill label="Next: Respiration" value="Thu" tone="bg-[#ff6b35] text-[#141414]" />
          </div>
        </div>
        <div>
          <h2 className="text-4xl font-bold leading-tight tracking-tight sm:text-5xl">Keep every class on track</h2>
          <p className="mt-4 max-w-lg text-[var(--l-muted)]">
            Your timetable, school calendar and after-class reflections decide what comes next, so each class moves at its own pace.
          </p>
          <ul className="mt-6 space-y-3">
            {CHECKS.map((c) => <li key={c} className="flex items-center gap-3"><CircleCheck className="h-5 w-5 shrink-0 fill-[#e0440e] text-white" aria-hidden />{c}</li>)}
          </ul>
        </div>
      </section>

      {/* ------------------------------------------------------------------ workflow */}
      <section className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
        <h2 className="text-center text-4xl font-bold leading-tight tracking-tight sm:text-5xl">Streamline your planning,<br />boost your teaching</h2>
        <div className="mt-14 grid gap-6 md:grid-cols-3">
          {STEPS.slice(0, 3).map((s, i) => (
            <div key={s.title}>
              <div className={cn("relative grid aspect-[4/3] place-items-center overflow-hidden rounded-[2rem] p-6", ["bg-[#fbcab8]", "bg-[#93b4ff]", "bg-[#7fd18f]"][i])}>
                {i === 0 && <div className="w-full space-y-2"><Pill label="Upload" value="science.pptx" tone="bg-[#fde047] text-[#141414]" /><Pill label="Colours & fonts" value="found" tone="bg-[#7fd18f] text-[#141414]" /><Pill label="Logo & footer" value="kept" tone="bg-[#ff6b35] text-[#141414]" /></div>}
                {i === 1 && (
                  <div className="grid w-[82%] place-items-center gap-2 rounded-2xl border-2 border-dashed border-[#3b5bdb] bg-white/90 p-6 text-[#141414]">
                    <span className="grid h-10 w-10 place-items-center rounded-full bg-[#3b5bdb] text-white"><Plus className="h-5 w-5" /></span>
                    <span className="font-medium">Add new lesson</span>
                  </div>
                )}
                {i === 2 && <MiniSlide title="Key vocabulary" color="#0F766E" bar="#F59E0B" items={["Chlorophyll", "Glucose", "Stomata"]} className="w-[86%]" />}
              </div>
              <h3 className="mt-5 text-xl font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--l-muted)]">{s.text}</p>
            </div>
          ))}
        </div>
      </section>

      <ProductVideo />
      <LandingDetails />
      <section className="mx-auto max-w-6xl px-5 py-14" aria-labelledby="teacher-guides-heading">
        <h2 id="teacher-guides-heading" className="text-3xl font-semibold">Practical answers for your next lesson</h2>
        <p className="mt-3 text-[var(--l-muted)]">Explore UAE lesson planning, EAL support, curriculum workflows and ways to edit a PPT without rebuilding everything.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{teacherGuides.filter((_, i) => [0, 1, 6, 7, 8, 12].includes(i)).map((guide) => <Link key={guide.slug} href={`/solutions/${guide.slug}`} className="focus-ring rounded-2xl bg-[var(--l-card)] p-5 ring-1 ring-black/10 hover:ring-brand-600"><h3 className="font-semibold">{guide.title}</h3><p className="mt-2 text-sm text-[var(--l-muted)]">{guide.description}</p></Link>)}</div>
        <Link href="/solutions" className="mt-6 inline-flex font-semibold text-brand-700">All teacher guides →</Link>
      </section>

      {/* ------------------------------------------------------------------ schools */}
      <section id="schools" className="mx-auto max-w-6xl px-4 pb-20 sm:px-6">
        <div className="grid items-center gap-8 rounded-[2rem] bg-[#141414] p-8 text-white sm:p-12 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">For departments and schools</h2>
            <p className="mt-3 max-w-xl text-white/70">
              Explore reusable designs, connected lesson planning and classroom resources for your department. Confirm account access, enabled integrations and data-handling requirements before rolling out across your school.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 lg:justify-end">
            <Link href="/signup" className="rounded-full bg-white px-6 py-3 font-medium text-[#141414] hover:bg-white/90">Try it yourself</Link>
            <Link href="/for-schools" className="rounded-full border border-white/30 px-6 py-3 font-medium text-white hover:bg-white/10">Explore a school pilot</Link>
          </div>
        </div>
      </section>
      <LandingFooter />
    </div>
  );
}
