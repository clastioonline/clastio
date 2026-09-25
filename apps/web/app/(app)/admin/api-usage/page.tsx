"use client";

import { useState } from "react";
import { AdminPage, DataTable, ExportButton, FilterBar } from "@/components/admin-kit";
import { BarList, ColumnChart, compact } from "@/components/charts";
import { Panel } from "@/components/dash";
import { Field, Input, Select, Skeleton } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function ApiUsage() {
  const [f, setF] = useState({ days: "7", route: "", status: "" });
  const qs = new URLSearchParams({ days: f.days });
  if (f.route) qs.set("route", f.route);
  if (f.status) qs.set("status", f.status);
  const { data } = useApi<any>(`/admin/api-usage?${qs}`);
  const t = data?.totals;
  const ms = (v: number | null) => (v == null ? "—" : `${v} ms`);
  return (
    <AdminPage title="API usage" perm="api_usage.view" subtitle="Requests, latency, errors and rate limiting, plus AI calls, tokens and cost by model."
      actions={<ExportButton dataset="ai_usage" days={Number(f.days)} />}>
      <FilterBar>
        <Field label="Period"><Select value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })}><option value="1">24 hours</option><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option></Select></Field>
        <Field label="Route"><Input value={f.route} onChange={(e) => setF({ ...f, route: e.target.value })} placeholder="/api/v1/courses" /></Field>
        <Field label="Outcome"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="">All</option><option value="error">Server errors</option><option value="client_error">Client errors</option><option value="rate_limited">Rate limited</option></Select></Field>
      </FilterBar>
      {!data ? <Skeleton className="h-96" /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            {[["Requests", compact(t.requests)], ["Server errors", `${t.server_errors} (${(t.error_rate * 100).toFixed(2)}%)`], ["Rate limited", t.rate_limited],
              ["Avg latency", ms(t.avg_ms)], ["P50", ms(t.p50_ms)], ["P95", ms(t.p95_ms)], ["P99", ms(t.p99_ms)]].map(([l, v]) => (
              <div key={l as string} className="rounded-2xl bg-surface p-4"><div className="text-xs text-muted">{l}</div><div className="mt-1 text-xl font-bold tabular-nums">{v}</div></div>
            ))}
          </div>
          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="Requests per day"><ColumnChart label="Requests" days={Number(f.days)} points={data.per_day.map((d: any) => ({ date: d.day, value: d.requests }))} /></Panel>
            <Panel title="AI cost per day (USD)"><ColumnChart label="AI cost" days={Number(f.days)} format={(v) => `$${v.toFixed(2)}`} points={data.ai.per_day.map((d: any) => ({ date: d.day, value: d.cost_usd }))} /></Panel>
          </div>
          <Panel title="Endpoints">
            <DataTable rows={data.by_route} rowKey="route" columns={[
              { key: "route", label: "Endpoint", render: (r) => <span className="font-mono text-xs">{r.method} {r.route}</span> },
              { key: "requests", label: "Requests", render: (r) => compact(r.requests) }, { key: "errors", label: "5xx" },
              { key: "avg_ms", label: "Avg", render: (r) => ms(r.avg_ms) }, { key: "p95_ms", label: "P95", render: (r) => ms(r.p95_ms) }, { key: "p99_ms", label: "P99", render: (r) => ms(r.p99_ms) }]} />
          </Panel>
          <div className="grid gap-5 xl:grid-cols-2">
            <Panel title="Busiest accounts"><DataTable rows={data.by_user} rowKey="user_id" columns={[
              { key: "email", label: "Account" }, { key: "requests", label: "Requests" }, { key: "errors", label: "5xx" }, { key: "rate_limited", label: "429s" }]} /></Panel>
            <Panel title="Top AI spend"><BarList format={(v) => `$${v.toFixed(3)}`} items={data.ai.top_spenders.map((s: any) => ({ name: s.email || s.user_id, value: s.cost_usd, hint: `${s.calls} calls` }))} /></Panel>
          </div>
          <Panel title="AI models">
            <DataTable rows={data.ai.by_model} rowKey="model" columns={[
              { key: "model", label: "Model", render: (m) => `${m.provider}:${m.model}` }, { key: "calls", label: "Calls" },
              { key: "failures", label: "Failures" }, { key: "tokens", label: "Tokens", render: (m) => compact(m.tokens) },
              { key: "cost_usd", label: "Cost", render: (m) => `$${m.cost_usd.toFixed(3)}` }, { key: "p95_ms", label: "P95", render: (m) => ms(m.p95_ms) }]} />
            {data.ai.errors.length > 0 && <p className="mt-3 text-sm text-muted">Failures by cause: {data.ai.errors.map((e: any) => `${e.code} ×${e.count}`).join(", ")}</p>}
          </Panel>
        </>
      )}
    </AdminPage>
  );
}
