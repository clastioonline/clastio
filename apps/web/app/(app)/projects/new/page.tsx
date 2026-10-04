"use client";

import { Check, Sparkles, WandSparkles } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { TeacherImages, type TeacherImage } from "@/components/teacher-images";
import { ChapterSources } from "@/components/chapter-sources";
import { TemplatePreview } from "@/components/template-preview";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, Chips, Field, Input, PageHeader, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { GRADES, SUBJECTS, cn } from "@/lib/utils";

function NewCourse() {
  const router = useRouter();
  const params = useSearchParams();
  const { notify } = useToast();
  const { data: creditInfo } = useApi<any>("/usage/estimates");
  const { data: profile } = useApi<any>("/me/profile");
  const { data: teacherMemory } = useApi<any>("/memory");
  const imageChoiceTouched = useRef(false);
  useEffect(() => {
    if (!teacherMemory || imageChoiceTouched.current) return;
    const saved = teacherMemory.preferences?.find((p: any) => p.key === "preferred_image_source" && p.confirmed);
    if (saved && ["hybrid", "ai", "stock"].includes(saved.value)) setForm((f) => ({...f, image_mode: saved.value}));
  }, [teacherMemory]);
  const { data: classes } = useApi<any>("/classes");
  const [form, setForm] = useState({
    topic: params.get("topic") || "",
    grade: params.get("grade") || "",
    subject: params.get("subject") || "",
    num_lectures: 5,
    slides_per_lecture: 10,
    lecture_minutes: 45,
    language: "en",
    class_section_id: params.get("class") || "",
    template_id: params.get("template") || "",
    instructions: "",
    auto_generate: true,
    homework: true,
    chapter_mode: "complete",
    source_file_ids: [] as string[],
    teacher_images: [] as TeacherImage[],
    previous_taught: "",
    revision_needed: "",
    image_mode: "hybrid",
    writing_style: "natural",
  });
  const templateQuery = new URLSearchParams();
  if (form.subject) templateQuery.set("subject", form.subject);
  if (form.grade) templateQuery.set("grade", form.grade);
  if (form.language) templateQuery.set("language", form.language);
  if (form.class_section_id) templateQuery.set("class_id", form.class_section_id);
  const { data: templates, error: templateError, mutate: refreshTemplates } = useApi<any>(`/templates?${templateQuery}`);
  const [showAllDesigns, setShowAllDesigns] = useState(false);
  const briefApplied = useRef<string | null>(null);
  const briefId = params.get("brief");
  const { data: briefConversation, error: briefError } = useApi<any>(briefId ? `/assistant/conversations/${briefId}` : null);
  useEffect(() => {
    if (!briefId || !briefConversation || briefApplied.current === briefId) return;
    const latest = [...(briefConversation.messages || [])].reverse().find((m: any) => m.role === "assistant");
    const action = latest?.actions?.find((a: any) => a.type === "ppt_brief");
    if (!action) return;
    const b = action.brief;
    setForm((f) => ({...f, topic: b.topic, grade: b.grade, subject: b.subject, language: b.language, num_lectures: b.num_lectures, slides_per_lecture: b.slides_per_lecture, lecture_minutes: b.lecture_minutes, instructions: b.instructions, writing_style: b.writing_style, image_mode: b.image_mode || "hybrid", auto_generate: false}));
    imageChoiceTouched.current = true;
    briefApplied.current = briefId;
  }, [briefId, briefConversation]);
  const [selected, setSelected] = useState<any[]>([]);
  const [sourcesBlocked, setSourcesBlocked] = useState(false);
  const [imagesBlocked, setImagesBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profile) return;
    setForm((f) => ({
      ...f,
      grade: f.grade || profile.grades?.[0] || "",
      subject: f.subject || profile.subjects?.[0] || "",
      lecture_minutes: briefId ? f.lecture_minutes : profile.class_duration_minutes || 45,
      template_id: f.template_id || profile.default_template_id || "",
      language: briefId ? f.language : profile.teaching_languages?.[0] === "ar" ? "ar" : "en",
    }));
  }, [profile, briefId]);
  useEffect(() => {
    if (!profile || form.template_id || !templates?.items?.length) return;
    const preferred = templates.items.find((t: any) => t.is_default) || templates.items.find((t: any) => t.status === "ready");
    if (preferred) setForm((f) => ({ ...f, template_id: f.template_id || preferred.id }));
  }, [templates, form.template_id, profile]);

  const designItems = [...(templates?.items || [])].filter((t: any) => t.status === "ready").sort((a: any, b: any) =>
    Number(b.is_default) - Number(a.is_default) || (b.recommendation?.score || 0) - (a.recommendation?.score || 0));
  const visibleDesigns = showAllDesigns ? designItems : designItems.filter((t: any, i: number) => i < 6 || t.id === form.template_id);
  const selectedDesign = designItems.find((t: any) => t.id === form.template_id);

  const cls = classes?.items?.find((c: any) => c.id === form.class_section_id);
  const curriculum = cls?.curriculum || profile?.curriculum || "british";
  const { data: outcomes } = useApi<any>(form.subject && form.grade ? `/curricula/${curriculum}/outcomes?subject=${encodeURIComponent(form.subject)}&grade=${form.grade}` : null);

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }));
  const onClass = (id: string) => {
    const c = classes?.items?.find((x: any) => x.id === id);
    setForm((f) => ({ ...f, class_section_id: id, ...(c ? { grade: c.grade, subject: c.subject } : {}) }));
  };
  const estimate = creditInfo ? creditInfo.costs.course_plan + (form.auto_generate && form.chapter_mode !== "parts" ? (form.chapter_mode === "daily" ? 1 : form.num_lectures) * form.slides_per_lecture * creditInfo.costs.slide : 0) : null;

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
          previous_taught: form.previous_taught || null,
          revision_needed: form.revision_needed || null,
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
      <Link href="/assistant?mode=playground" className="mb-4 inline-flex text-sm font-semibold text-brand-700">Discuss your PPT in the playground →</Link>
      {briefId && <Alert tone={briefError ? "warn" : "brand"} title={briefError ? "Could not load your PPT draft" : "Review your playground brief"}>Check the content, attach your source material and adjust the settings before creating your chapter.</Alert>}
      <PageHeader eyebrow="New chapter" title="What chapter are you teaching?" subtitle="The planner builds a connected sequence: each lesson introduces new ideas and revisits earlier ones." />
      <div className="grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <div className="min-w-0 space-y-6">
          <ChapterSources value={form.source_file_ids} onChange={(ids) => set("source_file_ids", ids)} onBlocked={setSourcesBlocked} />
          <TeacherImages value={form.teacher_images} onChange={(images) => set("teacher_images", images)} onBlocked={setImagesBlocked} />
          <Card className="p-5 sm:p-6">
            <div className="space-y-5">
              <Field label="Chapter / topic">
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
                  <Select aria-label="Grade" value={form.grade} onChange={(e) => set("grade", e.target.value)}>
                    {GRADES.map((g) => <option key={g} value={g}>{g === "KG" ? "KG" : `Grade ${g}`}</option>)}
                  </Select>
                </Field>
                <Field label="Subject">
                  <Select aria-label="Subject" value={form.subject} onChange={(e) => set("subject", e.target.value)}>
                    {SUBJECTS.map((s) => <option key={s}>{s}</option>)}
                  </Select>
                </Field>
              </div>
              <Field label="How would you like to prepare this chapter?">
                <Select data-tour="chapter-mode" aria-label="How would you like to prepare this chapter?" value={form.chapter_mode} onChange={(e) => set("chapter_mode", e.target.value)}>
                  <option value="complete">Complete chapter — build all lesson parts together</option>
                  <option value="parts">In parts — review the plan and choose lessons to build</option>
                  <option value="daily">Day by day — build lesson 1 now, prepare the next after teaching</option>
                </Select>
              </Field>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Number of lessons">
                  <Select aria-label="Number of lessons" value={form.num_lectures} onChange={(e) => set("num_lectures", Number(e.target.value))}>
                    {[1, 2, 3, 4, 5, 6, 8, 10, 12].map((n) => <option key={n} value={n}>{n} lesson{n > 1 ? "s" : ""}</option>)}
                  </Select>
                </Field>
                <Field label="Slides per lesson">
                  <Select aria-label="Slides per lesson" value={form.slides_per_lecture} onChange={(e) => set("slides_per_lecture", Number(e.target.value))}>
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
              <Field label="What have you already taught? (optional)" hint="Describe the previous class so the chapter starts at the right point.">
                <Textarea data-tour="chapter-revision" value={form.previous_taught} maxLength={2000} onChange={(e) => set("previous_taught", e.target.value)} placeholder="Yesterday we covered opposite, adjacent and hypotenuse. Students practised identifying the sides." />
              </Field>
              <Field label="What needs revision? (optional)" hint="The next lesson will include a focused recap and a worked example.">
                <Textarea value={form.revision_needed} maxLength={2000} onChange={(e) => set("revision_needed", e.target.value)} placeholder="Revise choosing sin, cos or tan. Students still confuse opposite and adjacent." />
              </Field>
              <Field label="PPT version">
                <div role="group" aria-label="PPT version" className="grid grid-cols-2 gap-2 rounded-2xl bg-surface-2 p-1.5">
                  {[{value: "standard", label: "AI"}, {value: "natural", label: "Humanize"}].map((mode) => (
                    <button key={mode.value} type="button" aria-pressed={form.writing_style === mode.value}
                      onClick={() => setForm((f) => ({...f, writing_style: mode.value}))}
                      className={`focus-ring rounded-xl px-4 py-3 text-sm font-semibold transition ${form.writing_style === mode.value ? "bg-brand-800 text-white shadow-sm" : "text-muted hover:bg-surface hover:text-ink"}`}>
                      {mode.label}
                    </button>
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted">{form.writing_style === "natural"
                  ? "Natural teacher voice with concrete examples and varied slides. Text is AI-assisted and editable."
                  : "Standard AI lesson structure. Choose your image source below."}</p>
              </Field>
              <Field label="Image source" hint="Hybrid searches licensed internet images first, then generates if needed within your AI image allowance. Attribution is retained. With no allowance, a placeholder may be used.">
                <Select value={form.image_mode} onChange={(e) => { imageChoiceTouched.current = true; set("image_mode", e.target.value); }}>
                  <option value="hybrid">Hybrid — search first, generate if needed</option>
                  <option value="stock">Licensed stock only — no AI image cost</option>
                  <option value="ai">AI images</option>
                </Select>
              </Field>
              <Field label="Anything specific? (optional)" hint="e.g. include a practical on leaf starch testing; students are mostly EAL learners">
                <Textarea value={form.instructions} onChange={(e) => set("instructions", e.target.value)} />
              </Field>
              <div className="divide-y divide-line rounded-xl border border-line px-3">
                <Toggle checked={form.auto_generate} onChange={(v) => set("auto_generate", v)} label={form.chapter_mode === "daily" ? "Build the first lesson after planning" : form.chapter_mode === "parts" ? "Review the plan before building selected parts" : "Build all chapter parts after planning"} description="Turn off to plan first. In parts mode, choose what to build from the chapter page." />
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

        <div className="min-w-0 space-y-6">
          <Card>
            <CardHeader title="Design" subtitle="Suggestions follow this lesson's subject, grade and selected class curriculum" />
            {templateError && <div className="px-5"><Alert tone="danger">Could not load designs. <Button size="sm" variant="outline" onClick={() => refreshTemplates()}>Try again</Button></Alert></div>}
            <div className="grid grid-cols-2 gap-3 p-5">
              {visibleDesigns.map((t: any) => (
                <button key={t.id} type="button" aria-label={`Use ${t.name}`} aria-pressed={form.template_id === t.id} onClick={() => set("template_id", t.id)}
                  className={cn("focus-ring min-w-0 rounded-xl border-2 p-1.5 text-start transition", form.template_id === t.id ? "border-brand-600" : "border-transparent hover:border-line-strong")}>
                  <TemplatePreview src={t.previews?.[0]} name={t.name} />
                  <div className="mt-1 flex flex-wrap items-center gap-1 px-0.5 text-xs">
                    <span className="min-w-0 max-w-full truncate font-medium text-ink">{t.name}</span>
                    {!t.builtin && <Badge tone="brand">Yours</Badge>}
                    {t.is_default ? <Badge tone="success">Default</Badge> : t.recommendation && <Badge tone="brand">Suggested</Badge>}
                  </div>
                </button>
              ))}
            </div>
            {designItems.length > 6 && <div className="px-5 pb-3"><Button size="sm" variant="ghost" onClick={() => setShowAllDesigns(!showAllDesigns)}>{showAllDesigns ? "Show fewer designs" : `Show all ${designItems.length} designs`}</Button></div>}
            {selectedDesign && <div className="mx-5 mb-4 rounded-xl bg-brand-50 p-3 text-xs leading-relaxed text-brand-800"><p className="font-semibold">Selected: {selectedDesign.name}</p><p className="mt-1">{selectedDesign.recommendation?.reason || selectedDesign.description || "Your selected presentation design."}</p></div>}
            <div className="px-5 pb-5 text-xs text-muted">Want your own design? Upload an old deck in <a href="/templates" className="text-brand-600 underline">My designs</a>.</div>
          </Card>
          <Card className="p-5">
            <div className="flex items-center gap-2 font-semibold text-ink"><Sparkles className="h-4 w-4 text-accent-500" /> You'll get</div>
            <ul className="mt-3 space-y-2 text-sm text-ink-2">
              <li>• {form.num_lectures} connected lessons{cls ? ` for ${cls.name}` : ""}</li>
              <li>• {!form.auto_generate || form.chapter_mode === "parts" ? "Review the plan, then build the parts you choose" : form.chapter_mode === "daily" ? `${form.slides_per_lecture} editable slides for day 1; prepare later parts after class` : `${form.num_lectures * form.slides_per_lecture} editable slides with teacher notes`}</li>
              <li>• Lesson plans with differentiation (EAL, SEND, stretch)</li>
              <li>• Activities, checks for understanding{form.homework ? " and homework" : ""}</li>
            </ul>
            <div className="mt-3 text-xs text-muted">{estimate === null ? "Loading credit estimate…" : `About ${estimate} credits`}
              {creditInfo && <p className="mt-1">{creditInfo.remaining === null ? "Unlimited plan credits" : `${creditInfo.remaining} credits available`} · Resets {new Date(creditInfo.reset_at).toLocaleDateString()}</p>}</div>
            {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
            <Button className="mt-4 w-full" size="lg" onClick={submit} loading={busy} disabled={form.topic.trim().length < 2 || !form.grade || !form.subject || sourcesBlocked || imagesBlocked}>
              <WandSparkles className="h-5 w-5" /> {form.auto_generate && form.chapter_mode !== "parts" ? form.chapter_mode === "daily" ? "Plan chapter & build first lesson" : "Plan & build complete chapter" : "Plan chapter"}
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
