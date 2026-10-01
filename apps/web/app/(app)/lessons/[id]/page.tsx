"use client";

import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Download,
  FileText,
  LoaderCircle,
  RotateCcw,
  Save,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { StatusBadge } from "@/components/common";
import { DocumentDialog, DocumentFiles } from "@/components/document-dialog";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, Select, Skeleton, Tabs, Textarea } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";
import { LAYOUT_LABELS, cn } from "@/lib/utils";

const ACTIONS = [
  { key: "simpler", label: "Make simpler" },
  { key: "more_visual", label: "More visual" },
  { key: "add_examples", label: "Add examples" },
  { key: "reduce_text", label: "Reduce text" },
  { key: "add_activity", label: "Turn into activity" },
  { key: "harder", label: "Stretch the most able" },
  { key: "another_version", label: "Another version" },
];

function toLines(xs: string[] | undefined) {
  return (xs || []).join("\n");
}

function SlideEditor({ lessonId, slide, onJob }: { lessonId: string; slide: any; onJob: (id: string) => void }) {
  const { notify } = useToast();
  const s = slide.spec;
  const [title, setTitle] = useState(s.title);
  const [subtitle, setSubtitle] = useState(s.subtitle || "");
  const [bullets, setBullets] = useState(s.bullets.map((b: any) => (b.level ? "  - " : "") + b.text).join("\n"));
  const [steps, setSteps] = useState(s.steps.map((st: any) => (st.detail ? `${st.label}: ${st.detail}` : st.label)).join("\n"));
  const [question, setQuestion] = useState(s.quiz?.question || s.question || "");
  const [options, setOptions] = useState(toLines(s.quiz?.options));
  const [answer, setAnswer] = useState(s.quiz?.answer_index ?? 0);
  const [notes, setNotes] = useState(s.speaker_notes || "");
  const [instruction, setInstruction] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const { data: versions, mutate: refreshVersions } = useApi<any>(`/lessons/${lessonId}/slides/${slide.number}/versions`);

  useEffect(() => {
    setTitle(s.title);
    setSubtitle(s.subtitle || "");
    setBullets(s.bullets.map((b: any) => (b.level ? "  - " : "") + b.text).join("\n"));
    setSteps(s.steps.map((st: any) => (st.detail ? `${st.label}: ${st.detail}` : st.label)).join("\n"));
    setQuestion(s.quiz?.question || s.question || "");
    setOptions(toLines(s.quiz?.options));
    setAnswer(s.quiz?.answer_index ?? 0);
    setNotes(s.speaker_notes || "");
    refreshVersions();
  }, [slide.id, slide.version]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setBusy("save");
    const patch: any = { title, speaker_notes: notes };
    if (s.subtitle !== null || subtitle) patch.subtitle = subtitle || null;
    if (s.bullets.length || ["concept", "summary", "objectives", "homework", "exit_ticket", "image_text", "discussion"].includes(s.layout)) {
      patch.bullets = bullets.split("\n").filter((l: string) => l.trim()).map((l: string) => ({ text: l.replace(/^\s*-\s*/, "").trim(), level: /^\s+-/.test(l) ? 1 : 0 }));
    }
    if (s.steps.length) {
      patch.steps = steps.split("\n").filter((l: string) => l.trim()).map((l: string) => {
        const [label, ...rest] = l.split(":");
        return { label: label.trim(), detail: rest.join(":").trim() };
      });
    }
    if (s.quiz) patch.quiz = { ...s.quiz, question, options: options.split("\n").filter((o: string) => o.trim()), answer_index: Number(answer) };
    else if (s.question !== null && s.question !== undefined) patch.question = question;
    try {
      const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}`, { method: "PATCH", body: { spec: patch } });
      onJob(r.job_id);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const regenerate = async (action?: string) => {
    setBusy(action || "custom");
    try {
      const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}/regenerate`, { body: { action, instruction: action ? undefined : instruction } });
      onJob(r.job_id);
      setInstruction("");
    } catch (e) {
      notify({ tone: "error", title: "Couldn't regenerate", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const restore = async (version: number) => {
    const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}/restore`, { body: { version } });
    onJob(r.job_id);
  };

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Quick changes (keeps your design)</div>
        <div className="flex flex-wrap gap-2">
          {ACTIONS.map((a) => (
            <Button key={a.key} size="sm" variant="outline" loading={busy === a.key} disabled={!!busy} onClick={() => regenerate(a.key)}>{a.label}</Button>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <Input value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="Or describe a change… e.g. use a camel example" />
          <Button onClick={() => regenerate()} disabled={!instruction.trim() || !!busy} loading={busy === "custom"}><WandSparkles className="h-4 w-4" /></Button>
        </div>
      </div>
      <div className="space-y-3 border-t border-line pt-5">
        <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        {(s.layout === "cover" || s.layout === "section" || s.layout === "activity" || s.subtitle) && (
          <Field label="Subtitle"><Input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} /></Field>
        )}
        {(s.quiz || s.question) && <Field label="Question"><Textarea className="min-h-[60px]" value={question} onChange={(e) => setQuestion(e.target.value)} /></Field>}
        {s.quiz && (
          <>
            <Field label="Options (one per line)"><Textarea className="min-h-[90px]" value={options} onChange={(e) => setOptions(e.target.value)} /></Field>
            <Field label="Correct answer">
              <Select value={answer} onChange={(e) => setAnswer(Number(e.target.value))}>
                {options.split("\n").filter((o) => o.trim()).map((o, i) => <option key={i} value={i}>{"ABCD"[i]}) {o}</option>)}
              </Select>
            </Field>
          </>
        )}
        {(s.bullets.length > 0 || ["concept", "summary", "objectives", "homework", "exit_ticket", "image_text"].includes(s.layout)) && (
          <Field label="Bullets (one per line, start with ‘  - ’ to indent)"><Textarea className="min-h-[120px]" value={bullets} onChange={(e) => setBullets(e.target.value)} /></Field>
        )}
        {s.steps.length > 0 && <Field label="Steps (Label: detail)"><Textarea className="min-h-[110px]" value={steps} onChange={(e) => setSteps(e.target.value)} /></Field>}
        {s.columns.length > 0 && <Alert tone="neutral">Columns: {s.columns.map((c: any) => c.heading).join(" · ")} — use a quick change or an instruction to rewrite them.</Alert>}
        <Field label="Speaker notes"><Textarea className="min-h-[100px]" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <div className="flex items-center justify-between gap-2">
          {versions?.items?.length > 1 ? (
            <Select className="max-w-[60%]" value="" onChange={(e) => e.target.value && restore(Number(e.target.value))}>
              <option value="">Version history ({versions.items.length})</option>
              {versions.items.slice(1).map((v: any) => <option key={v.version} value={v.version}>v{v.version} · {v.reason || "edit"} · {formatDate(v.created_at, { hour: "2-digit", minute: "2-digit" })}</option>)}
            </Select>
          ) : <span />}
          <Button onClick={save} loading={busy === "save"} disabled={!!busy && busy !== "save"}><Save className="h-4 w-4" /> Save & rebuild</Button>
        </div>
      </div>
    </div>
  );
}

function LessonPlanView({ plan }: { plan: any }) {
  if (!plan) return <EmptyState title="No lesson plan yet" />;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader title="Objectives & success criteria" />
        <div className="space-y-3 p-5 text-sm">
          <ul className="space-y-1 text-ink-2">{plan.objectives.map((o: string) => <li key={o}>• {o}</li>)}</ul>
          <ul className="space-y-1 text-muted">{plan.success_criteria.map((o: string) => <li key={o}>✓ {o}</li>)}</ul>
        </div>
      </Card>
      <Card>
        <CardHeader title={`Timings · ${plan.duration_minutes} minutes`} />
        <div className="space-y-2 p-5">
          {plan.phases.map((p: any) => (
            <div key={p.name} className="flex gap-3 rounded-xl bg-surface-2 p-3 text-sm">
              <div className="w-20 shrink-0 font-medium capitalize text-ink">{p.name}<div className="text-xs text-muted">{p.minutes} min</div></div>
              <div className="text-ink-2">{p.description}<div className="mt-0.5 text-xs text-muted">Teacher: {p.teacher_actions} · Students: {p.student_actions}</div></div>
            </div>
          ))}
        </div>
      </Card>
      <Card>
        <CardHeader title="Differentiation" />
        <dl className="grid gap-2 p-5 text-sm">
          {[["Support", plan.differentiation.support], ["Core", plan.differentiation.core], ["Stretch", plan.differentiation.extension],
            ["EAL learners", plan.differentiation.eal], ["Students of determination", plan.differentiation.send]].map(([k, v]) => (
            <div key={k} className="grid grid-cols-[140px_1fr] gap-2"><dt className="font-medium text-ink">{k}</dt><dd className="text-ink-2">{v}</dd></div>
          ))}
        </dl>
      </Card>
      <Card>
        <CardHeader title="Questions & misconceptions" />
        <div className="space-y-3 p-5 text-sm">
          {plan.questions_to_ask.map((q: any) => (
            <div key={q.question}><span className="font-medium text-ink">{q.question}</span> <Badge>{q.bloom_level}</Badge><div className="text-muted">Expected: {q.expected_response}</div></div>
          ))}
          {plan.misconceptions.map((m: any) => (
            <div key={m.misconception} className="rounded-lg bg-accent-50 px-3 py-2"><b>Misconception:</b> {m.misconception}<div className="text-muted">→ {m.correction}</div></div>
          ))}
          <div><b>Homework:</b> {plan.homework.task} ({plan.homework.estimated_minutes} min)</div>
        </div>
      </Card>
    </div>
  );
}

export default function LessonPage() {
  const { id } = useParams<{ id: string }>();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(`/lessons/${id}`);
  const [tab, setTab] = useState<"slides" | "plan" | "documents" | "qc">("slides");
  const [current, setCurrent] = useState(1);
  const [jobId, setJobId] = useState<string | null>(null);
  const [docOpen, setDocOpen] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);
  const [regenText, setRegenText] = useState("");
  const job = useJob(jobId || (["queued", "running"].includes(data?.job?.status) ? data.job.id : null), (j) => {
    setJobId(null);
    mutate();
    if (j.status === "succeeded") notify({ tone: "success", title: "Slides updated", body: "Your design system was preserved." });
    else notify({ tone: "error", title: "Update failed", body: j.error || undefined });
  });

  const generating = data?.lesson?.status === "generating" || ["queued", "running"].includes(data?.job?.status);
  useEffect(() => {
    if (!generating) return;
    const t = setInterval(() => mutate(), 2500);
    return () => clearInterval(t);
  }, [generating, mutate]);

  const slide = useMemo(() => data?.slides?.find((s: any) => s.number === current), [data, current]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName?.match(/INPUT|TEXTAREA|SELECT/)) return;
      if (!data?.slides?.length) return;
      if (e.key === "ArrowRight") setCurrent((c) => Math.min(data.slides.length, c + 1));
      if (e.key === "ArrowLeft") setCurrent((c) => Math.max(1, c - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [data]);

  if (!data) return <div className="space-y-4"><Skeleton className="h-16" /><Skeleton className="h-[480px]" /></div>;
  const { lesson, course, slides, documents, downloads, reflections } = data;

  const createPlanDoc = async (kind: "lesson_plan" | "teacher_guide") => {
    const existing = documents.find((d: any) => d.kind === kind && d.status === "ready");
    if (existing?.files?.docx) {
      window.location.href = existing.files.pdf || existing.files.docx;
      return;
    }
    const r = await api<any>("/documents", { body: { kind, lesson_id: id } });
    setJobId(r.job_id);
  };
  const regenerateLesson = async () => {
    const r = await api<any>(`/lessons/${id}/regenerate`, { body: { instructions: regenText || null } });
    setRegenOpen(false);
    notify({ tone: "info", title: "Rebuilding the lesson", body: "This takes a minute. You can keep working." });
    setJobId(r.job_id);
    mutate();
  };
  const reflect = async (outcome: string) => {
    const r = await api<any>(`/lessons/${id}/reflection`, { body: { outcome } });
    notify({ tone: "success", title: "Reflection saved", body: r.effects?.join(" ") || undefined });
    mutate();
  };

  const visualIssues = lesson.qc?.visual || {};
  const errors = Object.values(visualIssues).flat().filter((i: any) => i.severity === "error").length;
  const overflow = (lesson.qc?.render || []).filter((r: any) => r.overflow).length;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <Link href={`/projects/${course.project_id}`} className="text-sm text-brand-600 hover:underline">← {course.topic} · Grade {course.grade}</Link>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">Lesson {lesson.number}: {lesson.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <StatusBadge status={lesson.status} />
            <Badge tone={errors || overflow ? "warn" : "success"}><ShieldCheck className="h-3 w-3" /> {errors || overflow ? `${errors + overflow} QC notes` : "QC passed"}</Badge>
            <span className="text-muted">v{lesson.version} · {slides.length} slides</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {downloads.pptx && <Button href={downloads.pptx}><Download className="h-4 w-4" /> PowerPoint</Button>}
          {downloads.pdf && <Button variant="outline" href={downloads.pdf}><FileText className="h-4 w-4" /> PDF</Button>}
          <Button variant="outline" onClick={() => setRegenOpen(true)}><WandSparkles className="h-4 w-4" /> Rebuild lesson</Button>
        </div>
      </div>

      {lesson.carry_over?.text && <Alert tone="accent" title="Carried over from the last lesson">{lesson.carry_over.text}</Alert>}
      {(jobId || generating) && (
        <Alert tone="brand"><span className="flex items-center gap-2"><LoaderCircle className="h-4 w-4 animate-spin" /> {job?.stage || "Working on your lesson"}… {job ? `${job.progress}%` : ""}</span><p className="mt-2 text-sm">No need to wait here. Your changes keep processing; track them in <Link href="/activity" className="underline">Activity</Link>.</p></Alert>
      )}

      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "slides", label: "Slides" }, { value: "plan", label: "Lesson plan" },
        { value: "documents", label: `Documents (${documents.length})` }, { value: "qc", label: "Quality check" },
      ]} />

      {tab === "slides" && (slides.length ? (
        <div className="grid gap-5 xl:grid-cols-[140px_1fr_380px]">
          <div className="order-2 flex gap-2 overflow-x-auto pb-2 xl:order-1 xl:max-h-[76vh] xl:flex-col xl:overflow-y-auto xl:pb-0">
            {slides.map((s: any) => (
              <button key={s.id} onClick={() => setCurrent(s.number)}
                className={cn("focus-ring w-32 shrink-0 rounded-lg border-2 p-0.5 text-start transition xl:w-full", s.number === current ? "border-brand-600" : "border-transparent hover:border-line-strong")}>
                <div className="aspect-[16/9] overflow-hidden rounded-md bg-surface-2">{s.preview && <img src={s.preview} alt={`Slide ${s.number}`} className="h-full w-full object-cover" />}</div>
                <div className="mt-0.5 flex items-center justify-between px-0.5 text-[11px] text-muted">
                  <span>{s.number}</span><span className="truncate">{LAYOUT_LABELS[s.spec.layout]}</span>
                </div>
              </button>
            ))}
          </div>
          <div className="order-1 space-y-3 xl:order-2">
            <Card className="overflow-hidden p-2">
              <div className="relative aspect-[16/9] overflow-hidden rounded-xl bg-surface-2">
                {slide?.preview && <img src={slide.preview} alt={slide.spec.title} className={cn("h-full w-full object-contain transition", jobId && "opacity-60")} />}
              </div>
            </Card>
            <div className="flex items-center justify-between">
              <Button variant="ghost" size="sm" disabled={current <= 1} onClick={() => setCurrent(current - 1)}><ChevronLeft className="h-4 w-4 rtl:rotate-180" /> Previous</Button>
              <span className="text-sm text-muted">Slide {current} of {slides.length} · {slide && LAYOUT_LABELS[slide.spec.layout]} · {slide?.spec.timing_minutes} min</span>
              <Button variant="ghost" size="sm" disabled={current >= slides.length} onClick={() => setCurrent(current + 1)}>Next <ChevronRight className="h-4 w-4 rtl:rotate-180" /></Button>
            </div>
            {slide?.spec.speaker_notes && (
              <Card className="p-4 text-sm">
                <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Teacher notes</div>
                <p className="whitespace-pre-line text-ink-2">{slide.spec.speaker_notes}</p>
                {slide.spec.question_to_ask && <p className="mt-2"><b>Ask:</b> {slide.spec.question_to_ask}</p>}
                {slide.spec.teacher_instruction && <p className="mt-1"><b>Do:</b> {slide.spec.teacher_instruction}</p>}
              </Card>
            )}
          </div>
          <Card className="order-3 p-5">{slide && <SlideEditor lessonId={id} slide={slide} onJob={setJobId} />}</Card>
        </div>
      ) : <EmptyState title="This lesson hasn't been built yet" description="Build it from the project page." />)}

      {tab === "plan" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => createPlanDoc("lesson_plan")}><ClipboardList className="h-4 w-4" /> Download lesson plan (inspection format)</Button>
            <Button variant="outline" onClick={() => createPlanDoc("teacher_guide")}><FileText className="h-4 w-4" /> Download teacher guide</Button>
          </div>
          <LessonPlanView plan={lesson.plan} />
        </div>
      )}

      {tab === "documents" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {[["worksheet", "Worksheet"], ["quiz", "Quiz"], ["homework", "Homework"], ["assessment", "Test"]].map(([k, l]) => (
              <Button key={k} variant="outline" onClick={() => setDocOpen(k)}>+ {l}</Button>
            ))}
          </div>
          {documents.length ? documents.map((d: any) => (
            <Card key={d.id} className="p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium text-ink">{d.title}</div>
                  <div className="text-xs text-muted">{d.kind.replace("_", " ")} · {d.difficulty} · {formatDate(d.created_at)}</div>
                </div>
                <StatusBadge status={d.status} />
              </div>
              {d.status === "ready" && <div className="mt-3"><DocumentFiles files={d.files} /></div>}
            </Card>
          )) : <EmptyState title="No documents yet" description="Create a worksheet, quiz or homework from this lesson. Each comes with a separate answer key." />}
        </div>
      )}

      {tab === "qc" && (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-4">
            <Card className="p-4"><div className="text-sm text-muted">Overflowing slides</div><div className="mt-1 text-2xl font-semibold">{overflow}</div></Card>
            <Card className="p-4"><div className="text-sm text-muted">Visual errors</div><div className="mt-1 text-2xl font-semibold">{errors}</div></Card>
            <Card className="p-4"><div className="text-sm text-muted">Repairs made</div><div className="mt-1 text-2xl font-semibold">{(lesson.qc?.repairs || []).length}</div></Card>
            <Card className="p-4"><div className="text-sm text-muted">Images</div><div className="mt-1 text-sm">{Object.entries(lesson.qc?.images || {}).filter(([, v]) => Number(v) > 0).map(([k, v]) => `${v} ${k}`).join(", ") || "—"}</div></Card>
          </div>
          <Card>
            <CardHeader title="Per-slide checks" subtitle="Text is measured with real font metrics before rendering, then the rendered slides are inspected." />
            <ul className="divide-y divide-line">
              {(lesson.qc?.render || []).map((r: any) => {
                const v = visualIssues[String(r.number)] || [];
                return (
                  <li key={r.number} className="flex flex-wrap items-center gap-3 px-5 py-3 text-sm">
                    <span className="w-16 font-medium text-ink">Slide {r.number}</span>
                    <span className="w-28 text-muted">{LAYOUT_LABELS[r.layout]}</span>
                    <Badge tone={r.overflow ? "danger" : "success"}>{r.overflow ? "Overflow" : "Fits"}</Badge>
                    {r.min_font_pt && <span className="text-muted">min {r.min_font_pt}pt</span>}
                    {v.map((i: any, k: number) => <Badge key={k} tone={i.severity === "error" ? "danger" : "warn"}>{i.code.replace("_", " ")}</Badge>)}
                  </li>
                );
              })}
            </ul>
          </Card>
          {reflections.length > 0 && (
            <Card className="p-5 text-sm">
              <div className="font-medium text-ink">Reflections</div>
              {reflections.map((r: any, i: number) => <div key={i} className="mt-1 text-muted">{formatDate(r.created_at)} — {r.outcome.replace(/_/g, " ")} {r.note && `· ${r.note}`}</div>)}
            </Card>
          )}
        </div>
      )}

      {lesson.status === "generated" && (
        <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-ink-2">Taught this lesson? Tell the assistant how it went.</div>
          <div className="flex flex-wrap gap-2">
            {[["went_well", "✅ Went well"], ["ran_out_of_time", "⏱ Ran out of time"], ["struggled", "😕 Struggled"], ["skipped", "⏭ Skipped"]].map(([k, l]) => (
              <Button key={k} size="sm" variant="outline" onClick={() => reflect(k)}>{l}</Button>
            ))}
          </div>
        </Card>
      )}

      <DocumentDialog open={!!docOpen} kind={docOpen || "worksheet"} lessonId={id} onClose={() => { setDocOpen(null); mutate(); }} />
      <Modal open={regenOpen} onClose={() => setRegenOpen(false)} title="Rebuild this lesson"
        footer={<><Button variant="ghost" onClick={() => setRegenOpen(false)}>Cancel</Button><Button onClick={regenerateLesson}><RotateCcw className="h-4 w-4" /> Rebuild</Button></>}>
        <Field label="What should change? (optional)" hint="e.g. make it suitable for Grade 6; more visual; add a practical activity; shorten to 35 minutes">
          <Textarea value={regenText} onChange={(e) => setRegenText(e.target.value)} />
        </Field>
        <div className="mt-3 flex flex-wrap gap-2">
          {["Make it easier for a younger class", "More visual, less text", "Add a hands-on activity", "Stretch the most able students"].map((s) => (
            <button key={s} className="rounded-full border border-line-strong px-3 py-1 text-xs text-ink-2 hover:border-brand-300" onClick={() => setRegenText(s)}>{s}</button>
          ))}
        </div>
      </Modal>
    </div>
  );
}
