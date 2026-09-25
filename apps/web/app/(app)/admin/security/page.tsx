"use client";

import Link from "next/link";
import { useState } from "react";
import { AdminPage, DataTable, ExportButton, FilterBar, LoadMore, Mono, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { Field, Input, Select } from "@/components/ui";

const TYPES = ["login_failed", "login_success", "new_device", "password_reset_requested", "password_reset", "password_changed", "session_revoked", "rate_limited",
  "suspicious_request", "admin_role_changed", "account_suspended", "account_banned", "account_restored", "webhook_rejected", "trial_abuse", "provider_circuit_open", "deletion_requested"];

export default function SecurityEvents() {
  const [f, setF] = useState({ type: "", severity: "", ip: "", days: "30" });
  const qs = new URLSearchParams({ limit: "50", days: f.days });
  for (const k of ["type", "severity", "ip"] as const) if (f[k]) qs.set(k, f[k]);
  const list = useCursorList<any>(`/admin/security-events?${qs}`);
  const summary = list.extra?.last_24h || [];
  return (
    <AdminPage title="Security events" perm="security.view" subtitle="Sign-ins, failed logins, new devices, rate limiting, suspicious requests and admin role changes."
      actions={<ExportButton dataset="security_events" days={Number(f.days)} />}>
      {summary.length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="text-muted">Last 24 h:</span>
          {summary.map((s: any) => <button key={s.type + s.severity} onClick={() => setF({ ...f, type: s.type })} className="rounded-full bg-surface px-3 py-1 hover:bg-surface-2">{s.type.replace(/_/g, " ")} <b>{s.count}</b></button>)}
        </div>
      )}
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <FilterBar>
          <Field label="Type"><Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value })}><option value="">All</option>{TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}</Select></Field>
          <Field label="Severity"><Select value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}><option value="">All</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option></Select></Field>
          <Field label="IP"><Input value={f.ip} onChange={(e) => setF({ ...f, ip: e.target.value })} /></Field>
          <Field label="Period"><Select value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })}><option value="1">24 hours</option><option value="7">7 days</option><option value="30">30 days</option><option value="365">1 year</option></Select></Field>
        </FilterBar>
        <DataTable rows={list.items} columns={[
          { key: "type", label: "Event", render: (e) => e.type.replace(/_/g, " ") },
          { key: "severity", label: "Severity", render: (e) => <StatusPill value={e.severity} /> },
          { key: "email", label: "Account", render: (e) => e.user_id ? <Link className="text-brand-600 hover:underline" href={`/admin/users/${e.user_id}`}>{e.email || "account"}</Link> : "—" },
          { key: "ip", label: "IP", render: (e) => <button className="font-mono text-xs hover:underline" onClick={() => setF({ ...f, ip: e.ip || "" })}>{e.ip || "—"}</button> },
          { key: "details", label: "Details", render: (e) => <span className="text-xs text-muted">{Object.entries(e.details || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</span> },
          { key: "request_id", label: "Request", render: (e) => e.request_id ? <Link href={`/admin/system?trace=${e.request_id}`}><Mono>{e.request_id}</Mono></Link> : "—" },
          { key: "created_at", label: "When", render: (e) => <When at={e.created_at} /> }]} />
        <LoadMore list={list} />
      </section>
    </AdminPage>
  );
}
