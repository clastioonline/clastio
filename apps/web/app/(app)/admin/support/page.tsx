"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AdminPage, DataTable, FilterBar, LoadMore, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { Field, Select } from "@/components/ui";

export default function SupportDesk() {
  const router = useRouter();
  const [f, setF] = useState({ status: "active", kind: "", priority: "" });
  const qs = new URLSearchParams({ limit: "50" });
  for (const [k, v] of Object.entries(f)) if (v) qs.set(k, v);
  const list = useCursorList<any>(`/admin/support/tickets?${qs}`);
  const counts = list.extra?.counts || {};
  return (
    <AdminPage title="Tickets & requests" perm="support.manage" subtitle={`Open ${counts.open || 0} · waiting on teacher ${counts.pending || 0} · resolved ${counts.resolved || 0}. Feature requests are tickets of their own kind.`}>
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <FilterBar>
          <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}>
            <option value="active">Open & pending</option><option value="">All</option>{["open", "pending", "resolved", "closed", "planned", "declined"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Type"><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="">All</option><option value="support">Support</option><option value="bug">Bug</option><option value="billing">Billing</option><option value="feature_request">Feature request</option></Select></Field>
          <Field label="Priority"><Select value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="">Any</option>{["urgent", "high", "normal", "low"].map((p) => <option key={p}>{p}</option>)}</Select></Field>
        </FilterBar>
        <DataTable rows={list.items} onRowClick={(t) => router.push(`/admin/support/${t.id}`)} empty="Nothing waiting. Nice." columns={[
          { key: "number", label: "#", render: (t) => `#${t.number}` },
          { key: "subject", label: "Subject", render: (t) => <><span className="block font-medium text-ink">{t.subject}</span><span className="text-xs text-muted">{t.email} · {t.kind.replace("_", " ")}</span></> },
          { key: "priority", label: "Priority", render: (t) => <StatusPill value={t.priority} /> },
          { key: "status", label: "Status", render: (t) => <StatusPill value={t.status} /> },
          { key: "assigned_to", label: "Assignee", render: (t) => t.assigned_to || <span className="text-muted">—</span> },
          { key: "updated_at", label: "Updated", render: (t) => <When at={t.updated_at} /> }]} />
        <LoadMore list={list} />
      </section>
    </AdminPage>
  );
}
