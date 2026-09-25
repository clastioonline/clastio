"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { AdminPage, Mono, StatusPill, When } from "@/components/admin-kit";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Field, Select, Skeleton, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export default function TicketAdmin({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user } = useMe();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(`/admin/support/tickets/${id}`);
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(false);
  const [status, setStatus] = useState("pending");
  const [busy, setBusy] = useState(false);
  if (!data) return <Skeleton className="h-96" />;
  const send = async () => {
    setBusy(true);
    try {
      await api(`/admin/support/tickets/${id}/messages`, { body: { body, internal, status: internal ? undefined : status }, idempotent: true });
      setBody("");
      notify({ tone: "success", title: internal ? "Note added" : "Reply sent", body: internal ? undefined : "The teacher was notified by email and in the app." });
      mutate();
    } catch (e) { notify({ tone: "error", title: errorMessage(e) }); } finally { setBusy(false); }
  };
  const patch = async (b: any) => { await api(`/admin/support/tickets/${id}`, { method: "PATCH", body: b }); mutate(); };
  return (
    <AdminPage title={`#${data.number} ${data.subject}`} perm="support.manage"
      subtitle={<span className="flex flex-wrap items-center gap-2"><Link href={`/admin/users/${data.user_id}`} className="text-brand-600 hover:underline">{data.email}</Link> · {data.kind.replace("_", " ")} <StatusPill value={data.status} /></span>}
      actions={<Button variant="ghost" href="/admin/support"><ArrowLeft className="h-4 w-4" /> All tickets</Button>}>
      <div className="grid gap-6 lg:grid-cols-3">
        <section className="space-y-3 rounded-3xl bg-surface p-5 lg:col-span-2">
          {data.messages.map((m: any) => (
            <div key={m.id} className={cn("rounded-2xl px-4 py-3 text-sm", m.internal ? "border border-dashed border-warn-500 bg-warn-50" : m.from_staff ? "bg-brand-50" : "bg-surface-2")}>
              <div className="mb-1 text-xs text-muted">{m.author}{m.internal && " · internal note"} · <When at={m.created_at} /></div>
              <div className="whitespace-pre-wrap text-ink">{m.body}</div>
            </div>
          ))}
          <div className="space-y-3 border-t border-line pt-4">
            <Textarea rows={5} value={body} onChange={(e) => setBody(e.target.value)} placeholder={internal ? "Internal note (staff only)" : "Reply to the teacher"} aria-label="Message" />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="w-64"><Toggle checked={internal} onChange={setInternal} label="Internal note" /></div>
              <div className="flex items-end gap-2">
                {!internal && <Field label="Then set status"><Select value={status} onChange={(e) => setStatus(e.target.value)}>{["pending", "open", "resolved", "closed", "planned", "declined"].map((s) => <option key={s}>{s}</option>)}</Select></Field>}
                <Button loading={busy} disabled={!body.trim()} onClick={send}>{internal ? "Add note" : "Send reply"}</Button>
              </div>
            </div>
          </div>
        </section>
        <section className="space-y-3 rounded-3xl bg-surface p-5 text-sm">
          <Field label="Status"><Select value={data.status} onChange={(e) => patch({ status: e.target.value })}>{["open", "pending", "resolved", "closed", "planned", "declined"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Field label="Priority"><Select value={data.priority} onChange={(e) => patch({ priority: e.target.value })}>{["low", "normal", "high", "urgent"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <Button variant="outline" size="sm" onClick={() => patch(data.assigned_to === user?.id ? { unassign: true } : { assigned_to: user?.id })}>
            {data.assigned_to === user?.id ? "Unassign me" : "Assign to me"}
          </Button>
          {data.request_id && <p className="text-xs text-muted">Opened in request <Link className="underline" href={`/admin/system?trace=${data.request_id}`}><Mono>{data.request_id}</Mono></Link></p>}
        </section>
      </div>
    </AdminPage>
  );
}
