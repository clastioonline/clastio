"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { BarList, ColumnChart, compact } from "@/components/charts";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, Field, Input, Modal, PageHeader, Select, Skeleton, Stat, Tabs } from "@/components/ui";
import { api, formatDate, timeAgo } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";

function UserDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(id ? `/admin/users/${id}` : null);
  const [plan, setPlan] = useState("assistant");
  const [months, setMonths] = useState(1);
  const act = async (body: any) => {
    try {
      await api(`/admin/users/${id}`, { method: "PATCH", body });
      notify({ tone: "success", title: "Updated" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Failed", body: errorMessage(e) });
    }
  };
  return (
    <Modal open={!!id} onClose={onClose} title={data?.user?.email || "User"} size="lg">
      {!data ? <Skeleton className="h-40" /> : (
        <div className="space-y-5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.user.status === "active" ? "success" : "danger"}>{data.user.status}</Badge>
            <Badge>{data.user.role}</Badge>
            <Badge tone="brand">{data.usage.plan.name}</Badge>
            <span className="text-muted">joined {formatDate(data.user.created_at)} · AI cost ${data.usage.ai_cost_usd}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(data.usage.usage).map(([k, v]: any) => (
              <div key={k} className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted">{k.replace("_", " ")}</div><div className="font-semibold tabular-nums">{v.used} / {v.limit === -1 ? "∞" : v.limit ?? "—"}</div></div>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Grant plan"><Select value={plan} onChange={(e) => setPlan(e.target.value)}>{["teacher", "pro", "assistant"].map((p) => <option key={p}>{p}</option>)}</Select></Field>
            <Field label="Months"><Input type="number" min={1} max={36} value={months} onChange={(e) => setMonths(Number(e.target.value))} /></Field>
            <Button onClick={() => act({ plan, months })}>Grant</Button>
            <Button variant="outline" onClick={() => act({ credits_grant: 200 })}>+200 credits</Button>
            {data.user.status === "active" ? <Button variant="danger" onClick={() => act({ status: "suspended" })}>Suspend</Button> : <Button variant="outline" onClick={() => act({ status: "active" })}>Reactivate</Button>}
          </div>
          <div>
            <div className="mb-2 font-medium text-ink">Projects</div>
            <ul className="space-y-1">{data.projects.map((p: any) => <li key={p.id} className="flex justify-between"><span>{p.topic} · Grade {p.grade}</span><Badge>{p.status}</Badge></li>)}</ul>
          </div>
          <div>
            <div className="mb-2 font-medium text-ink">Recent jobs</div>
            <ul className="space-y-1">{data.jobs.map((j: any) => <li key={j.id} className="flex justify-between gap-2"><span className="truncate">{j.type} · {timeAgo(j.created_at)}</span><Badge tone={j.status === "failed" ? "danger" : "neutral"}>{j.status}</Badge></li>)}</ul>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default function Admin() {
  const { user } = useMe();
  const { notify } = useToast();
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const { data } = useApi<any>(user?.role === "admin" ? `/admin/metrics?days=${days}` : null);
  const [q, setQ] = useState("");
  const { data: users } = useApi<any>(user?.role === "admin" ? `/admin/users?limit=50${q ? `&q=${encodeURIComponent(q)}` : ""}` : null);
  const { data: failed, mutate: refreshFailed } = useApi<any>(user?.role === "admin" ? "/admin/jobs?status=failed" : null);
  const [selected, setSelected] = useState<string | null>(null);

  if (user && user.role !== "admin") return <p className="text-muted">Admins only.</p>;
  if (!data) return <div className="space-y-4"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>;
  const gen = data.generation;
  const lessonJobs = gen.jobs.lesson_generation || {};

  return (
    <div className="space-y-6">
      <PageHeader title="Admin" subtitle="Platform health, revenue, usage and users" />
      <Tabs value={days} onChange={setDays} tabs={[{ value: "7", label: "Last 7 days" }, { value: "30", label: "Last 30 days" }, { value: "90", label: "Last 90 days" }]} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="MRR" value={compact(data.revenue.mrr_aed, "AED")} hint={`ARR ${compact(data.revenue.arr_aed, "AED")}`} />
        <Stat label="Users" value={compact(data.users.total)} hint={`${data.users.active_30d} active · ${data.users.paid} paid`} />
        <Stat label="Lessons generated" value={compact(lessonJobs.succeeded || 0)} hint={`${Math.round(gen.lesson_success_rate * 100)}% success · avg ${Math.round(gen.avg_lesson_seconds)}s`} />
        <Stat label="AI cost" value={`$${data.ai.cost_usd.toFixed(2)}`} hint={`$${data.ai.cost_per_project_usd.toFixed(3)} per project`} />
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card><CardHeader title="Lessons generated per day" /><div className="p-5"><ColumnChart points={data.series.lessons} days={Number(days)} label="Lessons" /></div></Card>
        <Card><CardHeader title="AI cost per day (USD)" /><div className="p-5"><ColumnChart points={data.series.ai_cost} days={Number(days)} label="AI cost" format={(v) => `$${v.toFixed(v < 1 ? 2 : 0)}`} /></div></Card>
        <Card><CardHeader title="Sign-ups per day" /><div className="p-5"><ColumnChart points={data.series.signups} days={Number(days)} label="Sign-ups" /></div></Card>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card><CardHeader title="Most-used subjects" /><div className="p-5"><BarList items={data.popular.subjects.map((s: any) => ({ name: s.name, value: s.count }))} /></div></Card>
        <Card><CardHeader title="Most-used grades" /><div className="p-5"><BarList items={data.popular.grades.map((s: any) => ({ name: `Grade ${s.name}`, value: s.count }))} /></div></Card>
        <Card><CardHeader title="Documents created" /><div className="p-5"><BarList items={data.popular.documents.map((s: any) => ({ name: s.name.replace("_", " "), value: s.count }))} /></div></Card>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="Users" action={<div className="relative w-56"><Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" /><Input className="h-9 ps-9" placeholder="Search email…" value={q} onChange={(e) => setQ(e.target.value)} /></div>} />
          <div className="overflow-x-auto p-2">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-muted"><tr><th className="px-3 py-2 text-start">User</th><th className="px-3 py-2 text-start">Plan</th><th className="px-3 py-2 text-start">Last login</th><th className="px-3 py-2 text-start">Status</th></tr></thead>
              <tbody className="divide-y divide-line">
                {(users?.items || []).map((u: any) => (
                  <tr key={u.id} className="cursor-pointer hover:bg-surface-2/60" onClick={() => setSelected(u.id)}>
                    <td className="px-3 py-2"><div className="font-medium text-ink">{u.name || "—"}</div><div className="text-xs text-muted">{u.email}</div></td>
                    <td className="px-3 py-2"><Badge tone={u.plan === "free" ? "neutral" : "brand"}>{u.plan}</Badge></td>
                    <td className="px-3 py-2 text-muted">{u.last_login_at ? timeAgo(u.last_login_at) : "—"}</td>
                    <td className="px-3 py-2"><Badge tone={u.status === "active" ? "success" : "danger"}>{u.status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Failed jobs" subtitle={`${gen.failed} in period`} />
            <ul className="divide-y divide-line">
              {(failed?.items || []).slice(0, 8).map((j: any) => (
                <li key={j.id} className="flex items-start justify-between gap-3 px-5 py-3 text-sm">
                  <div className="min-w-0"><div className="font-medium text-ink">{j.type}</div><div className="truncate text-xs text-muted">{j.error}</div></div>
                  <Button size="sm" variant="outline" onClick={async () => { await api(`/admin/jobs/${j.id}/retry`, { method: "POST" }); notify({ tone: "success", title: "Job re-queued" }); refreshFailed(); }}>Retry</Button>
                </li>
              ))}
              {!failed?.items?.length && <li className="px-5 py-4 text-sm text-muted">No failed jobs 🎉</li>}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Other usage" />
            <div className="space-y-2 p-5 text-sm">
              <div className="flex justify-between"><span className="text-muted">Storage</span><span className="tabular-nums">{data.storage_mb} MB</span></div>
              <div className="flex justify-between"><span className="text-muted">AI calls</span><span className="tabular-nums">{compact(data.ai.calls)}</span></div>
              <div className="flex justify-between"><span className="text-muted">AI tokens</span><span className="tabular-nums">{compact(data.ai.tokens)}</span></div>
              <div className="flex justify-between"><span className="text-muted">WhatsApp messages</span><span className="tabular-nums">{data.whatsapp.reduce((a: number, w: any) => a + w.count, 0)}</span></div>
              <div className="flex justify-between"><span className="text-muted">Paid by plan</span><span>{Object.entries(data.users.by_plan).map(([k, v]) => `${k}: ${v}`).join(" · ") || "—"}</span></div>
            </div>
          </Card>
        </div>
      </div>
      <UserDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
