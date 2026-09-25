"use client";

import { Search } from "lucide-react";
import { useState } from "react";
import { UserDrawer } from "@/components/admin-user-drawer";
import { DashHeader } from "@/components/dash";
import { Badge } from "@/components/ui";
import { formatDate, timeAgo } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";

export default function AdminUsers() {
  const { user } = useMe();
  const [q, setQ] = useState("");
  const { data } = useApi<any>(user?.role === "admin" ? `/admin/users?limit=100${q ? `&q=${encodeURIComponent(q)}` : ""}` : null);
  const [selected, setSelected] = useState<string | null>(null);
  if (user && user.role !== "admin") return <p className="text-muted">Admins only.</p>;

  return (
    <div className="space-y-6">
      <DashHeader title="Users" subtitle="Teachers and admins. Open a user to grant a plan, add credits or suspend the account." />
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <div className="relative mb-4 max-w-sm">
          <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by email or name" aria-label="Search users"
            className="h-12 w-full rounded-full bg-surface-2 ps-12 pe-4 text-sm text-ink outline-none focus:ring-2 focus:ring-brand-200" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted">
              <tr><th className="px-3 py-3 text-start font-medium">User</th><th className="px-3 py-3 text-start font-medium">Plan</th><th className="px-3 py-3 text-start font-medium">Joined</th><th className="px-3 py-3 text-start font-medium">Last login</th><th className="px-3 py-3 text-start font-medium">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {(data?.items || []).map((u: any) => (
                <tr key={u.id} className="cursor-pointer hover:bg-surface-2" onClick={() => setSelected(u.id)}>
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 font-semibold text-white">{(u.name || u.email).slice(0, 1).toUpperCase()}</span>
                      <span className="min-w-0"><span className="block truncate font-medium text-ink">{u.name || "—"}</span><span className="block truncate text-xs text-muted">{u.email}</span></span>
                    </div>
                  </td>
                  <td className="px-3 py-3"><Badge tone={u.plan === "free" ? "neutral" : "brand"}>{u.plan}</Badge>{u.role === "admin" && <Badge className="ms-1" tone="accent">admin</Badge>}</td>
                  <td className="px-3 py-3 text-muted">{u.created_at ? formatDate(u.created_at) : "—"}</td>
                  <td className="px-3 py-3 text-muted">{u.last_login_at ? timeAgo(u.last_login_at) : "—"}</td>
                  <td className="px-3 py-3"><Badge tone={u.status === "active" ? "success" : "danger"}>{u.status}</Badge></td>
                </tr>
              ))}
              {data && !data.items.length && <tr><td colSpan={5} className="px-3 py-8 text-center text-muted">No users match.</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
      <UserDrawer id={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
