"use client";

import { ArrowRight, LifeBuoy, ScrollText, ServerCog, ShieldCheck, Wallet } from "lucide-react";
import Link from "next/link";
import { DataTable, When } from "@/components/admin-kit";
import { LoadError } from "@/components/load-error";
import { Button, PageHeader, Skeleton } from "@/components/ui";
import { useApi, useMe } from "@/lib/hooks";

type AuditEntry = { id: string; action: string; target_email?: string | null; target_type?: string | null; reason?: string | null; created_at: string };
const sections = [
  { permission: "audit.view", href: "/admin/audit", title: "Audit log", description: "Review staff actions and recorded changes.", icon: ScrollText },
  { permission: "system.logs.view", href: "/admin/system", title: "Health & logs", description: "Monitor background jobs, email delivery and webhooks.", icon: ServerCog },
  { permission: "security.view", href: "/admin/security", title: "Security events", description: "Review sign-in and account security events.", icon: ShieldCheck },
  { permission: "billing.view", href: "/admin/billing", title: "Subscriptions & payments", description: "Review teacher subscriptions and payment records.", icon: Wallet },
  { permission: "support.manage", href: "/admin/support", title: "Tickets & requests", description: "Follow teacher support requests.", icon: LifeBuoy },
];

export function AdminActivity() {
  const { user } = useMe();
  const staff = user?.role === "admin";
  const canAudit = staff && user.permissions.includes("audit.view");
  const { data, error, isLoading, mutate } = useApi<{ items: AuditEntry[] }>(canAudit ? `/admin/audit-logs?actor_id=${encodeURIComponent(user.id)}&limit=20&days=90` : null, { refreshInterval: 30_000 });
  const available = staff ? sections.filter(section => user.permissions.includes(section.permission)) : [];
  if (!staff) return null;
  return <div className="mx-auto max-w-5xl space-y-6">
    <PageHeader title="Admin activity" subtitle="Follow your staff actions and platform operations."
      actions={canAudit ? <Button variant="outline" onClick={() => { void mutate(); }}>Refresh</Button> : undefined} />
    <div className="grid gap-4 sm:grid-cols-2">
      {available.map(({ href, title, description, icon: Icon }) => <Link key={href} href={href} className="focus-ring rounded-2xl border border-line bg-surface p-5 transition hover:border-brand-300">
        <Icon className="h-6 w-6 text-brand-700" />
        <div className="mt-3 flex items-center justify-between gap-3"><h2 className="font-semibold text-ink">{title}</h2><ArrowRight className="h-4 w-4 shrink-0 text-brand-700" /></div>
        <p className="mt-2 text-sm text-muted">{description}</p>
      </Link>)}
    </div>
    {canAudit ? <section className="rounded-2xl border border-line bg-surface p-5">
      <h2 className="font-semibold text-ink">Your recent staff actions</h2>
      <p className="mt-1 mb-4 text-sm text-muted">Your latest 20 recorded actions from the last 90 days.</p>
      {error ? <LoadError label="your staff activity" retry={mutate} /> : isLoading ? <Skeleton className="h-48" /> : <DataTable rows={data?.items || []} empty="No staff actions recorded for you yet." columns={[
        { key: "action", label: "Action", render: entry => <span className="break-words font-medium text-ink">{entry.action.replace(/[._]/g, " ")}</span> },
        { key: "target", label: "Target", render: entry => <span className="break-words">{entry.target_email || entry.target_type || "—"}</span> },
        { key: "reason", label: "Reason", render: entry => <span className="text-muted">{entry.reason || "—"}</span> },
        { key: "created_at", label: "When", render: entry => <When at={entry.created_at} /> },
      ]} />}
    </section> : <p className="rounded-2xl border border-line bg-surface p-5 text-sm text-muted">The audit log is available to staff with audit access. Use the sections available to your role to follow platform activity.</p>}
    {!available.length && <Button href="/settings" variant="outline">Account settings</Button>}
  </div>;
}
