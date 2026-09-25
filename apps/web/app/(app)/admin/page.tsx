"use client";

import { Activity, CircleCheck, TriangleAlert, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { UserDrawer } from "@/components/admin-user-drawer";
import { BarList, compact } from "@/components/charts";
import { DashHeader, HalfDonut, KpiCard, Legend, Panel, PillButton, PillChart } from "@/components/dash";
import { useToast } from "@/components/toast";
import { Badge, Button, Skeleton, Tabs } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";

const PLAN_NAMES: Record<string, string> = { teacher: "Teacher", pro: "Teacher Pro", assistant: "AI Teaching Assistant" };

function lastDays(points: { date: string; value: number }[], n = 7) {
  const byDate = new Map(points.map((p) => [p.date, p.value]));
  const out = [];
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const value = Number(byDate.get(key) || 0);
    out.push({ label: d.toLocaleDateString(undefined, { weekday: "narrow" }), value, highlight: i === 0,
      title: `${d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}: ${value}` });
  }
  return out;
}

export default function AdminOverview() {
  const { user } = useMe();
  const { notify } = useToast();
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const isAdmin = user?.role === "admin";
  const { data } = useApi<any>(isAdmin ? `/admin/metrics?days=${days}` : null);
  const { data: failed, mutate: refreshFailed } = useApi<any>(isAdmin ? "/admin/jobs?status=failed" : null);
  const { data: plans } = useApi<any>("/billing/plans");
  const [selected, setSelected] = useState<string | null>(null);

  if (user && !isAdmin) return <p className="text-muted">Admins only.</p>;
  if (!data) return <div className="space-y-4"><Skeleton className="h-24 rounded-3xl" /><Skeleton className="h-72 rounded-3xl" /></div>;
  const gen = data.generation;
  const lessonJobs = gen.jobs.lesson_generation || {};
  const byPlan: Record<string, number> = data.users.by_plan;
  const provider = plans?.payment_provider;

  return (
    <div className="space-y-5">
      <DashHeader title="Admin overview" subtitle="Revenue, teachers, generation health and AI spend across PPT Genie."
        actions={<>
          <PillButton href="/admin/media"><Wallet className="h-5 w-5" /> Payments & media</PillButton>
          <PillButton href="/admin/users" variant="outline"><Users className="h-5 w-5" /> Manage users</PillButton>
        </>} />
      <Tabs value={days} onChange={setDays} tabs={[{ value: "7", label: "Last 7 days" }, { value: "30", label: "Last 30 days" }, { value: "90", label: "Last 90 days" }]} />

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard hero label="Monthly revenue" value={compact(data.revenue.mrr_aed, "AED")} hint={`ARR ${compact(data.revenue.arr_aed, "AED")}`} href="/admin/media" />
        <KpiCard label="Teachers" value={compact(data.users.total)} trend={data.users.paid || null} hint={`paid · ${data.users.active_30d} active`} href="/admin/users" />
        <KpiCard label="Lessons generated" value={compact(lessonJobs.succeeded || 0)} hint={`${Math.round(gen.lesson_success_rate * 100)}% success · avg ${Math.round(gen.avg_lesson_seconds)}s`} />
        <KpiCard label="AI spend" value={`$${data.ai.cost_usd.toFixed(2)}`} hint={`$${data.ai.cost_per_project_usd.toFixed(3)} per project`} href="/admin/ai-costs" />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <Panel title="Lessons generated, last 7 days" className="xl:col-span-6">
          <PillChart unit="lessons" points={lastDays(data.series.lessons)} />
        </Panel>

        <Panel title="Platform health" className="flex flex-col xl:col-span-3">
          <ul className="space-y-3 text-sm">
            <li className="flex items-center gap-2">
              {provider ? <CircleCheck className="h-5 w-5 text-brand-600" /> : <TriangleAlert className="h-5 w-5 text-accent-500" />}
              <span className="text-ink-2">{provider ? `Payments via ${provider === "dodo" ? "Dodo Payments" : "Stripe"}` : "No payment gateway set up"}</span>
            </li>
            <li className="flex items-center gap-2">
              {gen.failed ? <TriangleAlert className="h-5 w-5 text-danger-500" /> : <CircleCheck className="h-5 w-5 text-brand-600" />}
              <span className="text-ink-2">{gen.failed ? `${gen.failed} failed jobs in period` : "No failed jobs"}</span>
            </li>
            <li className="flex items-center gap-2"><Activity className="h-5 w-5 text-brand-600" /><span className="text-ink-2">{compact(data.ai.calls)} AI calls · {data.storage_mb} MB stored</span></li>
          </ul>
          <div className="mt-auto pt-5">
            <PillButton href={provider ? "/admin/ai-costs" : "/admin/media"}>{provider ? "View AI costs" : "Set up payments"}</PillButton>
          </div>
        </Panel>

        <Panel title="New sign-ups" className="xl:col-span-3" action={<Link href="/admin/users" className="text-sm font-semibold text-brand-600 hover:underline">All</Link>}>
          <ul className="space-y-4">
            {data.recent_signups.map((u: any) => (
              <li key={u.id}>
                <button onClick={() => setSelected(u.id)} className="flex w-full items-center gap-3 text-start">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 font-semibold text-white">{(u.name || u.email).slice(0, 1).toUpperCase()}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-ink">{u.name || u.email}</span>
                    <span className="block truncate text-xs text-muted">{timeAgo(u.created_at)} · {u.plan}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Most-used subjects" className="xl:col-span-5">
          <BarList items={data.popular.subjects.map((s: any) => ({ name: s.name, value: s.count }))} />
          <div className="mt-6 grid gap-6 sm:grid-cols-2">
            <div><div className="mb-2 text-sm font-medium text-ink">Grades</div><BarList items={data.popular.grades.map((s: any) => ({ name: `Grade ${s.name}`, value: s.count }))} /></div>
            <div><div className="mb-2 text-sm font-medium text-ink">Documents</div><BarList items={data.popular.documents.map((s: any) => ({ name: s.name.replace("_", " "), value: s.count }))} /></div>
          </div>
        </Panel>

        <Panel title="Paying teachers" className="xl:col-span-4">
          <HalfDonut total={data.users.total} center={`${data.users.total ? Math.round((data.users.paid / data.users.total) * 100) : 0}%`} caption="on a paid plan"
            segments={[{ label: "Paid", value: data.users.paid, className: "text-brand-600" }]} />
          <Legend items={[
            ...Object.entries(PLAN_NAMES).map(([code, name]) => ({ label: name, className: "bg-brand-600", value: byPlan[code] || 0 })),
            { label: "Free", striped: true, value: data.users.total - data.users.paid },
          ]} />
        </Panel>

        <section className="ui-hero flex flex-col rounded-3xl bg-brand-800 p-6 text-white xl:col-span-3">
          <h2 className="text-lg font-semibold sm:text-xl">Lesson success rate</h2>
          <div className="my-5 text-5xl font-bold tabular-nums tracking-tight">{Math.round(gen.lesson_success_rate * 100)}%</div>
          <div className="space-y-1 text-sm text-white/80">
            <div>{compact(lessonJobs.succeeded || 0)} built · {lessonJobs.failed || 0} failed</div>
            <div>Average {Math.round(gen.avg_lesson_seconds)} s per lesson</div>
            <div>{gen.projects} projects in total</div>
          </div>
          <Link href="#failed" className="mt-auto flex items-center justify-center gap-2 rounded-full bg-white py-3 text-sm font-semibold text-brand-800 hover:bg-white/90">
            <Activity className="h-4 w-4" /> Review failures
          </Link>
        </section>
      </div>

      <section id="failed" className="rounded-3xl bg-surface p-5 sm:p-6">
        <h2 className="mb-4 text-lg font-semibold text-ink sm:text-xl">Failed jobs</h2>
        <ul className="divide-y divide-line">
          {(failed?.items || []).slice(0, 10).map((j: any) => (
            <li key={j.id} className="flex items-start justify-between gap-3 py-3 text-sm">
              <div className="min-w-0"><div className="flex items-center gap-2 font-medium text-ink">{j.type}<Badge tone="danger">failed</Badge></div><div className="truncate text-xs text-muted">{j.error}</div></div>
              <Button size="sm" variant="outline" onClick={async () => { await api(`/admin/jobs/${j.id}/retry`, { method: "POST" }); notify({ tone: "success", title: "Job re-queued" }); refreshFailed(); }}>Retry</Button>
            </li>
          ))}
          {!failed?.items?.length && <li className="py-4 text-sm text-muted">No failed jobs.</li>}
        </ul>
      </section>
      <UserDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
