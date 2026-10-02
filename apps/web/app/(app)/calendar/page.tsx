"use client";

import { CalendarCheck, ChevronLeft, ChevronRight, Plus, Trash, Upload } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { ClassChip, StatusBadge } from "@/components/common";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageHeader, Select, Skeleton, Tabs } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { LoadError } from "@/components/load-error";
import { useApi } from "@/lib/hooks";
import { DAYS } from "@/lib/utils";

function addDays(iso: string, n: number) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function WeekView() {
  const { notify } = useToast();
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const { data, error, mutate } = useApi<any>(`/planner/week?start=${start}`);
  const [busy, setBusy] = useState(false);
  const generating = data?.days?.some((d: any) => d.classes.some((c: any) => c.lesson?.status === "generating"));
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(() => mutate(), 2500);
    return () => clearInterval(t);
  }, [generating, mutate]);
  const prepare = async () => {
    setBusy(true);
    try {
      const r = await api<any>("/planner/prepare", { body: { scope: "week" } });
      notify({ tone: "success", title: r.lessons_queued ? `Preparing ${r.lessons_queued} lessons` : "Your week is already prepared" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't prepare", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  if (error) return <LoadError retry={mutate} label="your calendar" />;
  if (!data) return <Skeleton className="h-96" />;
  const first = data.days[0]?.date;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={() => setStart(addDays(first || start, -7))} aria-label="Previous week"><ChevronLeft className="h-4 w-4 rtl:rotate-180" /></Button>
          <Button variant="outline" size="sm" onClick={() => setStart(new Date().toISOString().slice(0, 10))}>This week</Button>
          <Button variant="outline" size="icon" onClick={() => setStart(addDays(first || start, 7))} aria-label="Next week"><ChevronRight className="h-4 w-4 rtl:rotate-180" /></Button>
          <span className="ms-2 text-sm font-medium text-ink">{first && `${formatDate(first)} – ${formatDate(data.days[data.days.length - 1].date)}`}</span>
        </div>
        <Button onClick={prepare} loading={busy}><CalendarCheck className="h-4 w-4" /> Prepare my week</Button>
      </div>
      {!data.days.some((d: any) => d.classes.length) ? (
        <EmptyState title="No timetable yet" description="Add your periods in the Timetable tab so the planner can allocate lessons to each class." />
      ) : (
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
          {data.days.map((d: any) => (
            <Card key={d.date} className="flex flex-col">
              <div className="border-b border-line px-4 py-3">
                <div className="font-semibold text-ink">{d.weekday}</div>
                <div className="text-xs text-muted">{formatDate(d.date)} {d.duration_factor < 1 && <Badge tone="accent" className="ms-1">Short day</Badge>}</div>
              </div>
              <div className="flex-1 space-y-2 p-3">
                {d.holiday && <div className="rounded-lg bg-accent-50 p-3 text-sm text-accent-600">{d.holiday}</div>}
                {d.classes.map((c: any) => (
                  <div key={c.slot_id} className="rounded-xl border border-line p-3">
                    <div className="flex items-center justify-between text-xs text-muted"><span>{c.start}–{c.end}</span><ClassChip name={c.class.name} color={c.class.color} /></div>
                    {c.lesson ? (
                      <Link href={`/lessons/${c.lesson.id}`} className="mt-1.5 block text-sm font-medium text-ink hover:text-brand-700">
                        L{c.lesson.number}: {c.lesson.title}
                      </Link>
                    ) : (
                      <div className="mt-1.5 text-sm text-muted">{c.suggestion?.topic ? `Next: ${c.suggestion.topic}` : "Nothing planned"}</div>
                    )}
                    {c.lesson && <div className="mt-2"><StatusBadge status={c.lesson.status} /></div>}
                  </div>
                ))}
                {!d.holiday && !d.classes.length && <div className="p-2 text-sm text-muted">No classes</div>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function TimetableEditor() {
  const { notify } = useToast();
  const { data: classes } = useApi<any>("/classes");
  const { data, error, mutate } = useApi<any>("/timetable");
  const [slots, setSlots] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (data) setSlots(data.slots); }, [data]);
  const add = () => setSlots([...slots, { class_section_id: classes?.items?.[0]?.id || "", day_of_week: 0, start_time: "08:00", end_time: "08:45", room: "" }]);
  const save = async () => {
    setBusy(true);
    try {
      await api("/timetable", { method: "PUT", body: { slots: slots.map((s) => ({ ...s, room: s.room || null })) } });
      notify({ tone: "success", title: "Timetable saved" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const importCsv = async (f: File) => {
    const form = new FormData();
    form.append("file", f);
    try {
      const r = await api<any>("/timetable/import", { form });
      notify({ tone: "success", title: `Imported ${r.imported} periods` });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Import failed", body: errorMessage(e) });
    }
  };
  if (!classes?.items?.length) return <EmptyState title="Add a class first" description="Create your classes in Classes, then add their periods here." action={<Button href="/curriculum">Add classes</Button>} />;
  const byDay = DAYS.map((_, i) => slots.map((s, idx) => ({ s, idx })).filter(({ s }) => s.day_of_week === i));
  return (
    <Card>
      <CardHeader title="Weekly timetable" subtitle="Periods repeat every week. Holidays and Ramadan timings come from the school calendar."
        action={
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" /> Import CSV</Button>
            <input ref={fileRef} type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])} />
          </div>
        } />
      <div className="space-y-4 p-5">
        {byDay.map((items, day) => items.length ? (
          <div key={day}>
            <div className="mb-2 text-sm font-semibold text-ink">{DAYS[day]}</div>
            <div className="space-y-2">
              {items.map(({ s, idx }) => (
                <div key={idx} className="grid grid-cols-2 gap-2 sm:grid-cols-[1.2fr_1fr_110px_110px_1fr_auto]">
                  <Select value={s.class_section_id} onChange={(e) => setSlots(slots.map((x, j) => j === idx ? { ...x, class_section_id: e.target.value } : x))}>
                    {classes.items.map((c: any) => <option key={c.id} value={c.id}>{c.name} · {c.subject}</option>)}
                  </Select>
                  <Select value={s.day_of_week} onChange={(e) => setSlots(slots.map((x, j) => j === idx ? { ...x, day_of_week: Number(e.target.value) } : x))}>
                    {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
                  </Select>
                  <Input type="time" value={s.start_time} onChange={(e) => setSlots(slots.map((x, j) => j === idx ? { ...x, start_time: e.target.value } : x))} />
                  <Input type="time" value={s.end_time} onChange={(e) => setSlots(slots.map((x, j) => j === idx ? { ...x, end_time: e.target.value } : x))} />
                  <Input placeholder="Room" value={s.room || ""} onChange={(e) => setSlots(slots.map((x, j) => j === idx ? { ...x, room: e.target.value } : x))} />
                  <Button variant="ghost" size="icon" onClick={() => setSlots(slots.filter((_, j) => j !== idx))} aria-label="Remove"><Trash className="h-4 w-4" /></Button>
                </div>
              ))}
            </div>
          </div>
        ) : null)}
        {!slots.length && <p className="text-sm text-muted">No periods yet. Add them one by one or import a CSV with columns: day, start, end, class, subject, grade, room.</p>}
        <div className="flex justify-between border-t border-line pt-4">
          <Button variant="outline" onClick={add}><Plus className="h-4 w-4" /> Add period</Button>
          <Button onClick={save} loading={busy}>Save timetable</Button>
        </div>
      </div>
    </Card>
  );
}

function SchoolCalendar() {
  const { notify } = useToast();
  const { data, error, mutate } = useApi<any>("/calendar/events");
  const [form, setForm] = useState({ kind: "holiday", title: "", start_date: "", end_date: "", duration_factor: 1 });
  const add = async () => {
    try {
      await api("/calendar/events", { body: { ...form, end_date: form.end_date || form.start_date } });
      setForm({ ...form, title: "", start_date: "", end_date: "" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't add", body: errorMessage(e) });
    }
  };
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader title="School calendar" subtitle="Holidays skip lessons; Ramadan and short days shorten them automatically." />
        <ul className="divide-y divide-line">
          {(data?.items || []).map((e: any) => (
            <li key={e.id} className="flex items-center justify-between gap-3 px-5 py-3 text-sm">
              <div>
                <div className="font-medium text-ink">{e.title}</div>
                <div className="text-xs text-muted">{formatDate(e.start_date)}{e.end_date !== e.start_date && ` – ${formatDate(e.end_date)}`} {e.duration_factor < 1 && `· lessons at ${Math.round(e.duration_factor * 100)}% length`}</div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={e.kind === "holiday" ? "accent" : e.kind === "ramadan" ? "brand" : "neutral"}>{e.kind.replace("_", " ")}</Badge>
                {!e.global && <Button variant="ghost" size="icon" onClick={async () => { await api(`/calendar/events/${e.id}`, { method: "DELETE" }); mutate(); }} aria-label="Delete"><Trash className="h-4 w-4" /></Button>}
              </div>
            </li>
          ))}
        </ul>
      </Card>
      <Card className="h-fit p-5">
        <div className="font-semibold text-ink">Add an event</div>
        <div className="mt-4 space-y-3">
          <Field label="Type">
            <Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value, duration_factor: e.target.value === "ramadan" ? 0.75 : e.target.value === "short_day" ? 0.8 : 1 })}>
              <option value="holiday">Holiday</option><option value="ramadan">Ramadan timings</option><option value="short_day">Short day</option><option value="exam">Exams</option><option value="event">Event</option>
            </Select>
          </Field>
          <Field label="Title"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Mid-term break" /></Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="From"><Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
            <Field label="To"><Input type="date" value={form.end_date} onChange={(e) => setForm({ ...form, end_date: e.target.value })} /></Field>
          </div>
          {(form.kind === "ramadan" || form.kind === "short_day") && (
            <Field label="Lesson length" hint="Periods are shortened by this factor">
              <Select value={form.duration_factor} onChange={(e) => setForm({ ...form, duration_factor: Number(e.target.value) })}>
                {[0.6, 0.67, 0.7, 0.75, 0.8, 0.9].map((f) => <option key={f} value={f}>{Math.round(f * 100)}%</option>)}
              </Select>
            </Field>
          )}
          <Button className="w-full" onClick={add} disabled={!form.title || !form.start_date}>Add to calendar</Button>
        </div>
      </Card>
    </div>
  );
}

function CalendarPage() {
  const params = useSearchParams();
  const [tab, setTab] = useState<"week" | "timetable" | "calendar">((params.get("tab") as any) || "week");
  return (
    <div>
      <PageHeader title="Calendar" subtitle="Your week at a glance: what each class is learning next, prepared in advance." />
      <div className="mb-5"><Tabs value={tab} onChange={setTab} tabs={[{ value: "week", label: "Week plan" }, { value: "timetable", label: "Timetable" }, { value: "calendar", label: "School calendar" }]} /></div>
      {tab === "week" && <WeekView />}
      {tab === "timetable" && <TimetableEditor />}
      {tab === "calendar" && <SchoolCalendar />}
    </div>
  );
}

export default function Page() {
  return <Suspense><CalendarPage /></Suspense>;
}
