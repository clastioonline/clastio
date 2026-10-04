"use client";

import { ArrowLeft, Ban, KeyRound, LogOut, MailCheck, RotateCcw, ShieldOff } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { AdminPage, DataTable, JsonBlock, LoadMore, Mono, PrivacyNote, ReasonDialog, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Field, Input, Select, Skeleton, Tabs, Textarea } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi, useCan } from "@/lib/hooks";
import { quotaAvailable } from "@/lib/usage";

type Tab = "overview" | "billing" | "security" | "activity" | "notes";
type Action = null | { kind: "status"; status: string } | { kind: "logout" } | { kind: "verification"; action: string }
  | { kind: "credits" } | { kind: "plan" } | { kind: "role" };

export default function AdminUserPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const can = useCan();
  const { notify } = useToast();
  const { data, error, mutate } = useApi<any>(`/admin/users/${id}`);
  const [tab, setTab] = useState<Tab>("overview");
  const [action, setAction] = useState<Action>(null);
  const [credits, setCredits] = useState({ resource: "credits", amount: 100 });
  const [plan, setPlan] = useState({ mode: "grant", plan: "pro", months: 1, days: 7 });
  const [role, setRole] = useState("support");
  const [note, setNote] = useState("");

  if (error) return <Alert tone="danger">{errorMessage(error)}</Alert>;
  if (!data) return <Skeleton className="h-96" />;
  const u = data.user;
  const staff = !!u.admin_role;
  const done = (title: string) => { notify({ tone: "success", title }); mutate(); };
  const post = (path: string, body: any) => api(`/admin/users/${id}${path}`, { body, idempotent: true });

  const confirm = async (reason: string) => {
    if (!action) return;
    if (action.kind === "status") { await post("/status", { status: action.status, reason }); done(`Account ${action.status === "active" ? "restored" : action.status}`); }
    if (action.kind === "logout") { const r: any = await post("/force-logout", { reason }); done(`Signed out of ${r.sessions_revoked} session(s)`); }
    if (action.kind === "verification") { await post("/verification", { action: action.action, reason }); done("Verification updated"); }
    if (action.kind === "credits") { await post("/credits", { ...credits, reason }); done("Credits adjusted"); }
    if (action.kind === "plan") {
      const body = plan.mode === "grant" ? { plan: plan.plan, months: plan.months } : plan.mode === "trial" ? { extend_trial_days: plan.days } : { end_manual: true };
      await post("/plan", { ...body, reason }); done("Plan updated");
    }
    if (action.kind === "role") { await api(`/admin/users/${id}/staff-role`, { method: "PUT", body: { admin_role: role === "none" ? null : role, reason } }); done("Staff role changed"); }
  };
  const addNote = async () => {
    try { await post("/notes", { body: note }); setNote(""); done("Note added"); } catch (e) { notify({ tone: "error", title: errorMessage(e) }); }
  };
  const resetLink = async () => {
    try { await post("/password-reset", {}); notify({ tone: "success", title: "Reset link sent", body: "The teacher chooses their own password; staff never see it." }); } catch (e) { notify({ tone: "error", title: errorMessage(e) }); }
  };

  const usage = data.usage.usage;
  return (
    <AdminPage title={u.name || u.email} perm="users.view"
      subtitle={<span className="flex flex-wrap items-center gap-2">{u.email} <StatusPill value={u.status} /> {!u.email_verified && <Badge>email unverified</Badge>} {staff && <Badge tone="accent">{u.admin_role.replace("_", " ")}</Badge>}</span>}
      actions={<Button variant="ghost" href="/admin/users"><ArrowLeft className="h-4 w-4" /> All accounts</Button>}>
      {u.status === "suspended" || u.status === "banned" ? <Alert tone="warn" title={`Account ${u.status}`}>{u.suspended_reason}</Alert> : null}
      {u.status === "pending_deletion" && <Alert tone="warn" title="Deletion requested">Requested {formatDate(u.deletion_requested_at)}. Content is purged 30 days after the request. Restoring the account cancels the deletion.</Alert>}

      {can("users.manage") && u.status !== "deleted" && (
        <section className="flex flex-wrap gap-2 rounded-3xl bg-surface p-4">
          {u.status === "active" ? <Button variant="outline" onClick={() => setAction({ kind: "status", status: "suspended" })}><ShieldOff className="h-4 w-4" /> Suspend</Button>
            : <Button variant="outline" onClick={() => setAction({ kind: "status", status: "active" })}><RotateCcw className="h-4 w-4" /> Restore</Button>}
          {can("users.ban") && u.status !== "banned" && <Button variant="danger" onClick={() => setAction({ kind: "status", status: "banned" })}><Ban className="h-4 w-4" /> Ban</Button>}
          <Button variant="outline" onClick={() => setAction({ kind: "logout" })}><LogOut className="h-4 w-4" /> Force sign-out</Button>
          <Button variant="outline" onClick={resetLink}><KeyRound className="h-4 w-4" /> Send password reset</Button>
          {u.email_verified
            ? <Button variant="ghost" onClick={() => setAction({ kind: "verification", action: "mark_unverified" })}><MailCheck className="h-4 w-4" /> Reset verification</Button>
            : <><Button variant="ghost" onClick={() => api(`/admin/users/${id}/verification`, { body: { action: "resend" } }).then(() => done("Verification email sent"))}>Resend verification</Button>
                <Button variant="ghost" onClick={() => setAction({ kind: "verification", action: "mark_verified" })}>Mark verified</Button></>}
          {can("admins.manage") && !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && <Button variant="ghost" onClick={() => setAction({ kind: "role" })}>Staff role…</Button>}
        </section>
      )}

      <Tabs value={tab} onChange={setTab} tabs={[{ value: "overview", label: "Overview" }, { value: "billing", label: "Billing & credits" }, { value: "security", label: "Sessions & security" }, { value: "activity", label: "Activity" }, { value: "notes", label: "Notes & audit" }]} />

      {tab === "overview" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <section className="space-y-3 rounded-3xl bg-surface p-5 text-sm lg:col-span-1">
            <h2 className="font-semibold text-ink">Profile</h2>
            <dl className="grid grid-cols-[8rem_1fr] gap-y-2">
              <dt className="text-muted">User id</dt><dd><Mono>{u.id}</Mono></dd>
              <dt className="text-muted">Joined</dt><dd>{formatDate(u.created_at, { day: "numeric", month: "short", year: "numeric" })}</dd>
              <dt className="text-muted">Last active</dt><dd><When at={u.last_active_at || u.last_login_at} /></dd>
              <dt className="text-muted">Signed up via</dt><dd>{u.signup_source || "—"}</dd>
              <dt className="text-muted">Password</dt><dd>{u.has_password ? `set · changed ${u.password_changed_at ? formatDate(u.password_changed_at) : "—"}` : "single sign-on only"}</dd>
              <dt className="text-muted">Time zone</dt><dd>{u.timezone}</dd>
            </dl>
            {Object.keys(u.signup_meta || {}).length > 0 && <><h3 className="pt-2 font-medium text-ink">Acquisition</h3><JsonBlock value={u.signup_meta} /></>}
            <PrivacyNote>Staff can never see passwords. Viewing this page is recorded in the audit log.</PrivacyNote>
          </section>
          <section className="space-y-4 rounded-3xl bg-surface p-5 text-sm lg:col-span-2">
            <h2 className="font-semibold text-ink">Plan & usage — {data.usage.plan.name}{data.usage.trial?.active && ` (trial, ${data.usage.trial.days_left} days left)`}</h2>
            <div className="grid gap-3 sm:grid-cols-4">
              {Object.entries(usage).map(([k, v]: any) => (
                <div key={k} className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted">{k.replace("_", " ")}</div><div className="font-semibold tabular-nums">{v.used} / {v.limit === -1 ? "∞" : v.limit ?? "—"}</div>{["credits", "ai_images", "whatsapp_messages"].includes(k) && <div className="mt-1 text-xs text-muted">{quotaAvailable(v) === null ? "Unlimited" : `${quotaAvailable(v)} available`}{v.reserved > 0 && ` · ${v.reserved} reserved`}</div>}</div>
              ))}
              <div className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted">media credits</div><div className="font-semibold tabular-nums">{data.media_credits}</div></div>
              <div className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted">AI cost this period</div><div className="font-semibold tabular-nums">${data.usage.ai_cost_usd}</div></div>
            </div>
            <h3 className="pt-2 font-medium text-ink">Projects</h3>
            <DataTable rows={data.projects} empty="No projects yet." columns={[
              { key: "topic", label: "Topic", render: (p) => `${p.topic} · Grade ${p.grade}` },
              { key: "status", label: "Status", render: (p) => <StatusPill value={p.status} /> },
              { key: "created_at", label: "Created", render: (p) => <When at={p.created_at} /> }]} />
            <h3 className="pt-2 font-medium text-ink">Recent jobs</h3>
            <DataTable rows={data.jobs} empty="No jobs yet." columns={[
              { key: "type", label: "Job" }, { key: "status", label: "Status", render: (j) => <StatusPill value={j.status} /> },
              { key: "cost_usd", label: "AI cost", render: (j) => `$${(j.cost_usd || 0).toFixed(4)}` },
              { key: "error", label: "Error", render: (j) => <span className="line-clamp-2 text-xs text-danger-700">{j.error || ""}</span> },
              { key: "created_at", label: "When", render: (j) => <When at={j.created_at} /> }]} />
          </section>
        </div>
      )}

      {tab === "billing" && (
        <div className="space-y-6">
          {can("billing.modify") && !staff && (
            <section className="grid gap-4 rounded-3xl bg-surface p-5 md:grid-cols-2">
              <div className="space-y-3">
                <h2 className="font-semibold text-ink">Change plan</h2>
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="Action"><Select value={plan.mode} onChange={(e) => setPlan({ ...plan, mode: e.target.value })}><option value="grant">Grant a plan</option><option value="trial">Extend trial</option><option value="end">End granted plan/trial</option></Select></Field>
                  {plan.mode === "grant" && <><Field label="Plan"><Select value={plan.plan} onChange={(e) => setPlan({ ...plan, plan: e.target.value })}>{["teacher", "pro", "assistant"].map((p) => <option key={p}>{p}</option>)}</Select></Field>
                    <Field label="Months"><Input type="number" min={1} max={36} value={plan.months} onChange={(e) => setPlan({ ...plan, months: Number(e.target.value) })} className="w-20" /></Field></>}
                  {plan.mode === "trial" && <Field label="Days"><Input type="number" min={1} max={90} value={plan.days} onChange={(e) => setPlan({ ...plan, days: Number(e.target.value) })} className="w-20" /></Field>}
                  <Button onClick={() => setAction({ kind: "plan" })}>Apply…</Button>
                </div>
                <p className="text-xs text-muted">Teachers paying through the gateway must be changed there, so they're never charged for a plan they don't have.</p>
              </div>
              <div className="space-y-3">
                <h2 className="font-semibold text-ink">Adjust credits</h2>
                <div className="flex flex-wrap items-end gap-2">
                  <Field label="Credits"><Select value={credits.resource} onChange={(e) => setCredits({ ...credits, resource: e.target.value })}><option value="credits">Lesson credits</option><option value="media_credits">Media credits</option></Select></Field>
                  <Field label="Amount (negative removes)"><Input type="number" value={credits.amount} onChange={(e) => setCredits({ ...credits, amount: Number(e.target.value) })} className="w-28" /></Field>
                  <Button onClick={() => setAction({ kind: "credits" })} disabled={!credits.amount}>Apply…</Button>
                </div>
              </div>
            </section>
          )}
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Subscriptions</h2>
            <DataTable rows={data.subscriptions} columns={[
              { key: "plan", label: "Plan" }, { key: "status", label: "Status", render: (s) => <StatusPill value={s.status} /> },
              { key: "provider", label: "Source" }, { key: "period_end", label: "Period ends", render: (s) => s.period_end ? formatDate(s.period_end, { day: "numeric", month: "short", year: "numeric" }) : "—" },
              { key: "cancel_at_period_end", label: "Renews", render: (s) => (s.cancel_at_period_end ? "No" : "Yes") }]} />
          </section>
          {data.payments && <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Payments</h2>
            <DataTable rows={data.payments} empty="No payments." columns={[
              { key: "amount", label: "Amount", render: (p) => `${p.currency} ${p.amount.toFixed(2)}` }, { key: "status", label: "Status", render: (p) => <StatusPill value={p.status} /> },
              { key: "provider", label: "Gateway" }, { key: "provider_ref", label: "Reference", render: (p) => <Mono>{p.provider_ref}</Mono> },
              { key: "failure_reason", label: "Failure", render: (p) => p.failure_reason || "" }, { key: "created_at", label: "When", render: (p) => <When at={p.created_at} /> }]} />
          </section>}
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Credit ledger</h2>
            <DataTable rows={data.ledger} columns={[
              { key: "event_type", label: "Event", render: (r) => <Badge tone={r.amount > 0 ? "success" : "neutral"}>{r.event_type.replace("CREDIT_", "").toLowerCase()}</Badge> },
              { key: "amount", label: "Amount", render: (r) => <span className="tabular-nums">{r.amount > 0 ? "+" : ""}{r.amount} {r.resource === "credits" ? "" : r.resource.replace("_", " ")}</span> },
              { key: "reason", label: "Reason", render: (r) => <>{r.reason}{r.note && <span className="block text-xs text-muted">“{r.note}”</span>}</> },
              { key: "created_at", label: "When", render: (r) => <When at={r.created_at} /> }]} />
          </section>
        </div>
      )}

      {tab === "security" && (
        <div className="space-y-6">
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Sessions</h2>
            <DataTable rows={data.sessions} columns={[
              { key: "device", label: "Device", render: (s) => `${s.browser || "?"} on ${s.os || "?"} (${s.device_type || "?"})` },
              { key: "ip", label: "IP", render: (s) => <Mono>{s.ip || "—"}</Mono> }, { key: "method", label: "Method" },
              { key: "last_active_at", label: "Last active", render: (s) => <When at={s.last_active_at} /> },
              { key: "state", label: "State", render: (s) => s.revoked_at ? <Badge>ended · {s.revoked_reason}</Badge> : <Badge tone="success">active</Badge> },
              { key: "x", label: "", render: (s) => !s.revoked_at && can("users.manage") && <Button size="sm" variant="ghost" onClick={() => api(`/admin/users/${id}/sessions/${s.id}`, { method: "DELETE" }).then(() => done("Session ended"))}>End</Button> }]} />
          </section>
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Sign-ins & security events</h2>
            <DataTable rows={data.security_events} columns={[
              { key: "type", label: "Event", render: (e) => e.type.replace(/_/g, " ") }, { key: "severity", label: "Severity", render: (e) => <StatusPill value={e.severity} /> },
              { key: "ip", label: "IP", render: (e) => <Mono>{e.ip || "—"}</Mono> }, { key: "details", label: "Details", render: (e) => <span className="text-xs text-muted">{Object.entries(e.details || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</span> },
              { key: "created_at", label: "When", render: (e) => <When at={e.created_at} /> }]} />
          </section>
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Consents</h2>
            <DataTable rows={data.consents} columns={[
              { key: "kind", label: "Consent", render: (c) => c.kind.replace(/_/g, " ") }, { key: "granted", label: "Choice", render: (c) => c.granted ? <Badge tone="success">granted</Badge> : <Badge>declined</Badge> },
              { key: "version", label: "Version" }, { key: "method", label: "How" }, { key: "created_at", label: "When", render: (c) => <When at={c.created_at} /> }]} />
          </section>
        </div>
      )}

      {tab === "activity" && <Timeline id={id} />}

      {tab === "notes" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="space-y-3 rounded-3xl bg-surface p-5">
            <h2 className="font-semibold text-ink">Internal notes</h2>
            <PrivacyNote>Staff-only. Never shown to the teacher. Don't paste passwords or payment details.</PrivacyNote>
            {can("users.manage") && <div className="space-y-2"><Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add a note…" /><Button size="sm" disabled={!note.trim()} onClick={addNote}>Add note</Button></div>}
            <ul className="space-y-2 text-sm">{data.notes.map((n: any) => <li key={n.id} className="rounded-xl bg-surface-2 p-3"><div className="whitespace-pre-wrap">{n.body}</div><div className="mt-1 text-xs text-muted">{n.author} · <When at={n.created_at} /></div></li>)}</ul>
          </section>
          <section className="rounded-3xl bg-surface p-5"><h2 className="mb-3 font-semibold text-ink">Audit trail for this account</h2>
            <ul className="space-y-2 text-sm">{data.audit.map((a: any) => (
              <li key={a.id} className="rounded-xl bg-surface-2 p-3"><div className="font-medium text-ink">{a.action}</div>
                <div className="text-xs text-muted">{a.actor || "system"} · <When at={a.created_at} />{a.reason && <> · “{a.reason}”</>}</div>
                {(a.before || a.after) && <div className="mt-1 text-xs text-muted">{JSON.stringify(a.before)} → {JSON.stringify(a.after)}</div>}
              </li>))}</ul>
            <Link href={`/admin/audit?target=${id}`} className="mt-3 block text-sm text-brand-600 hover:underline">Open in the audit log</Link>
          </section>
        </div>
      )}

      <ReasonDialog open={!!action} onClose={() => setAction(null)} onConfirm={confirm}
        danger={action?.kind === "status" && action.status !== "active"}
        title={!action ? "" : action.kind === "status" ? (action.status === "active" ? "Restore account" : action.status === "banned" ? "Ban account" : "Suspend account")
          : action.kind === "logout" ? "Sign out everywhere" : action.kind === "credits" ? "Adjust credits" : action.kind === "plan" ? "Change plan" : action.kind === "role" ? "Change staff role" : "Change verification"}
        confirmLabel="Confirm"
        description={!action ? null : action.kind === "status" ? (action.status === "active" ? "The teacher can sign in again and gets an email." : `The teacher is signed out immediately and can't sign in. They get an email with your reason.`)
          : action.kind === "credits" ? `${credits.amount > 0 ? "Add" : "Remove"} ${Math.abs(credits.amount)} ${credits.resource.replace("_", " ")}. Recorded in the credit ledger with your name.`
          : action.kind === "plan" ? (plan.mode === "grant" ? `Grant ${plan.plan} for ${plan.months} month(s). No payment is taken.` : plan.mode === "trial" ? `Extend the trial by ${plan.days} days.` : "End the staff-granted plan or trial now.")
          : action.kind === "logout" ? "Every device is signed out at once." : undefined}>
        {action?.kind === "role" && (
          <Field label="Role"><Select value={role} onChange={(e) => setRole(e.target.value)}>
            {["super_admin", "admin", "support", "analyst", "finance", "moderator"].map((r) => <option key={r} value={r}>{r.replace("_", " ")}</option>)}
            <option value="none">Remove staff access</option></Select></Field>
        )}
      </ReasonDialog>
    </AdminPage>
  );
}

function Timeline({ id }: { id: string }) {
  const list = useCursorList<any>(`/admin/users/${id}/timeline`);
  return (
    <section className="rounded-3xl bg-surface p-5">
      <h2 className="mb-3 font-semibold text-ink">Activity timeline</h2>
      <DataTable rows={list.items} empty="No activity recorded yet." columns={[
        { key: "name", label: "Event", render: (e) => e.name.replace(/_/g, " ") },
        { key: "properties", label: "Details", render: (e) => <span className="text-xs text-muted">{Object.entries(e.properties || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</span> },
        { key: "created_at", label: "When", render: (e) => <When at={e.created_at} /> }]} />
      <LoadMore list={list} />
    </section>
  );
}
