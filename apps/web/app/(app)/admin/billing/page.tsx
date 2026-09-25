"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminPage, DataTable, ExportButton, FilterBar, LoadMore, Mono, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { Field, Select, Tabs } from "@/components/ui";
import { formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function BillingAdmin() {
  const router = useRouter();
  const [tab, setTab] = useState<"payments" | "subscriptions">("payments");
  const [status, setStatus] = useState("");
  const [ref, setRef] = useState("");
  useEffect(() => { setRef(new URLSearchParams(window.location.search).get("ref") || ""); }, []);
  const payments = useCursorList<any>(`/admin/payments?limit=50${status ? `&status=${status}` : ""}`);
  const { data: subs } = useApi<any>(tab === "subscriptions" ? "/admin/subscriptions" : null);
  const rows = ref ? payments.items.filter((p) => p.provider_ref === ref) : payments.items;
  return (
    <AdminPage title="Subscriptions & payments" perm="billing.view" subtitle="Every charge, failure and subscription. Refunds and plan changes for gateway subscriptions are made in the payment gateway."
      actions={<ExportButton dataset={tab === "payments" ? "payments" : "subscriptions"} days={365} />}>
      {payments.extra?.last_30d && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {payments.extra.last_30d.map((s: any) => (
            <div key={s.status} className="rounded-2xl bg-surface p-4"><div className="text-xs text-muted">{s.status} · 30 days</div><div className="text-2xl font-bold tabular-nums">{s.count}</div><div className="text-xs text-muted">AED {s.amount.toLocaleString()}</div></div>
          ))}
        </div>
      )}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: "payments", label: "Payments" }, { value: "subscriptions", label: "Subscriptions" }]} />
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        {tab === "payments" ? (
          <>
            <FilterBar>
              <Field label="Status"><Select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">Any</option><option value="paid">Paid</option><option value="failed">Failed</option><option value="refunded">Refunded</option></Select></Field>
              {ref && <button className="text-sm text-brand-600 underline" onClick={() => setRef("")}>Clear filter: {ref}</button>}
            </FilterBar>
            <DataTable rows={rows} onRowClick={(p) => router.push(`/admin/users/${p.user_id}`)} empty="No payments yet." columns={[
              { key: "email", label: "Teacher" }, { key: "amount", label: "Amount", render: (p) => `${p.currency} ${p.amount.toFixed(2)}` },
              { key: "status", label: "Status", render: (p) => <StatusPill value={p.status} /> }, { key: "provider", label: "Gateway" },
              { key: "provider_ref", label: "Reference", render: (p) => <Mono>{p.provider_ref}</Mono> },
              { key: "failure_reason", label: "Failure", render: (p) => <span className="text-xs text-danger-700">{p.failure_reason || ""}</span> },
              { key: "created_at", label: "When", render: (p) => <When at={p.created_at} /> }]} />
            <LoadMore list={payments} />
          </>
        ) : (
          <DataTable rows={subs?.items || []} rowKey="email" columns={[
            { key: "email", label: "Teacher" }, { key: "plan", label: "Plan" }, { key: "status", label: "Status", render: (s) => <StatusPill value={s.status} /> },
            { key: "provider", label: "Source" }, { key: "interval", label: "Billing" },
            { key: "period_end", label: "Period ends", render: (s) => s.period_end ? formatDate(s.period_end, { day: "numeric", month: "short", year: "numeric" }) : "—" }]} />
        )}
      </section>
    </AdminPage>
  );
}
