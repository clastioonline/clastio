"use client";

import {
  ArrowRight,
  Brain,
  CalendarCheck,
  CalendarDays,
  ClipboardList,
  Clock,
  Download,
  FileText,
  ListChecks,
  Palette,
  Plus,
  Presentation,
  Sparkles,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ClassChip, ProjectCard, StatusBadge } from "@/components/common";
import { DocumentDialog } from "@/components/document-dialog";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Progress, Skeleton } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { greeting, useApi, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";

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
    <Card>
      <CardHeader icon={<Brain className="h-5 w-5" />} title="Teacher memory" subtitle="Applied to every lesson"
        action={<Link href="/teacher-memory" className="text-sm font-medium text-brand-600 hover:underline">Manage</Link>} />
      <div className="space-y-3 p-5">
        <div className="flex flex-wrap gap-2">
          {confirmed.map((p: any) => <Badge key={p.key} tone="brand">{p.label}: {prefValue(p.value)}</Badge>)}
          {!confirmed.length && <span className="text-sm text-muted">Tell the assistant how you like to teach in Teacher memory.</span>}
        </div>
        {unconfirmed.map((p: any) => (
          <div key={p.key} className="flex items-center justify-between gap-3 rounded-xl bg-accent-50 px-3 py-2 text-sm">
            <span className="text-ink-2">From your slides: <b>{p.label}</b>: {prefValue(p.value, "–")}. Keep this?</span>
            <Button size="sm" variant="outline" onClick={() => confirm(p.key)}>Keep</Button>
          </div>
        ))}
      </div>
    </Card>
  );
}

function prefValue(v: any, sep = ", ") {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.join(sep);
  return String(v);
}

export default function Dashboard() {
  const { user } = useMe();
  const { t } = useI18n();
  const { notify } = useToast();
  const { data: day, mutate: refreshDay } = useApi<any>("/planner/day");
  const { data: projects } = useApi<any>("/projects?limit=6");
  const { data: templates } = useApi<any>("/templates");
  const { data: classes } = useApi<any>("/classes");
  const [busy, setBusy] = useState<string | null>(null);
  const [docKind, setDocKind] = useState<string | null>(null);

  const preparing = day?.classes?.some((c: any) => c.lesson?.status === "generating");
  useEffect(() => {
    if (!preparing) return;
    const t = setInterval(() => refreshDay(), 2500);
    return () => clearInterval(t);
  }, [preparing, refreshDay]);

  const prepare = async (scope: "today" | "tomorrow" | "week") => {
    setBusy(scope);
    try {
      const r = await api<any>("/planner/prepare", { body: { scope, with_documents: scope === "today" } });
      notify({
        tone: "success",
        title: r.lessons_queued ? `Preparing ${r.lessons_queued} lesson${r.lessons_queued > 1 ? "s" : ""}` : "Everything is already prepared",
        body: r.lessons_queued ? "They'll appear here as each one is ready." : undefined,
      });
      refreshDay();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't prepare", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  const ready = day?.classes?.filter((c: any) => c.lesson?.materials?.pptx).length || 0;
  const total = day?.classes?.length || 0;

  return (
    <div className="space-y-6">
      <div className="ui-hero flex flex-col gap-5 rounded-3xl bg-gradient-to-br from-brand-800 via-brand-600 to-brand-500 p-6 text-white shadow-[var(--shadow-pop)] sm:p-8 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0 lg:flex-1">
          <div className="text-sm text-white/80">{new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">{greeting(user?.name)}{"\u00a0"}👋</h1>
          <p className="mt-2 max-w-xl text-white/80">
            {total ? `${total} class${total > 1 ? "es" : ""} today · ${ready} ready to teach` : "Your teaching assistant is ready when you are."}
          </p>
          {total > 0 && <Progress value={(ready / total) * 100} className="mt-3 h-1.5 max-w-xs bg-white/20" tone="accent" />}
        </div>
        <div className="flex flex-wrap gap-2 lg:max-w-lg lg:justify-end">
          <Button variant="accent" size="lg" loading={busy === "today"} onClick={() => prepare("today")}>
            <WandSparkles className="h-5 w-5" /> {t("dash.prepareToday", "Create today's teaching plan")}
          </Button>
          <Button className="bg-white/15 text-white hover:bg-white/25" size="lg" loading={busy === "tomorrow"} onClick={() => prepare("tomorrow")}>
            {t("dash.prepareTomorrow", "Prepare tomorrow")}
          </Button>
          <Button className="bg-white/15 text-white hover:bg-white/25" size="lg" loading={busy === "week"} onClick={() => prepare("week")}>
            <CalendarCheck className="h-5 w-5" /> {t("dash.prepareWeek", "Prepare my week")}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { href: "/projects/new", icon: Presentation, label: t("dash.createPpt", "Create lessons & PPT") },
          { kind: "worksheet", icon: FileText, label: t("dash.worksheet", "Create worksheet") },
          { kind: "quiz", icon: ClipboardList, label: t("dash.quiz", "Create quiz") },
          { href: "/assistant", icon: Sparkles, label: "Ask the assistant" },
        ].map((a) => {
          const inner = (
            <>
              <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600"><a.icon className="h-5 w-5" /></div>
              <span className="text-sm font-medium text-ink">{a.label}</span>
            </>
          );
          const cls = "focus-ring flex items-center gap-3 rounded-2xl border border-line bg-surface p-4 text-start shadow-[var(--shadow-card)] transition hover:border-brand-200 hover:bg-surface-2/50";
          return a.href ? <Link key={a.label} href={a.href} className={cls}>{inner}</Link> :
            <button key={a.label} className={cls} onClick={() => setDocKind(a.kind!)}>{inner}</button>;
        })}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.7fr_1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<CalendarDays className="h-5 w-5" />} title={t("dash.todayClasses", "Today's classes")}
              subtitle={day?.events?.length ? day.events.map((e: any) => e.title).join(" · ") : undefined}
              action={<Link href="/calendar" className="text-sm font-medium text-brand-600 hover:underline">Week view</Link>} />
            <div className="mt-2"><TodayClasses day={day} onRefresh={refreshDay} /></div>
          </Card>
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-semibold text-ink">{t("dash.recent", "Recent projects")}</h2>
              <Link href="/projects" className="flex items-center gap-1 text-sm font-medium text-brand-600 hover:underline">All projects <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Link>
            </div>
            {!projects ? <div className="grid gap-4 sm:grid-cols-3"><Skeleton className="h-52" /><Skeleton className="h-52" /><Skeleton className="h-52" /></div> :
              projects.items.length ? (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{projects.items.slice(0, 3).map((p: any) => <ProjectCard key={p.id} p={p} />)}</div>
              ) : (
                <EmptyState icon={<Presentation className="h-6 w-6" />} title="No lessons yet" description="Create your first course: pick a topic, number of lessons and slides."
                  action={<Button href="/projects/new"><Plus className="h-4 w-4" /> New course</Button>} />
              )}
          </div>
        </div>
        <div className="space-y-6">
          <ReflectionPrompts />
          <MemoryInsights />
          <Card>
            <CardHeader icon={<Palette className="h-5 w-5" />} title={t("dash.templates", "Your templates")}
              action={<Link href="/templates" className="text-sm font-medium text-brand-600 hover:underline">Manage</Link>} />
            <div className="grid grid-cols-2 gap-3 p-5">
              {(templates?.items || []).slice(0, 4).map((tp: any) => (
                <Link key={tp.id} href={`/templates/${tp.id}`} className="group">
                  <div className="aspect-[16/9] overflow-hidden rounded-lg border border-line bg-surface-2">
                    {tp.previews?.[0] && <img src={tp.previews[0]} alt={tp.name} className="h-full w-full object-cover" />}
                  </div>
                  <div className="mt-1.5 flex items-center gap-1.5 text-xs">
                    <span className="truncate font-medium text-ink group-hover:text-brand-700">{tp.name}</span>
                    {tp.is_default && <Badge tone="success">Default</Badge>}
                  </div>
                </Link>
              ))}
            </div>
          </Card>
          <Card>
            <CardHeader icon={<Download className="h-5 w-5" />} title="Classes" subtitle="Curriculum progress" action={<Link href="/curriculum" className="text-sm font-medium text-brand-600 hover:underline">Open</Link>} />
            <ul className="space-y-2 p-5">
              {(classes?.items || []).map((c: any) => (
                <li key={c.id} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2"><ClassChip name={c.name} color={c.color} /> <span className="text-muted">Grade {c.grade} {c.subject}</span></span>
                  <Badge tone={c.pace === "slower" ? "accent" : "neutral"}>{c.pace} pace</Badge>
                </li>
              ))}
              {!classes?.items?.length && <li className="text-sm text-muted">No classes yet.</li>}
            </ul>
          </Card>
        </div>
      </div>
      <DocumentDialog open={!!docKind} kind={docKind || "worksheet"} onClose={() => setDocKind(null)} />
    </div>
  );
}
