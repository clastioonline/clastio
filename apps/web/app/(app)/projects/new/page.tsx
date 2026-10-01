"use client";

import { Check, Sparkles, WandSparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, Chips, Field, Input, PageHeader, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { GRADES, SUBJECTS, cn } from "@/lib/utils";

function NewCourse() {
  const router = useRouter();
  const params = useSearchParams();
  const { notify } = useToast();
  const { data: profile } = useApi<any>("/me/profile");
  const { data: classes } = useApi<any>("/classes");
  const { data: templates } = useApi<any>("/templates");
  const [form, setForm] = useState({
    topic: params.get("topic") || "",
    grade: params.get("grade") || "",
    subject: params.get("subject") || "",
    num_lectures: 5,
    slides_per_lecture: 10,
    lecture_minutes: 45,
    language: "en",
    class_section_id: params.get("class") || "",
    template_id: "",
    instructions: "",
    auto_generate: true,
    homework: true,
  });
  const [selected, setSelected] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    setForm((f) => ({
      ...f,
      grade: f.grade || profile.grades?.[0] || "8",
      subject: f.subject || profile.subjects?.[0] || "Science",
      lecture_minutes: profile.class_duration_minutes || 45,
      template_id: f.template_id || profile.default_template_id || "",
      language: profile.teaching_languages?.[0] === "ar" ? "ar" : "en",
    }));
  }, [profile]);
  useEffect(() => {
    if (!form.template_id && templates?.items?.length) setForm((f) => ({ ...f, template_id: templates.items[0].id }));
  }, [templates, form.template_id]);

  const curriculum = profile?.curriculum || "british";
  const { data: outcomes } = useApi<any>(form.subject && form.grade ? `/curricula/${curriculum}/outcomes?subject=${encodeURIComponent(form.subject)}&grade=${form.grade}` : null);
  const cls = classes?.items?.find((c: any) => c.id === form.class_section_id);

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const onClass = (id: string) => {
    const c = classes?.items?.find((x: any) => x.id === id);
    setForm((f) => ({ ...f, class_section_id: id, ...(c ? { grade: c.grade, subject: c.subject } : {}) }));
  };
  const estimate = useMemo(() => form.num_lectures * form.slides_per_lecture + 2, [form.num_lectures, form.slides_per_lecture]);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api<any>("/courses", {
        idempotent: true,
        body: {
          ...form,
          class_section_id: form.class_section_id || null,
          template_id: form.template_id || null,
          instructions: form.instructions || null,
          outcomes: selected.map((o) => ({ code: o.code, text: o.text })),
        },
      });
      notify({ tone: "success", title: "Planning your lessons", body: form.auto_generate ? "You can leave this page. Follow the plan and slides in Activity." : "Review the plan, then generate slides." });
      router.push(`/projects/${r.course.project_id}`);
    } catch (e: any) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow="New course" title="What are you teaching?" subtitle="The planner builds a connected sequence: each lesson introduces new ideas and revisits earlier ones." />
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="space-y-6">
          <Card className="p-5 sm:p-6">
            <div className="space-y-5">
              <Field label="Topic">
                <Input autoFocus value={form.topic} onChange={(e) => set("topic", e.target.value)} placeholder="e.g. Photosynthesis" className="h-12 text-base" />
              </Field>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Class (optional)">
                  <Select value={form.class_section_id} onChange={(e) => onClass(e.target.value)}>
                    <option value="">No specific class</option>
                    {(classes?.items || []).map((c: any) => <option key={c.id} value={c.id}>{c.name} · Grade {c.grade} {c.subject}</option>)}
                  </Select>
                </Field>
                <Field label="Grade">
                  <Select value={form.grade} onChange={(e) => set("grade", e.target.value)}>
                    {GRADES.map((g) => <option key={g} value={g}>{g === "KG" ? "KG" : `Grade ${g}`}</option>)}
                  </Select>
                </Field>
                <Field label="Subject">
                  <Select value={form.subject} onChange={(e) => set("subject", e.target.value)}>
                    {SUBJECTS.map((s) => <option key={s}>{s}</option>)}
                  </Select>
                </Field>
              </div>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Number of lessons">
                  <Select value={form.num_lectures} onChange={(e) => set("num_lectures", Number(e.target.value))}>
                    {[1, 2, 3, 4, 5, 6, 8, 10, 12].map((n) => <option key={n} value={n}>{n} lesson{n > 1 ? "s" : ""}</option>)}
                  </Select>
                </Field>
                <Field label="Slides per lesson">
                  <Select value={form.slides_per_lecture} onChange={(e) => set("slides_per_lecture", Number(e.target.value))}>
                    {[6, 8, 10, 12, 15, 20].map((n) => <option key={n} value={n}>{n} slides</option>)}
                  </Select>
                </Field>
                <Field label="Lesson length">
                  <Select value={form.lecture_minutes} onChange={(e) => set("lecture_minutes", Number(e.target.value))}>
                    {[30, 35, 40, 45, 50, 55, 60, 90].map((n) => <option key={n} value={n}>{n} min</option>)}
                  </Select>
                </Field>
              </div>
              <Field label="Slide language">
                <Chips options={[{ value: "en", label: "English" }, { value: "ar", label: "العربية (Arabic, right-to-left)" }]} value={form.language} onChange={(v) => set("language", v)} />
              </Field>
              <Field label="Anything specific? (optional)" hint="e.g. include a practical on leaf starch testing; students are mostly EAL learners">
                <Textarea value={form.instructions} onChange={(e) => set("instructions", e.target.value)} />
              </Field>
              <div className="divide-y divide-line rounded-xl border border-line px-3">
                <Toggle checked={form.auto_generate} onChange={(v) => set("auto_generate", v)} label="Build the slides straight after planning" description="Turn off to review and edit the lesson sequence first" />
                <Toggle checked={form.homework} onChange={(v) => set("homework", v)} label="End each lesson with homework" />
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Learning outcomes" subtitle={`${curriculum.toUpperCase()} · Grade ${form.grade} ${form.subject} — optional, improves curriculum alignment and coverage tracking`} />
            <div className="max-h-72 space-y-2 overflow-y-auto p-5">
              {(outcomes?.items || []).map((o: any) => {
                const on = selected.some((s) => s.code === o.code);
                return (
                  <button key={o.code} type="button" onClick={() => setSelected(on ? selected.filter((s) => s.code !== o.code) : [...selected, o])}
                    className={cn("focus-ring flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-start text-sm transition-colors",
                      on ? "border-brand-500 bg-brand-50" : "border-line hover:border-brand-200")}>
                    <span className={cn("mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border", on ? "border-brand-600 bg-brand-600 text-white" : "border-line-strong")}>
                      {on && <Check className="h-3 w-3" />}
                    </span>
                    <span><span className="font-medium text-ink">{o.strand}</span> <span className="text-muted">— {o.text}</span>
                      <span className="ms-2 text-xs text-muted">{o.code}</span></span>
                  </button>
                );
              })}
              {outcomes && !outcomes.items.length && <p className="text-sm text-muted">No outcomes loaded for this grade and subject yet. The planner will choose appropriate ones.</p>}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader title="Design" subtitle="Slides use this template" />
            <div className="grid grid-cols-2 gap-3 p-5">
              {(templates?.items || []).map((t: any) => (
                <button key={t.id} type="button" onClick={() => set("template_id", t.id)}
                  className={cn("focus-ring rounded-xl border-2 p-1.5 text-start transition", form.template_id === t.id ? "border-brand-600" : "border-transparent hover:border-line-strong")}>
                  <div className="aspect-[16/9] overflow-hidden rounded-lg bg-surface-2">
                    {t.previews?.[0] && <img src={t.previews[0]} alt="" className="h-full w-full object-cover" />}
                  </div>
                  <div className="mt-1 flex items-center gap-1 px-0.5 text-xs">
                    <span className="truncate font-medium text-ink">{t.name}</span>
                    {!t.builtin && <Badge tone="brand">Yours</Badge>}
                  </div>
                </button>
              ))}
            </div>
            <div className="px-5 pb-5 text-xs text-muted">Want your own design? Upload an old deck in <a href="/templates" className="text-brand-600 underline">My designs</a>.</div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center gap-2 font-semibold text-ink"><Sparkles className="h-4 w-4 text-accent-500" /> You'll get</div>
            <ul className="mt-3 space-y-2 text-sm text-ink-2">
              <li>• {form.num_lectures} connected lessons{cls ? ` for ${cls.name}` : ""}</li>
              <li>• {form.num_lectures * form.slides_per_lecture} editable slides with teacher notes</li>
              <li>• Lesson plans with differentiation (EAL, SEND, stretch)</li>
              <li>• Activities, checks for understanding{form.homework ? " and homework" : ""}</li>
            </ul>
            <div className="mt-3 text-xs text-muted">About {estimate} credits</div>
            {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
            <Button className="mt-4 w-full" size="lg" onClick={submit} loading={busy} disabled={form.topic.trim().length < 2}>
              <WandSparkles className="h-5 w-5" /> {form.auto_generate ? "Plan and build lessons" : "Plan lessons"}
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function NewCoursePage() {
  return (
    <Suspense>
      <NewCourse />
    </Suspense>
  );
}
