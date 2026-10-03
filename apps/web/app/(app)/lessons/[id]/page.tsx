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
  Pencil,
  Upload,
  ShieldCheck,
  WandSparkles,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { StatusBadge } from "@/components/common";
import { DocumentDialog, DocumentFiles } from "@/components/document-dialog";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, Select, Skeleton, Tabs, Textarea, Toggle } from "@/components/ui";
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

function SlideEditor({ lessonId, slide, onJob, pending }: { lessonId: string; slide: any; pending: boolean; onJob: (id: string) => void }) {
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
  const [layout, setLayout] = useState(s.layout);
  const [timing, setTiming] = useState(s.timing_minutes);
  const [columns, setColumns] = useState<any[]>(s.columns?.length ? s.columns : [{ heading: "", bullets: [] }, { heading: "", bullets: [] }]);
  const [table, setTable] = useState<any>(s.table || { headers: ["Item", "Value"], rows: [["", ""]] });
  const [terms, setTerms] = useState<any[]>(s.terms || []);
  const [chartKind, setChartKind] = useState(s.chart?.kind || "bar");
  const [categories, setCategories] = useState(toLines(s.chart?.categories));
  const [series, setSeries] = useState<any[]>(s.chart?.series?.map((item: any) => ({ name: item.name, values: item.values.join(", ") })) || [{ name: "", values: "" }]);
  const [chartSource, setChartSource] = useState(s.chart?.source || "");
  const [chartUnit, setChartUnit] = useState(s.chart?.unit || "");
  const [assetId, setAssetId] = useState<string | null>(s.asset_id || null);
  const [imageFit, setImageFit] = useState(s.visual?.fit || "contain");
  const [imageChanged, setImageChanged] = useState(false);
  const [imageRemoved, setImageRemoved] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [keepImages, setKeepImages] = useState(true);
  const { data: creditInfo } = useApi<any>("/usage/estimates");
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
    setLayout(s.layout); setTiming(s.timing_minutes);
    setColumns(s.columns?.length ? s.columns : [{ heading: "", bullets: [] }, { heading: "", bullets: [] }]);
    setTable(s.table || { headers: ["Item", "Value"], rows: [["", ""]] }); setTerms(s.terms || []);
    setChartKind(s.chart?.kind || "bar"); setCategories(toLines(s.chart?.categories));
    setSeries(s.chart?.series?.map((item: any) => ({ name: item.name, values: item.values.join(", ") })) || [{ name: "", values: "" }]);
    setChartSource(s.chart?.source || ""); setChartUnit(s.chart?.unit || "");
    setAssetId(s.asset_id || null); setImageFit(s.visual?.fit || "contain"); setImageChanged(false); setImageRemoved(false);
    refreshVersions();
  }, [slide.id, slide.version]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async () => {
    setBusy("save");
    const patch: any = { title, speaker_notes: notes, layout, timing_minutes: Number(timing) };
    if (s.subtitle !== null || subtitle) patch.subtitle = subtitle || null;
    if (s.bullets.length || ["concept", "summary", "objectives", "homework", "exit_ticket", "image_text", "discussion"].includes(layout)) {
      patch.bullets = bullets.split("\n").filter((l: string) => l.trim()).map((l: string) => ({ text: l.replace(/^\s*-\s*/, "").trim(), level: /^\s+-/.test(l) ? 1 : 0 }));
    }
    if (s.steps.length || ["process", "cycle", "timeline", "activity"].includes(layout)) {
      patch.steps = steps.split("\n").filter((l: string) => l.trim()).map((l: string) => {
        const [label, ...rest] = l.split(":");
        return { label: label.trim(), detail: rest.join(":").trim() };
      });
    }
    if (s.quiz || layout === "quiz") patch.quiz = { explanation: "", ...s.quiz, question, options: options.split("\n").filter((o: string) => o.trim()), answer_index: Number(answer) };
    else if (s.question !== null && s.question !== undefined) patch.question = question;
    if (["two_column", "comparison"].includes(layout)) patch.columns = columns;
    if (layout === "table") patch.table = table;
    if (layout === "key_vocabulary") patch.terms = terms;
    if (layout === "chart") patch.chart = { kind: chartKind, categories: categories.split("\n").map((item) => item.trim()).filter(Boolean),
      series: series.map((item) => ({ name: item.name, values: item.values.split(",").map((number: string) => Number(number.trim())) })), source: chartSource, unit: chartUnit };
    if (imageFit !== (s.visual?.fit || "contain") && !imageChanged) {
      patch.visual = { ...s.visual, fit: imageFit }; patch.asset_id = assetId;
    }
    if (imageChanged) {
      patch.asset_id = assetId;
      patch.visual = { ...s.visual, kind: imageRemoved ? "none" : "image", fit: imageFit, source_image_key: null, counting_groups: [], alt_text: s.visual?.alt_text || title };
      patch.sources = (s.sources || []).filter((source: any) => source.type !== "image");
      if (assetId) patch.sources.push({ type: "image", source: "upload", description: "Teacher supplied" });
    }
    try {
      const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}`, { method: "PATCH", body: { spec: patch }, idempotent: true });
      onJob(r.job_id);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const uploadImage = async (file?: File) => {
    if (!file) return;
    setBusy("image");
    try {
      const form = new FormData(); form.append("file", file);
      const result = await api<any>("/slide-images", { form });
      setAssetId(result.asset_id); setImageChanged(true); setImageRemoved(false);
      if (!["concept", "image_text"].includes(layout)) setLayout("image_text");
      notify({ tone: "success", title: "Image ready", body: "Save & rebuild to place it on the slide." });
    } catch (error) { notify({ tone: "error", title: "Couldn't upload image", body: errorMessage(error) }); }
    finally { setBusy(null); }
  };
  const regenerate = async (action?: string) => {
    setBusy(action || "custom");
    try {
      const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}/regenerate`, { body: { action, instruction: action ? undefined : instruction, keep_images: keepImages }, idempotent: true });
      onJob(r.job_id);
      setInstruction("");
    } catch (e) {
      notify({ tone: "error", title: "Couldn't regenerate", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const restore = async (version: number) => {
    const r = await api<any>(`/lessons/${lessonId}/slides/${slide.number}/restore`, { body: { version }, idempotent: true });
    onJob(r.job_id);
  };

  return (
    <fieldset disabled={pending || !!busy} className="space-y-5">
      <div>
        <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">AI edit — this slide only</div>
        <p className="mb-3 text-xs text-muted">{creditInfo ? `${creditInfo.costs.slide} credit(s) per successful changed slide` : "Loading edit cost…"}. Manual edits and version restores use 0 generation credits. Other slides are not sent for rewriting.</p>
        {["image_text", "concept"].includes(s.layout) && <Link href={`/assistant?mode=image_edit&lesson=${lessonId}&slide=${slide.number}`} className="mb-3 inline-flex text-sm font-semibold text-brand-700">Discuss image changes with your assistant →</Link>}
        <Toggle checked={keepImages} onChange={setKeepImages} label="Keep existing images" description="Recommended for wording changes. To replace a picture precisely, upload it in the manual editor below." />
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
        <div className="flex items-center gap-2 font-semibold"><Pencil className="h-4 w-4" /> Edit slide manually</div>
        <p className="text-xs text-muted">Change the content yourself, then save to rebuild the PowerPoint without an AI rewrite. For free-positioning shapes, download and edit in PowerPoint.</p>
        <Field label="Layout"><Select aria-label="Layout" value={layout} onChange={(e) => setLayout(e.target.value)}>{Object.entries(LAYOUT_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</Select></Field>
        <Field label="Teaching time (minutes)"><Input type="number" min={0} step={0.5} value={timing} onChange={(e) => setTiming(e.target.value)} /></Field>
        <Field label="Title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
        {(s.layout === "cover" || s.layout === "section" || s.layout === "activity" || s.subtitle) && (
          <Field label="Subtitle"><Input value={subtitle} onChange={(e) => setSubtitle(e.target.value)} /></Field>
        )}
        {(s.quiz || s.question || layout === "quiz" || layout === "discussion") && <Field label="Question"><Textarea className="min-h-[60px]" value={question} onChange={(e) => setQuestion(e.target.value)} /></Field>}
        {(s.quiz || layout === "quiz") && (
          <>
            <Field label="Options (one per line)"><Textarea className="min-h-[90px]" value={options} onChange={(e) => setOptions(e.target.value)} /></Field>
            <Field label="Correct answer">
              <Select value={answer} onChange={(e) => setAnswer(Number(e.target.value))}>
                {options.split("\n").filter((o) => o.trim()).map((o, i) => <option key={i} value={i}>{"ABCD"[i]}) {o}</option>)}
              </Select>
            </Field>
          </>
        )}
        {(["concept", "summary", "objectives", "homework", "exit_ticket", "image_text", "discussion", "worked_example"].includes(layout)) && (
          <Field label="Bullets (one per line, start with ‘  - ’ to indent)"><Textarea className="min-h-[120px]" value={bullets} onChange={(e) => setBullets(e.target.value)} /></Field>
        )}
        {(s.steps.length > 0 || ["process", "cycle", "timeline", "activity"].includes(layout)) && <Field label="Steps (Label: detail)"><Textarea className="min-h-[110px]" value={steps} onChange={(e) => setSteps(e.target.value)} /></Field>}
        {["two_column", "comparison"].includes(layout) && columns.map((column, index) => <div key={index} className="space-y-2 rounded-lg border border-line p-3">
          <Field label={`Column ${index + 1} heading`}><Input value={column.heading} onChange={(e) => setColumns(columns.map((item, n) => n === index ? { ...item, heading: e.target.value } : item))} /></Field>
          <Field label="Content (one point per line)"><Textarea value={toLines(column.bullets)} onChange={(e) => setColumns(columns.map((item, n) => n === index ? { ...item, bullets: e.target.value.split("\n") } : item))} /></Field>
        </div>)}
        {layout === "table" && <div className="space-y-2">
          <div className="text-sm font-medium">Table headings and cells</div>
          <div className="overflow-x-auto"><table><thead><tr>{table.headers.map((header: string, col: number) => <th key={col}><Input aria-label={`Heading ${col + 1}`} value={header} onChange={(e) => setTable({ ...table, headers: table.headers.map((h: string, i: number) => i === col ? e.target.value : h) })} /></th>)}</tr></thead>
          <tbody>{table.rows.map((row: string[], index: number) => <tr key={index}>{table.headers.map((_: string, col: number) => <td key={col}><Input aria-label={`Row ${index + 1} column ${col + 1}`} value={row[col] || ""} onChange={(e) => setTable({ ...table, rows: table.rows.map((r: string[], i: number) => i === index ? table.headers.map((_: string, j: number) => j === col ? e.target.value : r[j] || "") : r) })} /></td>)}<td><Button size="sm" variant="ghost" onClick={() => setTable({ ...table, rows: table.rows.filter((_: any, i: number) => i !== index) })}>Remove</Button></td></tr>)}</tbody></table></div>
          <Button size="sm" variant="outline" disabled={table.rows.length >= 5} onClick={() => setTable({ ...table, rows: [...table.rows, table.headers.map(() => "")] })}>Add row</Button>
          <Button size="sm" variant="outline" disabled={table.headers.length >= 4} onClick={() => setTable({ headers: [...table.headers, ""], rows: table.rows.map((row: string[]) => [...row, ""]) })}>Add column</Button>
        </div>}
        {layout === "chart" && <div className="space-y-3">
          <Field label="Chart type"><Select value={chartKind} onChange={(e) => setChartKind(e.target.value)}><option value="bar">Bar</option><option value="line">Line</option><option value="pie">Pie</option></Select></Field>
          <Field label="Categories (one per line)"><Textarea value={categories} onChange={(e) => setCategories(e.target.value)} /></Field>
          {series.map((item, index) => <div key={index} className="space-y-2"><Field label={`Series ${index + 1} name`}><Input value={item.name} onChange={(e) => setSeries(series.map((s, i) => i === index ? { ...s, name: e.target.value } : s))} /></Field><Field label="Values (comma separated, same order as categories)"><Input value={item.values} onChange={(e) => setSeries(series.map((s, i) => i === index ? { ...s, values: e.target.value } : s))} /></Field>{series.length > 1 && <Button size="sm" variant="ghost" onClick={() => setSeries(series.filter((_, i) => i !== index))}>Remove series</Button>}</div>)}
          <Button size="sm" variant="outline" disabled={series.length >= 4 || chartKind === "pie"} onClick={() => setSeries([...series, { name: "", values: "" }])}>Add series</Button>
          <Field label="Units"><Input value={chartUnit} onChange={(e) => setChartUnit(e.target.value)} /></Field>
          <Field label="Data source"><Input value={chartSource} onChange={(e) => setChartSource(e.target.value)} placeholder="e.g. Class survey, 2 October" /></Field>
        </div>}
        {layout === "key_vocabulary" && <div className="space-y-2">{terms.map((term, index) => <div key={index} className="space-y-2"><Input aria-label={`Term ${index + 1}`} value={term.term} onChange={(e) => setTerms(terms.map((t, i) => i === index ? { ...t, term: e.target.value } : t))} /><Input aria-label={`Meaning ${index + 1}`} value={term.meaning} onChange={(e) => setTerms(terms.map((t, i) => i === index ? { ...t, meaning: e.target.value } : t))} /><Button variant="ghost" size="sm" onClick={() => setTerms(terms.filter((_, i) => i !== index))}>Remove term</Button></div>)}<Button variant="outline" size="sm" disabled={terms.length >= 6} onClick={() => setTerms([...terms, { term: "", meaning: "", translation: null }])}>Add term</Button></div>}
        <Field label="Image fit"><Select value={imageFit} onChange={(e) => setImageFit(e.target.value)}><option value="contain">Show full image — preserve diagrams and labels</option><option value="cover">Fill image frame — crop edges</option></Select></Field>
        <Field label="Slide image"><span className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm"><Upload className="h-4 w-4" /> {busy === "image" ? "Uploading…" : "Upload / replace image"}<input type="file" accept="image/png,image/jpeg,image/webp" className="hidden" disabled={!!busy} onChange={(e) => { uploadImage(e.target.files?.[0]); e.target.value = ""; }} /></span>
          {assetId && <Button size="sm" variant="ghost" onClick={() => { setAssetId(null); setImageChanged(true); setImageRemoved(true); }}>Remove image</Button>}
          {imageChanged && <p className="mt-1 text-xs text-muted">Image change will apply when you save.</p>}
        </Field>
        <Field label="Speaker notes"><Textarea className="min-h-[100px]" value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        <div className="flex items-center justify-between gap-2">
          {versions?.items?.length > 1 ? (
            <Select className="max-w-[60%]" value="" onChange={(e) => e.target.value && restore(Number(e.target.value))}>
              <option value="">Version history ({versions.items.length})</option>
              {versions.items.slice(1).map((v: any) => <option key={v.version} value={v.version}>v{v.version} · {v.reason || "edit"} · {formatDate(v.created_at, { hour: "2-digit", minute: "2-digit" })}</option>)}
            </Select>
          ) : <span />}
          <Button onClick={save} loading={busy === "save"} disabled={!!busy && busy !== "save"}><Save className="h-4 w-4" /> Save & rebuild · 0 credits</Button>
        </div>
      </div>
    </fieldset>
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
  const { data: creditInfo } = useApi<any>("/usage/estimates");
  const [tab, setTab] = useState<"slides" | "plan" | "documents" | "qc">("slides");
  const [current, setCurrent] = useState(1);
  const [jobId, setJobId] = useState<string | null>(null);
  const [docOpen, setDocOpen] = useState<string | null>(null);
  const [regenOpen, setRegenOpen] = useState(false);
  const [reflectionNote, setReflectionNote] = useState("");
  const [coveredSlide, setCoveredSlide] = useState("");
  const [reflectionBusy, setReflectionBusy] = useState(false);
  const [regenText, setRegenText] = useState("");
  const job = useJob(jobId || (["queued", "running"].includes(data?.job?.status) ? data.job.id : null), (j) => {
    setJobId(null);
    mutate();
    if (j.status === "succeeded") notify({ tone: "success", title: j.result?.changed === false ? "No changes needed" : "Slides updated", body: j.result?.changed === false ? "No generation credits were used." : "Your design system was preserved." });
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
    setReflectionBusy(true);
    try {
      const result = await api<any>(`/lessons/${id}/reflection`, { body: { outcome, note: reflectionNote || null, covered_until_slide: coveredSlide ? Number(coveredSlide) : null } });
      notify({ tone: "success", title: "Class notes saved", body: result.effects?.join(" ") || "These notes will inform the next lesson." });
      setReflectionNote(""); setCoveredSlide(""); mutate();
    } catch (error) { notify({ tone: "error", title: "Couldn't save class notes", body: errorMessage(error) }); }
    finally { setReflectionBusy(false); }
  };

  const visualUnavailable = lesson.qc?.visual_status === "unavailable" || slides.some((s: any) => !s.preview);
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
            <Badge tone={visualUnavailable || errors || overflow ? "warn" : "success"}><ShieldCheck className="h-3 w-3" /> {visualUnavailable ? "Visual check unavailable" : errors || overflow ? `${errors + overflow} QC notes` : "QC passed"}</Badge>
            <span className="text-muted">v{lesson.version} · {slides.length} slides</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {downloads.pptx && <Button href={downloads.pptx}><Download className="h-4 w-4" /> Download editable PPT</Button>}
          {downloads.pdf && <Button variant="outline" href={downloads.pdf}><FileText className="h-4 w-4" /> PDF</Button>}
          <Button variant="outline" onClick={() => setRegenOpen(true)}><WandSparkles className="h-4 w-4" /> Rebuild lesson</Button>
        </div>
      </div>

      {Number(lesson.qc?.images?.placeholder || 0) > 0 && <Alert tone="warn" title="Some images need replacement">A real illustration was unavailable for {lesson.qc.images.placeholder} slide(s). Use Upload / replace image in the manual editor, or rebuild with live AI illustrations enabled.</Alert>}

      {lesson.carry_over?.text && <Alert tone="accent" title="Carried over from the last lesson">{lesson.carry_over.text}</Alert>}
      {(jobId || generating) && (
        <Alert tone="brand"><span className="flex items-center gap-2"><LoaderCircle className="h-4 w-4 animate-spin" /> {job?.stage || "Working on your lesson"}… {job ? `${job.progress}%` : ""}</span><p className="mt-2 text-sm">No need to wait here. Your changes keep processing; track them in <Link href="/activity" className="underline">Activity</Link>.</p></Alert>
      )}

      <Tabs value={tab} onChange={setTab} tabs={[
        { value: "slides", label: "Slides & manual editor" }, { value: "plan", label: "Lesson plan" },
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
          <div data-tour="slide-editor" className="order-3"><Card className="p-5">{slide && <SlideEditor lessonId={id} slide={slide} onJob={setJobId} pending={!!jobId || generating} />}</Card></div>
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

      {lesson.qc?.ai_mode === "offline" && <Alert tone="neutral">Offline demo content. Use this lesson to test the design and workflow; review or replace the sample teaching content before classroom use.</Alert>}

      {visualUnavailable && <Alert tone="warn">Slide previews and visual checks could not be completed. The PowerPoint is available, but its layout has not been verified. Rebuild the lesson to try again.</Alert>}

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

      {["generated", "reflected", "taught"].includes(lesson.status) && (
        <div data-tour="class-reflection"><Card className="space-y-4 p-5">
          <div className="font-semibold">After class: what did you teach, and what needs revision?</div>
          <Field label="Class notes"><Textarea value={reflectionNote} maxLength={2000} onChange={(e) => setReflectionNote(e.target.value)} placeholder="We taught ratios today. Students struggled to choose the correct ratio; revise this tomorrow with two examples." /></Field>
          <Field label="Last slide completed (optional)"><Input type="number" min={1} max={slides.length} value={coveredSlide} onChange={(e) => setCoveredSlide(e.target.value)} /></Field>
          <div className="flex flex-wrap gap-2">
            {[["went_well", "✅ Went well"], ["ran_out_of_time", "⏱ Ran out of time"], ["struggled", "😕 Struggled"], ["skipped", "⏭ Skipped"]].map(([k, l]) => (
              <Button key={k} size="sm" variant="outline" disabled={reflectionBusy} onClick={() => reflect(k)}>{l}</Button>
            ))}
          </div>
        </Card></div>
      )}

      <DocumentDialog open={!!docOpen} kind={docOpen || "worksheet"} lessonId={id} onClose={() => { setDocOpen(null); mutate(); }} />
      <Modal open={regenOpen} onClose={() => setRegenOpen(false)} title="Rebuild this lesson"
        footer={<><Button variant="ghost" onClick={() => setRegenOpen(false)}>Cancel</Button><Button onClick={regenerateLesson}><RotateCcw className="h-4 w-4" /> Rebuild</Button></>}>
        <Alert tone="brand" title="A small edit costs less">Manual edits and restores use 0 generation credits. An AI edit to one slide costs {creditInfo?.costs?.slide ?? "the configured slide rate"}; this full rebuild costs about {creditInfo ? creditInfo.costs.slide * course.slides_per_lecture : "the slide count × the configured rate"} credits. For a wording or example change, cancel and edit the selected slide.</Alert>
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
