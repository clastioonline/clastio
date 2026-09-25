"use client";

import { useRouter } from "next/navigation";
import { AdminPage, DataTable, StatusPill, When } from "@/components/admin-kit";
import { Badge } from "@/components/ui";
import { useApi } from "@/lib/hooks";

export default function StaffPage() {
  const router = useRouter();
  const { data: staff } = useApi<any>("/admin/staff");
  const { data: roles } = useApi<any>("/admin/roles");
  return (
    <AdminPage title="Staff & roles" perm="users.view" subtitle="Who runs PPT Genie and what each role may do. Super admins change roles from an account's page.">
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <DataTable rows={staff?.items || []} onRowClick={(u) => router.push(`/admin/users/${u.id}`)} columns={[
          { key: "email", label: "Staff member", render: (u) => <><span className="block font-medium text-ink">{u.name || "—"}</span><span className="text-xs text-muted">{u.email}</span></> },
          { key: "admin_role", label: "Role", render: (u) => <Badge tone="accent">{u.admin_role_label}</Badge> },
          { key: "status", label: "Status", render: (u) => <StatusPill value={u.status} /> },
          { key: "last_active_at", label: "Last active", render: (u) => <When at={u.last_active_at} /> }]} />
      </section>
      {roles && (
        <section className="overflow-x-auto rounded-3xl bg-surface p-5 sm:p-6">
          <h2 className="mb-3 font-semibold text-ink">Permission matrix</h2>
          <table className="w-full text-sm">
            <thead><tr><th className="py-2 text-start font-medium text-muted">Permission</th>{roles.roles.map((r: any) => <th key={r.code} className="px-2 py-2 font-medium text-muted">{r.label}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {Object.entries(roles.permissions).map(([p, label]: any) => (
                <tr key={p}><td className="py-2 pe-3"><span className="text-ink">{label}</span><span className="block text-xs text-muted">{p}</span></td>
                  {roles.roles.map((r: any) => <td key={r.code} className="text-center">{r.permissions.includes(p) ? <span aria-label="allowed" className="text-success-700">●</span> : <span aria-label="not allowed" className="text-line-strong">○</span>}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </AdminPage>
  );
}
