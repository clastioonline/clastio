"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminPage, DataTable, JsonBlock, LoadMore, Mono, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { Panel } from "@/components/dash";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Input, Skeleton, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Tab = "health" | "jobs" | "webhooks" | "emails" | "trace";

export default function SystemPage() {
  const [tab, setTab] = useState<Tab>("health");
  const [trace, setTrace] = useState("");
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get("trace")) { setTrace(p.get("trace")!); setTab("trace"); } else if (p.get("job")) setTab("jobs");
  }, []);
  return (
    <AdminPage title="Health & logs" perm="system.logs.view" subtitle="Readiness, AI providers, the job queue, webhooks, email delivery and request traces.">
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "health", label: "Health" }, { value: "jobs", label: "Jobs" }, { value: "webhooks", label: "Webhooks" }, { value: "emails", label: "Emails" }, { value: "trace", label: "Request trace" }]} />
      {tab === "health" && <Health />}
      {tab === "jobs" && <Jobs />}
      {tab === "webhooks" && <Webhooks />}
      {tab === "emails" && <Emails />}
      {tab === "trace" && <Trace initial={trace} />}
    </AdminPage>
  );
}

function Health() {
  const { data } = useApi<any>("/admin/system/health", { refreshInterval: 30_000 });
  if (!data) return <Skeleton className="h-72" />;
  const r = data.ready;
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Panel title="Readiness">
        <ul className="space-y-2 text-sm">
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Overall</span><StatusPill value={r.status === "ready" ? "operational" : "degraded"} /></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Database</span><span>{r.checks.database?.ok ? `ok · ${r.checks.database.ms} ms` : "down"}</span></li>
          {r.checks.redis && <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Redis</span><span>{r.checks.redis.ok ? "ok" : "down"}</span></li>}
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Migration</span><Mono>{r.checks.migration || "n/a"}</Mono></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Version</span><Mono>{r.version}</Mono></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>AI mode</span><span>{r.checks.ai.mode} · {r.checks.ai.providers.join(", ") || "none configured"}</span></li>
        </ul>
      </Panel>
      <Panel title="Last hour & queue">
        <ul className="space-y-2 text-sm">
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>API requests</span><span>{data.api_last_hour.requests} · {(data.api_last_hour.error_rate * 100).toFixed(2)}% errors</span></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Queued jobs now</span><span>{data.queue.queued_now}{data.queue.oldest_queued_minutes > 10 && <b className="text-warn-600"> · oldest {data.queue.oldest_queued_minutes} min</b>}</span></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Jobs (24 h)</span><span>{Object.entries(data.queue.last_24h).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}</span></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Emails (7 d)</span><span>{Object.entries(data.emails_7d).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}</span></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Webhooks (7 d)</span><span>{Object.entries(data.webhooks_7d).map(([k, v]) => `${k} ${v}`).join(" · ") || "none"}</span></li>
          <li className="flex flex-wrap justify-between gap-x-3 gap-y-1 break-words"><span>Critical security events (24 h)</span><Link href="/admin/security?severity=critical" className={data.critical_security_events_24h ? "font-semibold text-danger-700" : ""}>{data.critical_security_events_24h}</Link></li>
        </ul>
      </Panel>
      <Panel title="AI providers" className="lg:col-span-2">
        <DataTable rows={data.providers} rowKey="provider" empty="No AI calls recorded yet." columns={[
          { key: "provider", label: "Provider" }, { key: "circuit_open", label: "Circuit", render: (p) => <StatusPill value={p.circuit_open ? "failed" : "operational"} /> },
          { key: "failures", label: "Consecutive failures" }, { key: "avg_latency_ms", label: "Avg latency", render: (p) => `${p.avg_latency_ms} ms` },
          { key: "last_error", label: "Last error", render: (p) => <span className="line-clamp-2 text-xs text-muted">{p.last_error}</span> },
          { key: "updated_at", label: "Updated", render: (p) => <When at={p.updated_at} /> }]} />
      </Panel>
    </div>
  );
}

function Jobs() {
  const [status, setStatus] = useState("failed");
  const { data, mutate } = useApi<any>(`/admin/jobs?status=${status}`);
  const { notify } = useToast();
  const retry = async (id: string) => {
    try { await api(`/admin/jobs/${id}/retry`, { method: "POST" }); notify({ tone: "success", title: "Job re-queued" }); mutate(); } catch (e) { notify({ tone: "error", title: errorMessage(e) }); }
  };
  return (
    <section className="rounded-3xl bg-surface p-5">
      <Tabs value={status} onChange={setStatus} tabs={["failed", "queued", "running", "succeeded"].map((s) => ({ value: s, label: s }))} />
      <div className="mt-4"><DataTable rows={data?.items || []} columns={[
        { key: "type", label: "Job" }, { key: "status", label: "Status", render: (j) => <StatusPill value={j.status} /> }, { key: "attempts", label: "Tries" },
        { key: "error", label: "Error", render: (j) => <span className="line-clamp-2 text-xs text-danger-700">{j.error || ""}</span> },
        { key: "owner", label: "Owner", render: (j) => j.owner_id ? <Link className="text-brand-600 hover:underline" href={`/admin/users/${j.owner_id}`}>open</Link> : "—" },
        { key: "created_at", label: "Created", render: (j) => <When at={j.created_at} /> },
        { key: "x", label: "", render: (j) => j.status === "failed" && <Button size="sm" variant="outline" onClick={() => retry(j.id)}>Retry</Button> }]} /></div>
    </section>
  );
}

function Webhooks() {
  const [status, setStatus] = useState("");
  const list = useCursorList<any>(`/admin/webhooks?limit=50${status ? `&status=${status}` : ""}`);
  return (
    <section className="rounded-3xl bg-surface p-5">
      <Tabs value={status} onChange={setStatus} tabs={[{ value: "", label: "All" }, { value: "failed", label: "Failed" }, { value: "processed", label: "Processed" }, { value: "ignored", label: "Ignored" }]} />
      <div className="mt-4"><DataTable rows={list.items} columns={[
        { key: "provider", label: "Gateway" }, { key: "type", label: "Event" }, { key: "status", label: "Status", render: (w) => <StatusPill value={w.status} /> },
        { key: "retry_count", label: "Retries" }, { key: "event_id", label: "Event id", render: (w) => <Mono>{w.event_id.slice(0, 24)}</Mono> },
        { key: "error_message", label: "Error", render: (w) => <span className="line-clamp-2 text-xs text-danger-700">{w.error_message || ""}</span> },
        { key: "created_at", label: "Received", render: (w) => <When at={w.created_at} /> }]} /></div>
      <LoadMore list={list} />
    </section>
  );
}

function Emails() {
  const [status, setStatus] = useState("");
  const list = useCursorList<any>(`/admin/emails?limit=50${status ? `&status=${status}` : ""}`);
  const { notify } = useToast();
  return (
    <section className="rounded-3xl bg-surface p-5">
      <Tabs value={status} onChange={setStatus} tabs={[{ value: "", label: "All" }, { value: "queued", label: "Queued" }, { value: "failed", label: "Failed" }, { value: "sent", label: "Sent" }, { value: "logged", label: "Logged (no SMTP)" }]} />
      <div className="mt-4"><DataTable rows={list.items} columns={[
        { key: "template", label: "Email" }, { key: "to", label: "To" }, { key: "status", label: "Status", render: (e) => <StatusPill value={e.status} /> },
        { key: "attempts", label: "Tries" }, { key: "last_error", label: "Error", render: (e) => <span className="line-clamp-2 text-xs text-muted">{e.last_error || ""}</span> },
        { key: "created_at", label: "Queued", render: (e) => <When at={e.created_at} /> },
        { key: "x", label: "", render: (e) => e.status === "failed" && <Button size="sm" variant="outline" onClick={() => api(`/admin/emails/${e.id}/retry`, { method: "POST" }).then(() => { notify({ tone: "success", title: "Re-queued" }); list.reload(); })}>Retry</Button> }]} /></div>
      <LoadMore list={list} />
    </section>
  );
}

function Trace({ initial }: { initial: string }) {
  const [rid, setRid] = useState(initial);
  const [q, setQ] = useState(initial);
  const { data, error } = useApi<any>(q ? `/admin/trace/${encodeURIComponent(q)}` : null);
  return (
    <section className="space-y-4 rounded-3xl bg-surface p-5">
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); setQ(rid.trim()); }}>
        <Input value={rid} onChange={(e) => setRid(e.target.value)} placeholder="req_… (shown to users in error messages as “ref”)" aria-label="Request id" />
        <Button type="submit">Trace</Button>
      </form>
      {error && <Alert tone="warn">Nothing recorded for that request id.</Alert>}
      {data && (
        <div className="space-y-4 text-sm">
          {data.request && <p><Mono>{data.request.method} {data.request.route}</Mono> → <b>{data.request.status}</b> in {data.request.duration_ms} ms {data.request.error_code && <>· {data.request.error_code}</>} · <When at={data.request.created_at} />
            {data.request.user_id && <> · <Link className="text-brand-600 hover:underline" href={`/admin/users/${data.request.user_id}`}>user</Link></>}</p>}
          {[["AI calls", data.ai_calls], ["Jobs", data.jobs], ["Credit ledger", data.ledger], ["Security events", data.security_events], ["Audit", data.audit]].map(([label, rows]: any) =>
            rows.length > 0 && <div key={label}><div className="mb-1 font-medium text-ink">{label}</div><JsonBlock value={rows} /></div>)}
        </div>
      )}
    </section>
  );
}
