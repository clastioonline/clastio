"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AdminPage, DataTable, ExportButton, FilterBar, LoadMore, StatusPill, When, useCursorList } from "@/components/admin-kit";
import { Badge, Field, Select } from "@/components/ui";
import { formatDate } from "@/lib/api";

export default function AdminUsers() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [f, setF] = useState({ status: "", plan: "", kind: "teacher", sort: "newest", verified: "" });
  useEffect(() => { const v = new URLSearchParams(window.location.search).get("q") || ""; setQ(v); setTerm(v); }, []);
  useEffect(() => { const t = setTimeout(() => setTerm(q), 300); return () => clearTimeout(t); }, [q]);
  const params = new URLSearchParams({ limit: "50", sort: f.sort });
  if (term) params.set("q", term);
  for (const k of ["status", "plan", "kind", "verified"] as const) if (f[k]) params.set(k, f[k]);
  const list = useCursorList<any>(`/admin/users?${params}`);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  return (
    <AdminPage title="Teachers" perm="users.view" subtitle="Everyone who signed up. Open an account for usage, billing, sessions, activity and actions."
      actions={<ExportButton dataset="users" days={3650} />}>
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <FilterBar>
          <div className="relative min-w-60 flex-1">
            <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Email, name or user id" aria-label="Search accounts"
              className="h-10 w-full rounded-full bg-surface-2 ps-12 pe-4 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-200" />
          </div>
          <Field label="Status"><Select value={f.status} onChange={set("status")}>
            <option value="">Any</option>{["active", "email_unverified", "suspended", "banned", "pending_deletion", "deleted"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
          </Select></Field>
          <Field label="Plan"><Select value={f.plan} onChange={set("plan")}>
            <option value="">Any</option>{["free", "trial", "teacher", "pro", "assistant"].map((s) => <option key={s}>{s}</option>)}
          </Select></Field>
          <Field label="Accounts"><Select value={f.kind} onChange={set("kind")}><option value="teacher">Teachers</option><option value="staff">Staff</option><option value="">Everyone</option></Select></Field>
          <Field label="Sort"><Select value={f.sort} onChange={set("sort")}><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="last_active">Last active</option><option value="email">Email</option></Select></Field>
        </FilterBar>
        <p className="mb-2 text-xs text-muted">{list.extra?.total ?? "…"} matching accounts</p>
        <DataTable rows={list.items} onRowClick={(u) => router.push(`/admin/users/${u.id}`)} empty="No accounts match these filters."
          columns={[
            { key: "user", label: "Account", render: (u) => (
              <div className="flex items-center gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-sm font-semibold text-white">{(u.name || u.email).slice(0, 1).toUpperCase()}</span>
                <span className="min-w-0"><span className="block truncate font-medium text-ink">{u.name || "—"}</span><span className="block truncate text-xs text-muted">{u.email}</span></span>
              </div>) },
            { key: "plan", label: "Plan", render: (u) => u.admin_role ? <Badge tone="accent">{u.admin_role.replace("_", " ")}</Badge> : (
              <span className="flex flex-wrap gap-1">
                <Badge tone={u.plan === "free" ? "neutral" : "brand"}>{u.plan}</Badge>
                {u.plan_source === "trial" && <Badge tone="accent">trial</Badge>}
                {["stripe", "dodo"].includes(u.plan_source) && <Badge tone="success">paying</Badge>}
                {u.plan_source === "manual" && <Badge>granted</Badge>}
                {u.plan_status === "past_due" && <Badge tone="warn">past due</Badge>}
              </span>) },
            { key: "created_at", label: "Joined", render: (u) => <span className="text-muted">{formatDate(u.created_at)}</span> },
            { key: "last_active_at", label: "Last active", render: (u) => <When at={u.last_active_at || u.last_login_at} /> },
            { key: "status", label: "Status", render: (u) => <span className="flex flex-wrap gap-1"><StatusPill value={u.status} />{!u.email_verified && <Badge>unverified</Badge>}</span> },
          ]} />
        <LoadMore list={list} />
      </section>
    </AdminPage>
  );
}
