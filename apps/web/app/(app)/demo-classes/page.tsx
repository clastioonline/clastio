"use client";

import { Clock3, Presentation } from "lucide-react";
import { Suspense, useEffect, useState } from "react";
import { EducatorContextFields, EducatorDocument, EducatorJobStatus, EducatorSources, SavedEducatorItems, useEducatorContext, useEducatorSelection, type EducatorItem } from "@/components/educator-workspace";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, CardHeader, Field, PageHeader, Select, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";
import { teacherCourseSelectionValid } from "@/lib/teacher-course-options";

function DemoClassesPage() {
  const { notify } = useToast();
  const [context, setContext, teaching] = useEducatorContext();
  const teachingSelectionValid = teaching.ready && teacherCourseSelectionValid({ ...context, class_section_id: "" }, teaching.options)
    && teaching.stages.includes(context.education_stage);
  const [instructions, setInstructions] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [planId, setPlanId] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useEducatorSelection();
  const [jobId, setJobId] = useState<string | null>(null);
  const { data: list, error: listError, mutate: refreshList } = useApi<{ items: EducatorItem[] }>("/demo-classes", { refreshInterval: data => data?.items.some((item: EducatorItem) => ["queued", "generating"].includes(item.status)) ? 3000 : 0 });
  const { data: detail, error: detailError, mutate: refreshDetail } = useApi<EducatorItem>(selected ? `/demo-classes/${selected}` : null, { refreshInterval: data => data && ["queued", "generating"].includes(data.status) ? 2000 : 0 });
  const templateQuery = new URLSearchParams({ subject: context.subject, grade: context.grade, language: context.language });
  const { data: templates } = useApi<{ items: { id: string; name: string; status: string }[] }>(teachingSelectionValid ? `/templates?${templateQuery}` : null);
  const { data: plans } = useApi<{ items: EducatorItem[] }>("/lesson-plans");
  const { data: linkedPlan } = useApi<EducatorItem>(planId ? `/lesson-plans/${planId}` : null);
  useEffect(() => {
    if (!linkedPlan?.content || !teaching.ready || !teacherCourseSelectionValid({
      subject: String(linkedPlan.content.subject || linkedPlan.subject || ""),
      grade: String(linkedPlan.content.grade || linkedPlan.grade || ""), class_section_id: "",
    }, teaching.options)) return;
    const content = linkedPlan.content;
    setContext(previous => ({ ...previous, topic: String(content.topic || previous.topic),
      subject: String(content.subject || previous.subject), grade: String(content.grade || previous.grade),
      curriculum: String(content.curriculum || previous.curriculum), language: String(content.language || previous.language),
      framework: String(content.framework || previous.framework), education_stage: String(content.education_stage || previous.education_stage) }));
  }, [linkedPlan, setContext, teaching.ready, teaching.options]);
  const eligiblePlans = (plans?.items || []).filter(plan => ["ready", "reviewed"].includes(plan.status) && plan.duration_minutes === 15
    && teacherCourseSelectionValid({ subject: plan.subject || "", grade: plan.grade || "", class_section_id: "" }, teaching.options));
  useEffect(() => {
    if (teaching.ready && plans && planId && !eligiblePlans.some(plan => plan.id === planId)) setPlanId("");
  }, [teaching.ready, plans, planId, teaching.options]);
  const job = useJob(jobId || detail?.job?.id, async finished => { await refreshDetail(); await refreshList(); if (finished.status === "failed") notify({ tone: "error", title: "Could not generate demo", body: finished.error || "Check your inputs and try again." }); });
  const updateContext = (next: typeof context) => { setContext(next); setPlanId(""); };
  const generate = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy || blocked || !teachingSelectionValid) return; setBusy(true);
    try { const result = await api<any>("/demo-classes", { body: { ...context, duration_minutes: 15, instructions, template_id: templateId || null, lesson_plan_id: planId || null }, idempotent: true }); setSelected(result.demo_class_id); setJobId(result.job_id); await refreshList(); notify({ tone: "info", title: "Preparing your demonstration lesson", body: "Clastio will match your timed teacher script, learning checks and presentation." }); }
    catch (error) { notify({ tone: "error", title: "Could not start demo", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  const detailContent = detail?.content || (detail?.teacher_script ? { hook: detail.hook, teacher_script: detail.teacher_script, review_checks: detail.review_checks } : null);
  const scriptContent = detailContent ? Object.fromEntries(Object.entries(detailContent).filter(([key]) => key !== "slide_payload")) : null;
  return <div className="space-y-5"><PageHeader title="Demo class generator" eyebrow="Teacher workspace" subtitle="A focused 15-minute micro-lesson with an interactive hook, timed teaching script and matching slides." />
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"><div className="min-w-0 space-y-5"><Card><CardHeader title="Build a high-impact demo" icon={<Presentation className="h-5 w-5" />} subtitle="Choose a small, teachable idea and make every minute purposeful." /><form onSubmit={generate} className="space-y-4 p-5"><EducatorContextFields value={context} onChange={updateContext} /><Alert tone="neutral"><span className="flex items-center gap-2"><Clock3 className="h-4 w-4" /> Fixed duration: 15 minutes, including the hook and exit check.</span></Alert><div className="grid gap-4 sm:grid-cols-2"><Field label="Presentation design"><Select value={templateId} onChange={event => setTemplateId(event.target.value)}><option value="">Clastio default design</option>{(templates?.items || []).filter(template => template.status === "ready").map(template => <option key={template.id} value={template.id}>{template.name}</option>)}</Select></Field><Field label="Link to a saved lesson plan"><Select value={planId} onChange={event => setPlanId(event.target.value)}><option value="">Create a new micro-lesson plan</option>{eligiblePlans.map(plan => <option key={plan.id} value={plan.id}>{plan.title}</option>)}</Select></Field></div><Field label="Class needs and demo instructions"><Textarea value={instructions} maxLength={6000} onChange={event => setInstructions(event.target.value)} placeholder="Open with a mangrove observation, use pair talk, include ELL sentence frames and finish with a hinge question." /></Field><Button type="submit" loading={busy} disabled={blocked || !teachingSelectionValid || job?.status === "queued" || job?.status === "running"}>Generate demo class</Button></form></Card><EducatorSources value={context} onChange={setContext} onBlocked={setBlocked} /><EducatorJobStatus job={job} />
      {detailError && <Alert tone="danger" title="Could not open demo">{errorMessage(detailError)}</Alert>}{selected && !detail && !detailError && <Spinner />}{detail?.error && <Alert tone="danger" title="Demo generation failed">{detail.error}</Alert>}
      {detail && scriptContent && Object.keys(scriptContent).length > 0 && <EducatorDocument language={detail.language} title={detail.title} content={scriptContent} downloads={detail.downloads}><Alert tone="neutral" className="mb-5">Rehearse the timings and check expected student responses before teaching. The generated presentation follows the script’s slide references.</Alert>{typeof detail.presentation_version === "number" && detail.presentation_version > 1 && <Alert tone="neutral" className="mb-5">The script below is the original demo draft. Open the presentation to view your latest slide edits.</Alert>}{typeof detail.lesson_id === "string" && <div className="mb-5"><Button href={`/lessons/${encodeURIComponent(detail.lesson_id)}`} variant="outline">Open presentation preview & editor</Button></div>}</EducatorDocument>}
    </div><div className="min-w-0 space-y-3">{listError && <Alert tone="danger">{errorMessage(listError)}</Alert>}<SavedEducatorItems title="My demo classes" items={list?.items || []} selected={selected} onSelect={id => { setSelected(id); setJobId(null); }} empty="No saved demo classes yet" /></div></div></div>;
}

export default function Page() { return <Suspense fallback={<Spinner />}><DemoClassesPage /></Suspense>; }
