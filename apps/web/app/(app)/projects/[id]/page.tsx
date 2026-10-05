"use client";

import { BookOpen, ChevronRight, Pencil, RefreshCw, Target, Trash, WandSparkles } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SlideThumb, StatusBadge } from "@/components/common";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, Modal, PageHeader, Progress, Skeleton, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function PlanEditor({ open, onClose, course, onSaved }: { open: boolean; onClose: () => void; course: any; onSaved: () => void }) {
  const [plan, setPlan] = useState<any>(course?.plan);
  const [busy, setBusy] = useState(false);
  const { notify } = useToast();
  useEffect(() => setPlan(course?.plan), [course]);
  if (!plan) return null;
  const setLec = (i: number, k: string, v: any) => setPlan({ ...plan, lectures: plan.lectures.map((l: any, j: number) => (j === i ? { ...l, [k]: v } : l)) });
  const save = async () => {
    setBusy(true);
    try {
      await api(`/courses/${course.id}/plan`, { method: "PUT", body: plan });
      notify({ tone: "success", title: "Plan saved" });
      onSaved();
      onClose();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title="Edit lesson sequence" size="lg"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy}>Save plan</Button></>}>
      <div className="space-y-4">
        {plan.lectures.map((l: any, i: number) => (
          <div key={i} className="rounded-xl border border-line p-4">
            <div className="text-xs font-semibold text-brand-600">Lesson {l.number}</div>
            <Input className="mt-2" value={l.title} onChange={(e) => setLec(i, "title", e.target.value)} />
            <Textarea className="mt-2 min-h-[60px]" value={l.objectives.join("\n")} onChange={(e) => setLec(i, "objectives", e.target.value.split("\n").filter(Boolean))} />
            <div className="mt-1 text-xs text-muted">One objective per line</div>
          </div>
        ))}
      </div>
    </Modal>
  );
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(`/projects/${id}`);
  const [preparing, setPreparing] = useState<number[] | null>(null);
  const [previousTaught, setPreviousTaught] = useState("");
  const [revisionNeeded, setRevisionNeeded] = useState("");
  const [preparationNotes, setPreparationNotes] = useState("");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const working = data && (["planning", "generating"].includes(data.course.status) || data.lessons.some((l: any) => l.status === "generating"));
  useEffect(() => {
    if (!working) return;
    const t = setInterval(() => mutate(), 2000);
    return () => clearInterval(t);
  }, [working, mutate]);

  if (!data) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-64" /></div>;
  const { course, lessons, progress } = data;
  const plan = course.plan;

  const generate = async (numbers?: number[]) => {
    setBusy("generate");
    try {
      await api(`/courses/${course.id}/generate`, { body: { lessons: numbers, previous_taught: previousTaught, revision_needed: revisionNeeded, instructions: preparationNotes || null } });
      mutate();
      setPreparing(null);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't start", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const prepare = (numbers?: number[]) => {
    const waiting = lessons.filter((lesson: any) => ["planned", "failed"].includes(lesson.status));
    const targets = numbers || waiting.slice(0, 1).map((lesson: any) => lesson.number);
    if (!targets.length) return;
    setPreviousTaught(targets.includes(1) ? course.options?.previous_taught || "" : "");
    setRevisionNeeded(targets.includes(1) ? course.options?.revision_needed || "" : "");
    setPreparationNotes(""); setPreparing(targets);
  };
  const remove = async () => {
    if (!confirm("Delete this project and all its lessons?")) return;
    await api(`/projects/${id}`, { method: "DELETE" });
    router.push("/projects");
  };
  const pct = progress.total ? Math.round(progress.lessons.reduce((a: number, l: any) => a + (l.status === "generated" || l.status === "reflected" ? 100 : l.progress || 0), 0) / progress.total) : 0;

  return (
    <div className="space-y-6">
      <Modal open={!!preparing} onClose={() => setPreparing(null)} title={`Prepare lesson${(preparing?.length || 0) > 1 ? "s" : ""} ${preparing?.join(", ") || ""}`}
        footer={<><Button variant="ghost" onClick={() => setPreparing(null)}>Cancel</Button><Button loading={busy === "generate"} onClick={() => generate(preparing || undefined)}>Build these lessons</Button></>}>
        <div className="space-y-4">
          <p className="text-sm text-muted">Recorded classroom reflections and unfinished work are included automatically. Add anything the assistant should know before this class.</p>
          <Field label="What did you teach in the previous class?"><Textarea value={previousTaught} maxLength={2000} onChange={(e) => setPreviousTaught(e.target.value)} placeholder="We introduced sin, cos and tan and completed the first two examples." /></Field>
          <Field label="What should be revised again?"><Textarea value={revisionNeeded} maxLength={2000} onChange={(e) => setRevisionNeeded(e.target.value)} placeholder="Revise identifying opposite and adjacent with a short diagnostic question." /></Field>
          <Field label="Instructions for this part / day"><Textarea value={preparationNotes} maxLength={2000} onChange={(e) => setPreparationNotes(e.target.value)} placeholder="Start with 5 minutes of revision, then cover worked examples and finish with an exit ticket." /></Field>
        </div>
      </Modal>
      <PageHeader eyebrow={`Grade ${course.grade} · ${course.subject} · ${course.num_lectures} lessons × ${course.slides_per_lecture} slides`}
        title={course.topic}
        subtitle={plan?.overview}
        actions={
          <>
            {plan && <Button variant="outline" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" /> Edit sequence</Button>}
            {plan && lessons.some((l: any) => l.status === "planned" || l.status === "failed") && (
              <Button disabled={working || lessons.some((l: any) => l.has_pptx && !l.review_approved)} onClick={() => prepare()} loading={busy === "generate"}><WandSparkles className="h-4 w-4" /> Prepare next lesson</Button>
            )}
            <Button variant="ghost" size="icon" onClick={remove} aria-label="Delete project"><Trash className="h-4 w-4" /></Button>
          </>
        } />

      {course.options?.chapter_mode === "daily" && <Alert tone="neutral" title="Prepare day by day">Teach the ready lesson, record how the class went, then prepare the next day. The chapter plan stays connected while each new lesson can respond to revision needs.</Alert>}
      {course.options?.chapter_mode === "parts" && <Alert tone="neutral" title="Prepare selected parts">Build one lesson, review its slides and request changes, then approve it to unlock the next lesson.</Alert>}
      {(course.options?.source_file_ids?.length || 0) > 0 && <p className="text-sm text-muted">Grounded in {course.options.source_file_ids.length} selected book / notes file(s).</p>}
      {working && <Alert tone="brand" title="Keep teaching while we prepare">This work continues in the background. You can leave this page or close the browser. <Link href="/activity" className="font-medium underline">Follow progress in Activity</Link>.</Alert>}
      {course.status === "planning" && (
        <Card className="p-6">
          <div className="flex items-center gap-3 text-ink"><WandSparkles className="h-5 w-5 animate-pulse text-brand-600" /> Planning a connected lesson sequence…</div>
          <Progress value={data.plan_job?.progress || 20} className="mt-4" />
          <div className="mt-2 text-xs text-muted">{data.plan_job?.stage}</div>
        </Card>
      )}
      {course.status === "failed" && <Alert tone="danger" title="Planning failed">{course.error}</Alert>}
      {working && course.status !== "planning" && (
        <Card className="p-5">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-ink">Building your lessons in your design…</span>
            <span className="tabular-nums text-muted">{progress.done} / {progress.total} ready</span>
          </div>
          <Progress value={pct} className="mt-3" />
        </Card>
      )}

      {plan && <Alert title="Review each PPT before continuing">Open the generated PPT, inspect each slide and request changes. Approve the finished version to unlock the next class.</Alert>}
      {plan && (
        <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
          <div className="space-y-3">
            {lessons.map((l: any) => {
              const lp = plan.lectures[l.number - 1];
              const pr = progress.lessons.find((x: any) => x.lesson_id === l.id);
              return (
                <Card key={l.id} className="overflow-hidden">
                  <div className="flex flex-col gap-4 p-4 sm:flex-row">
                    <SlideThumb src={l.cover} alt={l.title} className="w-full shrink-0 sm:w-48" />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">

                        <Badge tone="brand">Lesson {l.number}</Badge>
                        <StatusBadge status={l.status} />
                        {l.scheduled_date && <span className="text-xs text-muted">{l.scheduled_date}</span>}
                      </div>
                      <h3 className="mt-1.5 font-semibold text-ink">{l.title}</h3>
                      {lp && (
                        <>
                          <ul className="mt-1.5 space-y-0.5 text-sm text-muted">
                            {lp.objectives.slice(0, 2).map((o: string) => <li key={o}>• {o}</li>)}
                          </ul>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {lp.key_concepts.map((k: string) => <Badge key={k}>{k}</Badge>)}
                          </div>
                        </>
                      )}
                      {l.status === "generating" && pr && <div className="mt-3"><Progress value={pr.progress} className="h-1.5" /><div className="mt-1 text-xs text-muted">{pr.stage}</div></div>}
                      {l.error && l.status === "failed" && <Alert tone="danger" className="mt-3">{l.error}</Alert>}
                      {l.carry_over?.text && <div className="mt-2 rounded-lg bg-accent-50 px-3 py-1.5 text-xs text-accent-600">↪ {l.carry_over.text}</div>}
                    </div>
                    <div className="flex shrink-0 items-start gap-2 sm:flex-col">
                      {l.has_pptx ? (
                        <Button size="sm" href={`/lessons/${l.id}`}>{l.review_approved ? "Open" : "Review PPT"} <ChevronRight className="h-4 w-4 rtl:rotate-180" /></Button>
                      ) : l.status !== "generating" ? (
                        <Button size="sm" variant="outline" disabled={working || lessons.some((prior: any) => prior.number < l.number && !prior.review_approved)} onClick={() => prepare([l.number])}>Build</Button>
                      ) : null}
                      {l.has_pptx && (
                        <Button size="sm" variant="ghost" onClick={() => prepare([l.number])}><RefreshCw className="h-4 w-4" /> Rebuild</Button>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
          <div className="space-y-6">
            <Card>
              <CardHeader icon={<Target className="h-5 w-5" />} title="Learning outcomes" />
              <ul className="space-y-2 p-5 text-sm text-ink-2">
                {plan.learning_outcomes.map((o: any, i: number) => <li key={i}>• {o.text} {o.code && <span className="text-xs text-muted">({o.code})</span>}</li>)}
              </ul>
            </Card>
            <Card>
              <CardHeader icon={<BookOpen className="h-5 w-5" />} title="Big idea" subtitle={plan.big_idea} />
              <div className="space-y-3 p-5 text-sm">
                <div><div className="font-medium text-ink">Prerequisites</div><div className="text-muted">{plan.prerequisites.join("; ") || "—"}</div></div>
                <div><div className="font-medium text-ink">Diagnostic questions</div><ul className="text-muted">{plan.diagnostic_questions.map((q: string) => <li key={q}>• {q}</li>)}</ul></div>
                <div><div className="font-medium text-ink">Revision strategy</div><div className="text-muted">{plan.revision_strategy}</div></div>
                <div><div className="font-medium text-ink">Assessment</div><div className="text-muted">{plan.assessment_strategy}</div></div>
                {plan.local_context_links?.length > 0 && <div><div className="font-medium text-ink">Local links</div><div className="text-muted">{plan.local_context_links.join("; ")}</div></div>}
              </div>
            </Card>
            <Link href="/lessons?tab=documents" className="block text-sm font-medium text-brand-600 hover:underline">Worksheets & quizzes for this course →</Link>
          </div>
        </div>
      )}
      <PlanEditor open={editing} onClose={() => setEditing(false)} course={course} onSaved={mutate} />
    </div>
  );
}
