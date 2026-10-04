"use client";

import { useEffect, useState } from "react";
import { AdminPage } from "@/components/admin-kit";
import { Panel } from "@/components/dash";
import { LoadError } from "@/components/load-error";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Field, Input, Modal, Skeleton, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useCan } from "@/lib/hooks";

type Task = { id?: string; title: string; instructions: string; credits: number; published: boolean; max_approvals: number; starts_at: string | null; ends_at: string | null };
const emptyTask: Task = { title: "", instructions: "", credits: 5, published: false, max_approvals: 100, starts_at: null, ends_at: null };
const limits = [{ key: "daily_credits", label: "Per teacher / day", max: 50 }, { key: "monthly_credits", label: "Per teacher / month", max: 200 }, { key: "lifetime_credits", label: "Per teacher / lifetime", max: 500 }, { key: "global_daily_credits", label: "Platform / day", max: 2000 }];

export default function AdminRewards() {
  const can = useCan();
  const manage = can("billing.modify");
  const { data, error, mutate } = useApi<any>(can("billing.view") ? "/admin/rewards" : null);
  const { notify } = useToast();
  const [program, setProgram] = useState<any>(null);
  const [reason, setReason] = useState("");
  const [task, setTask] = useState<Task | null>(null);
  const [ack, setAck] = useState(false);
  const [review, setReview] = useState<any>(null);
  const [note, setNote] = useState("");
  const [email, setEmail] = useState("");
  const [exceptionReason, setExceptionReason] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) setProgram(data.program); }, [data]);
  const action = async (path: string, method: "POST" | "PUT", body: any, title: string, after?: () => void) => {
    setBusy(true);
    try { await api(path, { method, body }); await mutate(); after?.(); notify({ tone: "success", title }); }
    catch (e) { notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) }); }
    finally { setBusy(false); }
  };
  return <AdminPage title="Free-plan credit tasks" perm="billing.view" subtitle="Publish optional tasks and manually review proof. Every approval adds a single audited ledger reward. No tasks are published initially.">
    {error ? <LoadError label="credit tasks" retry={mutate} /> : !data ? <Skeleton className="h-80 rounded-3xl" /> : <>
      {program && <Panel title="Program limits"><fieldset disabled={!manage || busy} className="space-y-4">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!program.enabled} onChange={(e) => setProgram({ ...program, enabled: e.target.checked })} />Enable published tasks</label>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{limits.map((item) => <Field key={item.key} label={item.label}><Input type="number" min={1} max={item.max} value={program[item.key]} onChange={(e) => setProgram({ ...program, [item.key]: Number(e.target.value) })} /></Field>)}</div>
        <Field label="Reason for changing the program"><Input value={reason} minLength={5} maxLength={500} onChange={(e) => setReason(e.target.value)} /></Field>
        <p className="text-xs text-muted">Credits expire at the next calendar month. Daily limits use UTC. Account and browser claims deter repeat rewards; support can review legitimate shared devices. Require useful work or honest product feedback. Never require positive public reviews, unsolicited messages, fabricated evidence or purchases.</p>
        {manage && <Button loading={busy} disabled={reason.trim().length < 5} onClick={() => action("/admin/rewards/program", "PUT", { ...program, reason: reason.trim() }, "Program saved", () => setReason(""))}>Save program</Button>}
      </fieldset></Panel>}
      <Panel title="Tasks" action={manage && <Button variant="outline" onClick={() => { setTask({ ...emptyTask }); setAck(false); }}>Add task</Button>}>
        {!data.tasks.length && <p className="text-sm text-muted">No tasks yet. Add your first task when content quality and your reward budget are ready.</p>}
        <div className="divide-y divide-line">{data.tasks.map((item: Task) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3"><div><div className="font-medium">{item.title}</div><p className="text-sm text-muted">{item.credits} credits · maximum {item.max_approvals} approvals</p></div><div className="flex items-center gap-2"><Badge>{item.published ? "Published" : "Draft"}</Badge>{manage && <Button variant="outline" onClick={() => { setTask(item); setAck(false); }}>Edit</Button>}</div></div>)}</div>
      </Panel>
      <Panel title={`Awaiting review (${data.submissions.length})`}>
        {!data.submissions.length && <p className="text-sm text-muted">No pending submissions.</p>}
        <div className="divide-y divide-line">{data.submissions.map((item: any) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><div className="font-medium">{item.task_title}</div><p className="text-muted">{item.email || "Deleted account"} · {item.credits} credits</p></div>{manage && <Button variant="outline" onClick={() => { setReview(item); setNote(""); }}>Review proof</Button>}</div>)}</div>
      </Panel>
      {can("users.manage", "billing.modify") && <Panel title="Shared-school-device trial exception"><p className="mb-4 text-sm text-muted">Allow a verified teacher to choose their one-time trial on a shared browser. This never resets their email trial history or starts a trial automatically.</p><div className="grid gap-3 sm:grid-cols-2"><Field label="Verified teacher email"><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field><Field label="Verified reason for the exception"><Input minLength={10} maxLength={500} value={exceptionReason} onChange={(e) => setExceptionReason(e.target.value)} /></Field></div><Button className="mt-4" loading={busy} disabled={!email || exceptionReason.trim().length < 10} onClick={() => action("/admin/rewards/trial-exception", "POST", { email, reason: exceptionReason.trim() }, "Shared-device exception recorded", () => { setEmail(""); setExceptionReason(""); })}>Allow one-time trial choice</Button></Panel>}
    </>}
    <Modal open={!!task} onClose={() => !busy && setTask(null)} title={task?.id ? "Edit credit task" : "Add credit task"} size="lg">
      {task && <div className="space-y-4"><Field label="Task title"><Input value={task.title} maxLength={160} onChange={(e) => setTask({ ...task, title: e.target.value })} /></Field><Field label="Instructions and evidence required"><Textarea rows={5} value={task.instructions} maxLength={4000} onChange={(e) => setTask({ ...task, instructions: e.target.value })} /></Field><div className="grid gap-3 sm:grid-cols-2"><Field label="Lesson credits"><Input type="number" min={1} max={20} value={task.credits} onChange={(e) => setTask({ ...task, credits: Number(e.target.value) })} /></Field><Field label="Maximum approvals"><Input type="number" min={1} max={5000} value={task.max_approvals} onChange={(e) => setTask({ ...task, max_approvals: Number(e.target.value) })} /></Field><Field label="Starts (optional)"><Input type="datetime-local" value={task.starts_at ? new Date(task.starts_at).toISOString().slice(0, 16) : ""} onChange={(e) => setTask({ ...task, starts_at: e.target.value ? new Date(e.target.value + "Z").toISOString() : null })} /><span className="text-xs text-muted">UTC</span></Field><Field label="Ends (optional)"><Input type="datetime-local" value={task.ends_at ? new Date(task.ends_at).toISOString().slice(0, 16) : ""} onChange={(e) => setTask({ ...task, ends_at: e.target.value ? new Date(e.target.value + "Z").toISOString() : null })} /><span className="text-xs text-muted">UTC</span></Field></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={task.published} onChange={(e) => setTask({ ...task, published: e.target.checked })} />Publish task</label><label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /><span>This task asks for useful work or honest feedback and does not require positive public reviews, fabricated evidence, unsolicited messages or purchases.</span></label><Button loading={busy} disabled={!ack || task.title.trim().length < 5 || task.instructions.trim().length < 20} onClick={() => action(task.id ? `/admin/rewards/tasks/${task.id}` : "/admin/rewards/tasks", task.id ? "PUT" : "POST", { ...task, policy_acknowledged: true }, "Task saved", () => setTask(null))}>Save task</Button></div>}
    </Modal>
    <Modal open={!!review} onClose={() => !busy && setReview(null)} title="Review task evidence" size="lg">
      {review && <div className="space-y-4"><p className="text-sm text-muted">{review.task_title} · {review.email} · {review.credits} credits</p><p className="whitespace-pre-wrap break-words rounded-xl bg-surface-2 p-4 text-sm">{review.proof}</p><Field label="Review note"><Textarea rows={3} minLength={5} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} /></Field><div className="flex flex-wrap gap-3"><Button loading={busy} disabled={note.trim().length < 5} onClick={() => action(`/admin/rewards/submissions/${review.id}/review`, "POST", { approve: true, note: note.trim() }, "Reward approved", () => setReview(null))}>Approve {review.credits} credits</Button><Button variant="outline" disabled={busy || note.trim().length < 5} onClick={() => action(`/admin/rewards/submissions/${review.id}/review`, "POST", { approve: false, note: note.trim() }, "Submission returned", () => setReview(null))}>Reject with feedback</Button></div></div>}
    </Modal>
  </AdminPage>;
}
