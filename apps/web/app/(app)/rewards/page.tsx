"use client";

import Link from "next/link";
import { useState } from "react";
import { Gift } from "lucide-react";
import { DashHeader, Panel } from "@/components/dash";
import { LoadError } from "@/components/load-error";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Field, Modal, Skeleton, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Task = { id: string; title: string; instructions: string; credits: number; ends_at?: string | null };
type Submission = { id: string; task_id: string; credits: number; status: string; review_note?: string | null; expires_at?: string | null };
type Rewards = { enabled: boolean; eligible: boolean; ineligible_reason?: string; earned_this_month: number; expires_at: string; tasks: Task[]; submissions: Submission[]; limits: { daily_credits: number; monthly_credits: number } };

export default function EarnCredits() {
  const { data, error, mutate } = useApi<Rewards>("/rewards");
  const { notify } = useToast();
  const [selected, setSelected] = useState<Task | null>(null);
  const [proof, setProof] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await api(`/rewards/tasks/${selected.id}/submit`, { method: "POST", body: { proof: proof.trim() } });
      setSelected(null); setProof(""); await mutate();
      notify({ tone: "success", title: "Submitted for review", body: "Credits are added only after a staff member approves your work." });
    } catch (e) { notify({ tone: "error", title: "Couldn't submit task", body: errorMessage(e) }); }
    finally { setBusy(false); }
  };
  if (error) return <LoadError label="credit tasks" retry={mutate} />;
  if (!data) return <Skeleton className="h-80 rounded-3xl" />;
  return <div className="mx-auto max-w-5xl space-y-6">
    <DashHeader title="Earn lesson credits" subtitle="Optional tasks for verified teachers on the Free plan. Honest feedback helps us improve your teaching tools." />
    <Panel title={<span className="flex items-center gap-2"><Gift className="h-5 w-5 text-brand-600" />Your reward credits</span>}>
      <p className="text-3xl font-semibold">{data.earned_this_month} <span className="text-base font-normal text-muted">earned this month</span></p>
      <p className="mt-2 text-sm text-muted">Approved credits increase your lesson allowance until {new Date(data.expires_at).toLocaleDateString()}. Up to {data.limits.daily_credits} credits a day and {data.limits.monthly_credits} a month. They follow Free-plan feature limits.</p>
      {!data.eligible && <p className="mt-3 rounded-xl bg-accent-50 p-3 text-sm">{data.ineligible_reason} <Link className="underline" href="/billing">View your plan</Link></p>}
    </Panel>
    <div className="grid gap-4 sm:grid-cols-2">
      {!data.tasks.length && <Panel title="Tasks are coming soon"><p className="text-sm text-muted">We are preparing useful tasks. Your monthly Free credits remain available. No action earns a reward until a published task is reviewed and approved.</p></Panel>}
      {data.tasks.map((task) => {
        const previous = data.submissions.find((s) => s.task_id === task.id);
        const blocked = previous && previous.status !== "rejected";
        return <Panel key={task.id} title={task.title} action={<Badge>{task.credits} credits</Badge>}>
          <p className="whitespace-pre-wrap text-sm text-ink-2">{task.instructions}</p>
          {task.ends_at && <p className="mt-2 text-xs text-muted">Closes {new Date(task.ends_at).toLocaleDateString()}</p>}
          {previous?.review_note && <p className="mt-3 text-sm text-muted">Review: {previous.review_note}</p>}
          <Button className="mt-4" variant="outline" disabled={!data.enabled || !data.eligible || !!blocked} onClick={() => { setSelected(task); setProof(""); }}>{blocked ? previous?.status === "approved" ? "Reward approved" : "Awaiting review" : previous ? "Submit corrected work" : "Complete task"}</Button>
        </Panel>;
      })}
    </div>
    {!!data.submissions.length && <Panel title="Your submissions"><div className="divide-y divide-line">{data.submissions.map((s) => <div key={s.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm"><div><span className="font-medium">{data.tasks.find((t) => t.id === s.task_id)?.title || "Previous task"}</span>{s.review_note && <p className="mt-1 text-muted">{s.review_note}</p>}{s.expires_at && <p className="text-xs text-muted">Credits valid until {new Date(s.expires_at).toLocaleDateString()}</p>}</div><Badge>{s.status} · {s.credits} credits</Badge></div>)}</div></Panel>}
    <p className="text-xs text-muted">One reward per task for an account and browser. Shared school device? <Link className="underline" href="/support">Contact support</Link>. Do not submit student personal information. Honest feedback is welcome regardless of whether it is positive.</p>
    <Modal open={!!selected} onClose={() => !busy && setSelected(null)} title={selected?.title || "Complete task"}>
      <p className="mb-4 whitespace-pre-wrap text-sm text-muted">{selected?.instructions}</p>
      <Field label="Describe your completed work" hint="20–2,000 characters. Include the requested evidence, without student names or private information."><Textarea value={proof} minLength={20} maxLength={2000} rows={6} onChange={(e) => setProof(e.target.value)} /></Field>
      <Button className="mt-4" loading={busy} disabled={proof.trim().length < 20} onClick={submit}>Submit for review</Button>
    </Modal>
  </div>;
}
