"use client";

import { CircleCheck, CircleAlert, Wrench } from "lucide-react";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { Skeleton } from "@/components/ui";
import { timeAgo } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const LABELS: Record<string, string> = { web_app: "Web app", api: "API", ai_generation: "AI generation", generation_queue: "Lesson building queue" };

function State({ value }: { value: string }) {
  const ok = value === "operational";
  const Icon = ok ? CircleCheck : value === "maintenance" ? Wrench : CircleAlert;
  return <span className={`inline-flex items-center gap-1.5 text-sm font-medium ${ok ? "text-success-700" : "text-warn-600"}`}><Icon className="h-4 w-4" />{value}</span>;
}

export default function StatusPage() {
  const { data, error } = useApi<any>("/status", { refreshInterval: 60_000 });
  return (
    <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]">
      <LandingNav />
      <main className="mx-auto max-w-3xl px-4 py-12 sm:px-6">
        <h1 className="text-3xl font-bold tracking-tight">Clastio status</h1>
        {error ? <p className="mt-6 rounded-2xl bg-[var(--l-card)] p-6">We can't reach the service right now. If this continues, it's likely an outage; we're on it.</p>
          : !data ? <Skeleton className="mt-6 h-64" /> : (
          <>
            <div className="mt-6 flex items-center justify-between rounded-2xl bg-[var(--l-card)] p-6">
              <span className="text-lg font-semibold">{data.status === "operational" ? "All systems operational" : data.status === "maintenance" ? "Scheduled maintenance" : "Some systems degraded"}</span>
              <State value={data.status} />
            </div>
            <ul className="mt-4 divide-y divide-[var(--l-line)] rounded-2xl bg-[var(--l-card)] px-6">
              {Object.entries(data.components).map(([k, v]: any) => <li key={k} className="flex items-center justify-between py-4"><span>{LABELS[k] || k}</span><State value={v} /></li>)}
            </ul>
            {data.notices.length > 0 && (
              <section className="mt-6 space-y-3">
                <h2 className="text-lg font-semibold">Notices</h2>
                {data.notices.map((n: any, i: number) => <div key={i} className="rounded-2xl bg-[var(--l-card)] p-4"><div className="font-medium">{n.title}</div><p className="text-sm text-[var(--l-muted)]">{n.body}</p></div>)}
              </section>
            )}
            <p className="mt-6 text-sm text-[var(--l-muted)]">Updated {timeAgo(data.updated_at)}. Refreshes every minute.</p>
          </>
        )}
      </main>
      <LandingFooter />
    </div>
  );
}
