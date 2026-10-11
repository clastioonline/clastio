"use client";

import { BookOpenCheck, CheckCheck, Pencil, Plus, Save } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { EducatorContextFields, EducatorDocument, EducatorJobStatus, EducatorSources, SavedEducatorItems, useEducatorContext, useEducatorSelection, type EducatorItem } from "@/components/educator-workspace";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, CardHeader, Field, Input, PageHeader, Select, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";

function PlanEditor({ content, onChange }: { content: any; onChange: (content: any) => void }) {
  const change = (path: (string | number)[], value: string | boolean | string[]) => {
    const updated = structuredClone(content);
    let cursor = updated;
    for (const key of path.slice(0, -1)) cursor = cursor[key];
    cursor[path[path.length - 1]] = value;
    onChange(updated);
  };
  const objectiveActions = ["identify", "describe", "explain", "compare", "classify", "calculate", "construct", "justify", "evaluate", "design", "demonstrate", "analyse", "apply", "solve", "create", "observe", "predict", "present", "model", "write", "summarise", "investigate"];
  return <div className="space-y-4"><Field label="Plan title"><Input value={content.title || ""} onChange={event => change(["title"], event.target.value)} /></Field>
    <h3 className="font-semibold">Measurable objectives</h3>{(content.learning_objectives || []).map((objective: any, index: number) => <div key={objective.id} className="space-y-3 rounded-xl border border-line p-3"><Field label={`Objective ${index + 1}`}><Textarea value={objective.description} onChange={event => change(["learning_objectives", index, "description"], event.target.value)} /></Field><Field label="Success measure"><Textarea value={objective.success_measure} onChange={event => change(["learning_objectives", index, "success_measure"], event.target.value)} /></Field></div>)}
    <h3 className="font-semibold">Success criteria</h3>{(content.success_criteria || []).map((criterion: any, index: number) => <Field key={criterion.id} label={`Criterion ${index + 1}`}><Textarea value={criterion.description} onChange={event => change(["success_criteria", index, "description"], event.target.value)} /></Field>)}
    <h3 className="font-semibold">Observable learning actions</h3>{(content.learning_objectives || []).map((objective: any, index: number) => <Field key={objective.id} label={`Observable action for objective ${index + 1}`}><Select value={objective.observable_action || "explain"} onChange={event => change(["learning_objectives", index, "observable_action"], event.target.value)}>{objectiveActions.map(action => <option key={action}>{action}</option>)}</Select></Field>)}
    <h3 className="font-semibold">Cross-curricular links</h3>{(content.cross_curricular_links || []).map((link: any, index: number) => <div key={index} className="space-y-3 rounded-xl border border-line p-3"><Field label={`Linked subject ${index + 1}`}><Input value={link.subject} onChange={event => change(["cross_curricular_links", index, "subject"], event.target.value)} /></Field><Field label="Linked learning activity"><Textarea value={link.activity} onChange={event => change(["cross_curricular_links", index, "activity"], event.target.value)} /></Field><Field label="Evidence of cross-curricular learning"><Textarea value={link.evidence_of_learning} onChange={event => change(["cross_curricular_links", index, "evidence_of_learning"], event.target.value)} /></Field></div>)}
    <h3 className="font-semibold">UAE connections</h3>{Object.entries(content.uae_context || {}).map(([key, connection]) => { const item = connection as any; return <div key={key} className="space-y-3 rounded-xl border border-line p-3"><p className="font-medium capitalize">{key.replaceAll("_", " ")}</p><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={item.relevant} onChange={event => change(["uae_context", key, "relevant"], event.target.checked)} /> Relevant to this lesson</label><Field label="Connection or reason"><Textarea value={item.connection_or_reason} onChange={event => change(["uae_context", key, "connection_or_reason"], event.target.value)} /></Field><Field label="Classroom application"><Textarea value={item.classroom_application} onChange={event => change(["uae_context", key, "classroom_application"], event.target.value)} /></Field></div>; })}
    <h3 className="font-semibold">Differentiation and inclusion</h3>{(["sen", "ell"] as const).map(group => <div key={group} className="space-y-3"><h4 className="text-sm font-medium">{group === "sen" ? "SEN / students of determination" : "ELL / language support"}</h4>{(content.differentiation?.[group] || []).map((strategy: any, index: number) => <div key={index} className="space-y-3 rounded-xl border border-line p-3"><Field label="Learning barrier"><Textarea value={strategy.learning_barrier} onChange={event => change(["differentiation", group, index, "learning_barrier"], event.target.value)} /></Field><Field label="Scaffold"><Textarea value={strategy.scaffold} onChange={event => change(["differentiation", group, index, "scaffold"], event.target.value)} /></Field><Field label="Assessment accommodation"><Textarea value={strategy.assessment_accommodation} onChange={event => change(["differentiation", group, index, "assessment_accommodation"], event.target.value)} /></Field></div>)}</div>)}
    <h3 className="font-semibold">Teaching sequence</h3>{(content.lesson_sequence || []).map((phase: any, index: number) => <div key={index} className="space-y-3 rounded-xl border border-line p-3"><p className="font-medium">{phase.name} · {phase.duration_minutes} minutes</p><Field label="Teacher actions"><Textarea value={phase.teacher_actions} onChange={event => change(["lesson_sequence", index, "teacher_actions"], event.target.value)} /></Field><Field label="Student actions"><Textarea value={phase.student_actions} onChange={event => change(["lesson_sequence", index, "student_actions"], event.target.value)} /></Field></div>)}
    <Field label="Core learning task"><Textarea value={content.differentiation?.core || ""} onChange={event => change(["differentiation", "core"], event.target.value)} /></Field><Field label="Extension challenge"><Textarea value={content.differentiation?.extension || ""} onChange={event => change(["differentiation", "extension"], event.target.value)} /></Field>
    <h3 className="font-semibold">Formative assessment</h3>{(content.formative_assessment || []).map((assessment: any, index: number) => <div key={assessment.id} className="space-y-3 rounded-xl border border-line p-3"><Field label={assessment.tool}><Textarea value={assessment.question_or_task} onChange={event => change(["formative_assessment", index, "question_or_task"], event.target.value)} /></Field><Field label="Expected response"><Textarea value={assessment.expected_response} onChange={event => change(["formative_assessment", index, "expected_response"], event.target.value)} /></Field><Field label="Teaching response"><Textarea value={assessment.teaching_response} onChange={event => change(["formative_assessment", index, "teaching_response"], event.target.value)} /></Field></div>)}
    <Field label="Homework"><Textarea value={content.homework || ""} onChange={event => change(["homework"], event.target.value)} /></Field>
    <h3 className="font-semibold">Recorded assessment evidence</h3>{(content.formative_assessment || []).map((assessment: any, index: number) => <Field key={assessment.id} label={`Evidence for ${assessment.tool}`}><Textarea value={assessment.evidence_to_record || ""} onChange={event => change(["formative_assessment", index, "evidence_to_record"], event.target.value)} /></Field>)}
    </div>;
}

function LessonPlannersPage() {
  const { notify } = useToast();
  const [context, setContext] = useEducatorContext();
  const [minutes, setMinutes] = useState(45);
  const [instructions, setInstructions] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useEducatorSelection();
  const [jobId, setJobId] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<any>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [actionBusy, setActionBusy] = useState(false);
  const { data: list, error: listError, mutate: refreshList } = useApi<{ items: EducatorItem[] }>("/lesson-plans", { refreshInterval: data => data?.items.some((item: EducatorItem) => ["queued", "generating"].includes(item.status)) ? 3000 : 0 });
  const { data: detail, error: detailError, mutate: refreshDetail } = useApi<EducatorItem>(selected ? `/lesson-plans/${selected}` : null, { refreshInterval: data => data && ["queued", "generating"].includes(data.status) ? 2000 : 0 });
  const job = useJob(jobId || detail?.job?.id, async finished => { await refreshDetail(); await refreshList(); if (finished.status === "failed") notify({ tone: "error", title: "Could not generate plan", body: finished.error || "Try again after reviewing your inputs." }); });
  useEffect(() => { setEditing(false); setDraft(null); setReviewNotes(""); }, [selected]);
  const generate = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy || blocked) return; setBusy(true);
    try { const result = await api<any>("/lesson-plans", { body: { ...context, duration_minutes: minutes, instructions }, idempotent: true }); setSelected(result.lesson_plan_id); setJobId(result.job_id); await refreshList(); notify({ tone: "info", title: "Planning your lesson", body: "Your inspection-aligned draft will include objectives, inclusion strategies and assessment evidence." }); }
    catch (error) { notify({ tone: "error", title: "Could not start planner", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  const action = async (kind: "save" | "review" | "export") => {
    if (!detail || actionBusy) return; setActionBusy(true);
    try {
      const result = await api<any>(`/lesson-plans/${detail.id}${kind === "save" ? "" : `/${kind}`}`, { method: kind === "save" ? "PUT" : "POST", body: kind === "save" ? { version: detail.version, content: draft } : kind === "review" ? { version: detail.version, notes: reviewNotes } : {}, idempotent: kind !== "save" });
      if (result?.job_id) setJobId(result.job_id);
      setEditing(false); await refreshDetail(); await refreshList(); notify({ tone: "success", title: kind === "save" ? "Plan changes saved" : kind === "review" ? "Teacher review recorded" : "Preparing PDF export" });
    } catch (error) { notify({ tone: "error", title: "Could not save plan", body: errorMessage(error) }); }
    finally { setActionBusy(false); }
  };
  return <div className="space-y-5"><PageHeader title="Lesson planners" eyebrow="Teacher workspace" subtitle="Backward design, UAE connections, inclusion and formative assessment in one teacher-reviewed plan." actions={<Button variant="outline" href="/projects/new"><Plus className="h-4 w-4" /> Create matching presentations</Button>} />
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"><div className="min-w-0 space-y-5"><Card><CardHeader title="Plan a lesson" icon={<BookOpenCheck className="h-5 w-5" />} subtitle="Tell Clastio what your class needs to learn and how you will check it." /><form onSubmit={generate} className="space-y-4 p-5"><EducatorContextFields value={context} onChange={setContext} /><Field label="Lesson duration (minutes)"><Input type="number" required min={5} max={180} value={minutes} onChange={event => setMinutes(Number(event.target.value))} /></Field><Field label="Class needs and planning instructions" hint="Describe learning barriers and language support without individual student names or diagnoses."><Textarea value={instructions} maxLength={6000} onChange={event => setInstructions(event.target.value)} placeholder="Include vocabulary visuals, sentence frames, an extension task and a hinge question." /></Field><Button type="submit" loading={busy} disabled={blocked || job?.status === "queued" || job?.status === "running"}>Generate lesson plan</Button></form></Card><EducatorSources value={context} onChange={setContext} onBlocked={setBlocked} /><EducatorJobStatus job={job} />
      {detailError && <Alert tone="danger" title="Could not open plan">{errorMessage(detailError)}</Alert>}{selected && !detail && !detailError && <Spinner />}{detail?.error && <Alert tone="danger" title="Plan generation failed">{detail.error}</Alert>}
      {detail?.content && Object.keys(detail.content).length > 0 && <>{editing ? <Card className="space-y-4 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Edit lesson plan</h2><div className="flex gap-2"><Button variant="outline" onClick={() => setEditing(false)}>Cancel</Button><Button loading={actionBusy} onClick={() => action("save")}><Save className="h-4 w-4" /> Save changes</Button></div></div><PlanEditor content={draft} onChange={setDraft} /></Card> : <EducatorDocument language={detail.language} title={detail.title} content={detail.content} downloads={detail.downloads}><div className="mb-5 flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => { setDraft(structuredClone(detail.content)); setEditing(true); }}><Pencil className="h-4 w-4" /> Edit plan</Button><Button variant="outline" size="sm" loading={actionBusy} onClick={() => action("export")}>Generate PDF</Button></div></EducatorDocument>}
      <Card className="space-y-3 p-5"><h3 className="font-semibold">Teacher review</h3><p className="text-sm text-muted">Check curriculum accuracy, class suitability and any evidence gaps. This records your review of the draft.</p><Field label="Review notes"><Textarea value={reviewNotes} maxLength={2000} onChange={event => setReviewNotes(event.target.value)} placeholder="Changes checked and teaching resources confirmed." /></Field><Button variant="outline" loading={actionBusy} disabled={editing || detail.status === "reviewed"} onClick={() => action("review")}><CheckCheck className="h-4 w-4" /> {detail.status === "reviewed" ? "Reviewed by teacher" : "Mark reviewed"}</Button></Card></>}
    </div><div className="min-w-0 space-y-3">{listError && <Alert tone="danger">{errorMessage(listError)}</Alert>}<SavedEducatorItems title="My lesson plans" items={list?.items || []} selected={selected} onSelect={id => { setSelected(id); setJobId(null); }} empty="No saved plans yet" /></div></div></div>;
}

export default function Page() { return <Suspense fallback={<Spinner />}><LessonPlannersPage /></Suspense>; }
