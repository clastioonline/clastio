"use client";

import {
  ArrowRight,
  CalendarCheck,
  CalendarDays,
  Check,
  Clock,
  FileText,
  GraduationCap,
  ListChecks,
  Pause,
  Play,
  Plus,
  Presentation,
  Square,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ActivityOverview } from "@/components/activity-center";
import { ClassChip, StatusBadge } from "@/components/common";
import { DashHeader, HalfDonut, KpiCard, Legend, Panel, PillButton, PillChart } from "@/components/dash";
import { DocumentDialog } from "@/components/document-dialog";
import { LoadError } from "@/components/load-error";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Skeleton } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { greeting, useApi, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { SETUP_STEPS } from "@/lib/tutorials";
import { cn } from "@/lib/utils";

function TodayClasses({ day, onRefresh }: { day: any; onRefresh: () => void }) {
  const { t } = useI18n();
  if (!day) return <div className="space-y-3 p-5"><Skeleton className="h-20" /><Skeleton className="h-20" /></div>;
  if (day.holiday) {
    return <div className="p-5"><EmptyState icon={<CalendarDays className="h-6 w-6" />} title={day.holiday} description="No classes today. Enjoy the break!" /></div>;
  }
  if (!day.classes.length) {
    return (
      <div className="p-5">
        <EmptyState icon={<CalendarDays className="h-6 w-6" />} title="No classes on your timetable today"
          description="Add your timetable so the assistant knows what to prepare each day."
          action={<Button href="/calendar" variant="outline">Set up timetable</Button>} />
      </div>
    );
  }
  return (
    <ul className="divide-y divide-line">
      {day.classes.map((c: any) => (
        <li key={c.slot_id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center">
          <div className="flex w-24 shrink-0 items-center gap-2 text-sm font-medium text-ink tabular-nums">
            <Clock className="h-4 w-4 text-muted" />{c.start}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <ClassChip name={c.class.name} color={c.class.color} />
              <span className="text-sm text-muted">{c.class.subject} · {c.minutes} min</span>
              {day.duration_factor < 1 && <Badge tone="accent">Short day</Badge>}
            </div>
            {c.lesson ? (
              <div className="mt-1.5">
                <div className="font-medium text-ink">{c.course.topic} — Lesson {c.lesson.number}: {c.lesson.title}</div>
                {c.lesson.carry_over?.text && <div className="mt-1 text-xs text-accent-600">↪ {c.lesson.carry_over.text}</div>}
              </div>
            ) : (
              <div className="mt-1.5 text-sm text-muted">
                {c.suggestion?.topic ? <>Nothing planned. Suggested next: <span className="font-medium text-ink">{c.suggestion.topic}</span></> : c.suggestion?.reason}
              </div>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {c.lesson ? (
              <>
                <StatusBadge status={c.lesson.status} />
                <Button size="sm" variant="outline" href={`/lessons/${c.lesson.id}`}>{t("common.open", "Open")}</Button>
              </>
            ) : (
              <Button size="sm" variant="outline"
                href={`/projects/new?class=${c.class.id}&topic=${encodeURIComponent(c.suggestion?.topic || "")}&grade=${c.class.grade}&subject=${encodeURIComponent(c.class.subject)}`}>
                <Plus className="h-4 w-4" /> Plan lessons
              </Button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}

function ReflectionPrompts() {
  const { data, mutate } = useApi<any>("/lessons?status=generated&limit=30");
  const { notify } = useToast();
  const today = new Date().toISOString().slice(0, 10);
  const due = (data?.items || []).filter((l: any) => l.scheduled_date && l.scheduled_date < today).slice(0, 3);
  if (!due.length) return null;
  const reflect = async (id: string, outcome: string) => {
    try {
      const r = await api(`/lessons/${id}/reflection`, { body: { outcome } });
      notify({ tone: "success", title: "Thanks — noted", body: r.effects?.join(" ") || "Your next lesson will take this into account." });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };
  return (
    <Card>
      <CardHeader icon={<ListChecks className="h-5 w-5" />} title="How did it go?" subtitle="One tap helps the assistant pace your next lessons." />
      <ul className="space-y-3 p-5">
        {due.map((l: any) => (
          <li key={l.id} className="rounded-xl border border-line p-3">
            <div className="text-sm font-medium text-ink">{l.topic} · L{l.number}: {l.title}</div>
            <div className="text-xs text-muted">{formatDate(l.scheduled_date, { weekday: "short", day: "numeric", month: "short" })}</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {[["went_well", "✅ Went well"], ["ran_out_of_time", "⏱ Ran out of time"], ["struggled", "😕 Struggled"], ["skipped", "⏭ Skipped"]].map(([k, label]) => (
                <Button key={k} size="sm" variant="outline" onClick={() => reflect(l.id, k)}>{label}</Button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function prefValue(v: any, sep = ", ") {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.join(sep);
  return String(v);
}

function MemoryInsights() {
  const { data, mutate } = useApi<any>("/memory?limit=5");
  if (!data) return <Skeleton className="h-40" />;
  const unconfirmed = data.preferences.filter((p: any) => !p.confirmed).slice(0, 2);
  const confirmed = data.preferences.filter((p: any) => p.confirmed).slice(0, 5);
  const confirm = async (key: string) => {
    await api(`/memory/preferences/${key}/confirm`, { method: "POST" });
    mutate();
  };
  return (
    <Panel title="Teacher memory" action={<Link href="/teacher-memory" className="text-sm font-semibold text-brand-600 hover:underline">Manage</Link>}>
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2">
          {confirmed.map((p: any) => <Badge key={p.key} tone="brand">{p.label}: {prefValue(p.value)}</Badge>)}
          {!confirmed.length && <span className="text-sm text-muted">Tell Clastio how you like to teach in Teacher memory.</span>}
        </div>
        {unconfirmed.map((p: any) => (
          <div key={p.key} className="flex items-center justify-between gap-3 rounded-2xl bg-accent-50 px-3 py-2 text-sm">
            <span className="text-ink-2">From your slides: <b>{p.label}</b>: {prefValue(p.value, "–")}. Keep this?</span>
            <Button size="sm" variant="outline" onClick={() => confirm(p.key)}>Keep</Button>
          </div>
        ))}
      </div>
    </Panel>
  );
}

/* Getting-started checklist with links into the tutorials. Hidden once complete or dismissed. */
function GettingStarted({ checklist }: { checklist: Record<string, boolean> }) {
  const [hidden, setHidden] = useState(true);
  useEffect(() => {
    try { setHidden(localStorage.getItem("clastio-hide-getting-started") === "1"); } catch { setHidden(false); }
  }, []);
  const done = SETUP_STEPS.filter((s) => checklist[s.check!]).length;
  if (hidden || done === SETUP_STEPS.length) return null;
  const next = SETUP_STEPS.find((s) => !checklist[s.check!]);
  return (
    <section className="rounded-3xl bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold text-brand-600"><GraduationCap className="h-4 w-4" /> Getting started · {done} of {SETUP_STEPS.length} done</div>
          <h2 className="mt-1 text-xl font-semibold text-ink">Set up Clastio in about 10 minutes</h2>
          <div className="mt-3 h-2 w-64 max-w-full overflow-hidden rounded-full bg-surface-2"><div className="h-full rounded-full bg-brand-600" style={{ width: `${(done / SETUP_STEPS.length) * 100}%` }} /></div>
        </div>
        <div className="flex items-center gap-2">
          {next && <PillButton href={next.href}>{next.cta} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></PillButton>}
          <Button variant="ghost" size="sm" onClick={() => { try { localStorage.setItem("clastio-hide-getting-started", "1"); } catch {} setHidden(true); }}>Hide</Button>
        </div>
      </div>
      <ol className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
        {SETUP_STEPS.map((s, i) => {
          const ok = checklist[s.check!];
          return (
            <li key={s.id}>
              <Link href={ok ? s.href : `/tutorials#${s.id}`} className={cn("flex h-full items-start gap-3 rounded-2xl border p-3 transition hover:border-brand-300",
                ok ? "border-transparent bg-brand-50" : "border-line")}>
                <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-full text-sm font-semibold",
                  ok ? "bg-brand-600 text-white" : "bg-surface-2 text-ink-2")}>{ok ? <Check className="h-4 w-4" /> : i + 1}</span>
                <span className="min-w-0">
                  <span className={cn("block text-sm font-medium", ok ? "text-ink-2 line-through decoration-brand-300" : "text-ink")}>{s.title}</span>
                  <span className="text-xs text-muted">{ok ? "Done" : `${s.minutes} min guide`}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function NextClass({ n }: { n: any }) {
  if (!n) {
    return (
      <Panel title="Next class" className="flex flex-col">
        <p className="text-muted">Add your timetable and your next class will show here, with its lesson ready to open.</p>
        <div className="mt-auto pt-5"><PillButton href="/calendar?tab=timetable" variant="outline">Add timetable</PillButton></div>
      </Panel>
    );
  }
  return (
    <Panel title="Next class" className="flex flex-col">
      <div className="text-2xl font-bold leading-snug tracking-tight text-brand-700">
        {n.class.name} {n.class.subject}
        {n.lesson && <span className="block text-lg font-semibold text-ink">{n.course?.topic} · L{n.lesson.number}: {n.lesson.title}</span>}
      </div>
      <p className="mt-2 text-muted">{n.is_today ? "Today" : new Date(n.date).toLocaleDateString(undefined, { weekday: "long" })} · {n.start} – {n.end}</p>
      {!n.lesson && n.suggestion?.topic && <p className="mt-2 text-sm text-ink-2">Nothing planned yet. Suggested: <b>{n.suggestion.topic}</b></p>}
      <div className="mt-auto pt-5">
        {n.lesson ? (
          <PillButton href={`/lessons/${n.lesson.id}`}><Presentation className="h-5 w-5" /> Open lesson</PillButton>
        ) : (
          <PillButton href={`/projects/new?class=${n.class.id}&topic=${encodeURIComponent(n.suggestion?.topic || "")}&grade=${n.class.grade}&subject=${encodeURIComponent(n.class.subject)}`}><Plus className="h-5 w-5" /> Plan lessons</PillButton>
        )}
      </div>
    </Panel>
  );
}

const LESSON_ICON_COLORS = ["#1b7446", "#3b5bdb", "#e0440e", "#7c3aed", "#0f766e"];

function Upcoming({ items }: { items: any[] }) {
  return (
    <Panel title="Upcoming lessons" action={<Link href="/projects/new" className="inline-flex h-9 items-center gap-1 rounded-full border-2 border-brand-700 px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"><Plus className="h-4 w-4" />New</Link>}>
      {items.length ? (
        <ul className="space-y-4">
          {items.map((l, i) => (
            <li key={l.id}>
              <Link href={l.status === "generated" ? `/lessons/${l.id}` : `/projects/${l.project_id}`} className="group flex items-start gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl text-white" style={{ background: LESSON_ICON_COLORS[i % LESSON_ICON_COLORS.length] }}>
                  <Presentation className="h-5 w-5" />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-ink group-hover:text-brand-700">{l.topic} · L{l.number}</span>
                  <span className="block truncate text-xs text-muted">
                    {l.scheduled_date ? `Teach on ${formatDate(l.scheduled_date, { day: "numeric", month: "short" })}` : `Grade ${l.grade} ${l.subject}`} · {l.status === "generated" ? "ready" : l.status === "generating" ? "building" : "to build"}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">No lessons waiting. Create a unit and it will show here.</p>
      )}
    </Panel>
  );
}

const STATUS_BADGE: Record<string, { label: string; tone: any }> = {
  ready: { label: "Ready", tone: "success" }, in_progress: { label: "Building", tone: "accent" }, pending: { label: "To plan", tone: "danger" },
};

function Classes({ items }: { items: any[] }) {
  return (
    <Panel title="Your classes" action={<Link href="/curriculum" className="inline-flex h-9 items-center gap-1 rounded-full border-2 border-brand-700 px-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"><Plus className="h-4 w-4" />Add class</Link>}>
      {items.length ? (
        <ul className="space-y-4">
          {items.map((c) => (
            <li key={c.id} className="flex items-center gap-3">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-sm font-bold text-white" style={{ background: c.color || "#1b7446" }}>{c.name}</span>
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium text-ink">Grade {c.grade} {c.subject}</div>
                <div className="truncate text-xs text-muted">{c.next_lesson ? <>Next: <span className="font-medium text-ink-2">{c.topic} · L{c.next_lesson.number} {c.next_lesson.title}</span></> : c.topic ? `${c.topic} finished` : "No unit yet"}</div>
              </div>
              <Badge tone={STATUS_BADGE[c.status].tone} className="shrink-0">{STATUS_BADGE[c.status].label}</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">Add your classes so each one keeps its own pace and progress.</p>
      )}
    </Panel>
  );
}

function Coverage({ c }: { c: any }) {
  const pct = c.total ? Math.round((c.taught / c.total) * 100) : 0;
  return (
    <Panel title="Curriculum coverage">
      {c.total ? (
        <>
          <HalfDonut total={c.total} center={`${pct}%`} caption="outcomes taught"
            segments={[{ label: "Taught", value: c.taught, className: "text-brand-600" }, { label: "In progress", value: c.in_progress, className: "text-brand-800" }, { label: "Planned", value: c.planned, className: "text-brand-300" }]} />
          <Legend items={[{ label: "Taught", className: "bg-brand-600", value: c.taught }, { label: "In progress", className: "bg-brand-800", value: c.in_progress }, { label: "Planned", className: "bg-brand-300", value: c.planned }, { label: "Not yet", striped: true, value: c.total - c.taught - c.in_progress - c.planned }]} />
        </>
      ) : (
        <p className="text-sm text-muted">Coverage appears once your classes have curriculum outcomes. Add classes with a grade and subject to start.</p>
      )}
    </Panel>
  );
}

/* A class timer: counts up, survives page changes, pause and stop. */
function LessonTimer() {
  const KEY = "clastio-timer";
  const [state, setState] = useState<{ start: number | null; acc: number }>({ start: null, acc: 0 });
  const [, tick] = useState(0);
  useEffect(() => {
    try { const s = JSON.parse(localStorage.getItem(KEY) || "null"); if (s) setState(s); } catch {}
  }, []);
  useEffect(() => {
    if (!state.start) return;
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, [state.start]);
  const save = (s: typeof state) => { setState(s); try { localStorage.setItem(KEY, JSON.stringify(s)); } catch {} };
  const elapsed = Math.floor((state.acc + (state.start ? Date.now() - state.start : 0)) / 1000);
  const hh = String(Math.floor(elapsed / 3600)).padStart(2, "0");
  const mm = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return (
    <section className="ui-hero relative flex flex-col overflow-hidden rounded-3xl bg-brand-800 p-6 text-white">
      <h2 className="text-lg font-semibold sm:text-xl">Lesson timer</h2>
      <div className="my-6 text-center text-5xl font-bold tabular-nums tracking-tight" aria-live="off">{hh}:{mm}:{ss}</div>
      <div className="mt-auto flex justify-center gap-3">
        {state.start ? (
          <button onClick={() => save({ start: null, acc: state.acc + (Date.now() - state.start!) })} aria-label="Pause timer" className="grid h-14 w-14 place-items-center rounded-full bg-white text-brand-800 hover:bg-white/90"><Pause className="h-6 w-6 fill-current" /></button>
        ) : (
          <button onClick={() => save({ start: Date.now(), acc: state.acc })} aria-label="Start timer" className="grid h-14 w-14 place-items-center rounded-full bg-white text-brand-800 hover:bg-white/90"><Play className="h-6 w-6 fill-current" /></button>
        )}
        <button onClick={() => save({ start: null, acc: 0 })} aria-label="Stop and reset timer" className="grid h-14 w-14 place-items-center rounded-full bg-danger-500 text-white hover:brightness-110"><Square className="h-5 w-5 fill-current" /></button>
      </div>
    </section>
  );
}

export default function Dashboard() {
  const { user } = useMe();
  const { notify } = useToast();
  const { data, error: dashboardError, mutate } = useApi<any>("/me/dashboard");
  const { data: day, error: dayError, mutate: refreshDay } = useApi<any>("/planner/day");
  const [busy, setBusy] = useState<string | null>(null);
  const [docKind, setDocKind] = useState<string | null>(null);

  const building = (data?.kpis?.building || 0) > 0 || day?.classes?.some((c: any) => c.lesson?.status === "generating");
  useEffect(() => {
    if (!building) return;
    const t = setInterval(() => { mutate(); refreshDay(); }, 3000);
    return () => clearInterval(t);
  }, [building, mutate, refreshDay]);

  const prepare = async (scope: "today" | "week") => {
    setBusy(scope);
    try {
      const r = await api<any>("/planner/prepare", { body: { scope, with_documents: scope === "today" } });
      notify({
        tone: "success",
        title: r.lessons_queued ? `Preparing ${r.lessons_queued} lesson${r.lessons_queued > 1 ? "s" : ""}` : "Everything is already prepared",
        body: r.lessons_queued ? "They'll appear here as each one is ready." : undefined,
      });
      mutate();
      refreshDay();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't prepare", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const k = data?.kpis;
  return (
    <div className="space-y-5">
      <DashHeader title="Dashboard" subtitle={`${greeting(user?.name)}. Plan, prepare and teach with ease.`}
        actions={<>
          <PillButton href="/projects/new"><Plus className="h-5 w-5" /> New lessons</PillButton>
          <PillButton variant="outline" onClick={() => prepare("week")} disabled={busy === "week"}>
            <CalendarCheck className="h-5 w-5" /> {busy === "week" ? "Preparing…" : "Prepare my week"}
          </PillButton>
        </>} />
      <ActivityOverview />

      {dashboardError ? <LoadError retry={mutate} label="your dashboard" /> : !data ? <Skeleton className="h-40 rounded-3xl" /> : (
        <>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard hero label="Lessons prepared" value={k.total} trend={k.new_this_month || null} hint={k.new_this_month ? "new this month" : "Create your first unit"} href="/projects" />
            <KpiCard label="Ready to teach" value={k.ready} hint="PowerPoints ready to open" href="/lessons" />
            <KpiCard label="Taught" value={k.taught} hint="with reflections recorded" href="/calendar" />
            <KpiCard label="On the way" value={k.building + k.pending} hint={k.building ? `${k.building} building now` : "waiting to be built"} href="/projects" />
          </div>

          <GettingStarted checklist={data.checklist} />

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
            <Panel title="Lessons prepared this week" className="xl:col-span-6">
              <PillChart unit="lessons" points={data.week.map((d: any) => ({ label: d.label.slice(0, 1), value: d.value, future: d.future, highlight: d.today, title: `${d.label}: ${d.value} lesson${d.value === 1 ? "" : "s"}` }))} />
            </Panel>
            <div className="xl:col-span-3"><NextClass n={data.next_class} /></div>
            <div className="xl:col-span-3"><Upcoming items={data.upcoming} /></div>
            <div className="xl:col-span-5"><Classes items={data.classes} /></div>
            <div className="xl:col-span-4"><Coverage c={data.coverage} /></div>
            <div className="xl:col-span-3"><LessonTimer /></div>
          </div>
        </>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <section className="rounded-3xl bg-surface xl:col-span-7">
          <div className="flex items-center justify-between px-6 pt-6">
            <h2 className="text-lg font-semibold text-ink sm:text-xl">Today's classes</h2>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" loading={busy === "today"} onClick={() => prepare("today")}><WandSparkles className="h-4 w-4" /> Prepare today</Button>
              <Link href="/calendar" className="inline-flex h-8 items-center text-sm font-semibold text-brand-600 hover:underline">Week view</Link>
            </div>
          </div>
          {dayError ? <div className="p-5"><LoadError retry={refreshDay} label="today’s classes" /></div> : <TodayClasses day={day?.days?.[0] ?? day} onRefresh={refreshDay} />}
        </section>
        <div className="space-y-5 xl:col-span-5">
          <ReflectionPrompts />
          <MemoryInsights />
          <Panel title="Quick create">
            <div className="grid grid-cols-2 gap-3">
              {[["worksheet", "Worksheet"], ["quiz", "Quiz"], ["homework", "Homework"], ["assessment", "Test"]].map(([kind, label]) => (
                <button key={kind} onClick={() => setDocKind(kind)} className="focus-ring flex items-center gap-2 rounded-2xl border border-line px-4 py-3 text-sm font-medium text-ink hover:border-brand-300 hover:bg-brand-50">
                  <FileText className="h-4 w-4 text-brand-600" /> {label}
                </button>
              ))}
            </div>
          </Panel>
        </div>
      </div>
      <DocumentDialog open={!!docKind} kind={docKind || "worksheet"} onClose={() => setDocKind(null)} />
    </div>
  );
}
