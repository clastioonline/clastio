"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AdminPage, DataTable, ExportButton, FilterBar, JsonBlock, LoadMore, Mono, PrivacyNote, When, useCursorList } from "@/components/admin-kit";
import { Field, Input, Modal, Select } from "@/components/ui";

export default function AuditLog() {
  const [f, setF] = useState({ action: "", target: "", days: "90" });
  useEffect(() => { const t = new URLSearchParams(window.location.search).get("target"); if (t) setF((x) => ({ ...x, target: t })); }, []);
  const qs = new URLSearchParams({ limit: "50", days: f.days });
  if (f.action) qs.set("action", f.action);
  if (f.target) qs.set("target", f.target);
  const list = useCursorList<any>(`/admin/audit-logs?${qs}`);
  const [open, setOpen] = useState<any>(null);
  return (
    <AdminPage title="Audit log" perm="audit.view" subtitle="Every staff action with who, when, before/after values and reason. Append-only: entries can't be edited or deleted."
      actions={<ExportButton dataset="audit_logs" days={Number(f.days)} />}>
      <PrivacyNote>Viewing a teacher's profile and exporting data are logged here too ("data_access" and "data.export").</PrivacyNote>
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <FilterBar>
          <Field label="Action starts with"><Select value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })}>
            <option value="">All</option>{["user.", "credits.", "staff.", "plan.", "setting.", "legal.", "announcement.", "support.", "data.", "data_access.", "job.", "email."].map((a) => <option key={a} value={a}>{a}</option>)}</Select></Field>
          <Field label="Target (user id or object id)"><Input value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })} /></Field>
          <Field label="Period"><Select value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })}><option value="7">7 days</option><option value="90">90 days</option><option value="365">1 year</option><option value="3650">All</option></Select></Field>
        </FilterBar>
        <DataTable rows={list.items} onRowClick={setOpen} columns={[
          { key: "action", label: "Action", render: (a) => <span className="font-medium text-ink">{a.action}</span> },
          { key: "actor", label: "By", render: (a) => a.actor || "system" },
          { key: "target", label: "Target", render: (a) => a.target_email ? <Link onClick={(e) => e.stopPropagation()} className="text-brand-600 hover:underline" href={`/admin/users/${a.target}`}>{a.target_email}</Link> : a.target_id ? <Mono>{a.target_type}:{String(a.target_id).slice(0, 12)}</Mono> : "—" },
          { key: "reason", label: "Reason", render: (a) => <span className="line-clamp-2 text-xs text-muted">{a.reason || ""}</span> },
          { key: "created_at", label: "When", render: (a) => <When at={a.created_at} /> }]} />
        <LoadMore list={list} />
      </section>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open?.action || ""} size="lg">
        {open && (
          <div className="space-y-3 text-sm">
            <p className="text-muted">By {open.actor || "system"} · {new Date(open.created_at).toLocaleString()} · IP <Mono>{open.ip || "—"}</Mono> · request <Mono>{open.request_id || "—"}</Mono></p>
            {open.reason && <p><b>Reason:</b> {open.reason}</p>}
            <div className="grid gap-3 md:grid-cols-2"><div><div className="mb-1 font-medium">Before</div><JsonBlock value={open.before} /></div><div><div className="mb-1 font-medium">After</div><JsonBlock value={open.after} /></div></div>
            <div><div className="mb-1 font-medium">Details</div><JsonBlock value={open.details} /></div>
          </div>
        )}
      </Modal>
    </AdminPage>
  );
}
