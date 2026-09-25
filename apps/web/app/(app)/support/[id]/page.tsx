"use client";

import { ArrowLeft } from "lucide-react";
import { use, useState } from "react";
import { StatusPill } from "@/components/admin-kit";
import { DashHeader } from "@/components/dash";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Skeleton, Textarea } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export default function TicketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { notify } = useToast();
  const { data, error, mutate } = useApi<any>(`/support/tickets/${id}`);
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  if (error) return <Alert tone="danger">This request doesn't exist or isn't yours.</Alert>;
  if (!data) return <Skeleton className="h-64" />;
  const send = async () => {
    setBusy(true);
    try {
      await api(`/support/tickets/${id}/messages`, { body: { body: reply }, idempotent: true });
      setReply("");
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't send", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="space-y-6">
      <Button variant="ghost" href="/support"><ArrowLeft className="h-4 w-4" /> All requests</Button>
      <DashHeader title={data.subject} subtitle={<span className="flex items-center gap-2">Request #{data.number} <StatusPill value={data.status} /></span>} />
      <section className="space-y-3 rounded-3xl bg-surface p-5 sm:p-6">
        {data.messages.map((m: any) => (
          <div key={m.id} className={cn("max-w-[85%] rounded-2xl px-4 py-3 text-sm", m.from_staff ? "bg-brand-50 text-ink" : "ms-auto bg-surface-2 text-ink")}>
            <div className="mb-1 text-xs font-medium text-muted">{m.author} · {timeAgo(m.created_at)}</div>
            <div className="whitespace-pre-wrap">{m.body}</div>
          </div>
        ))}
        {data.status === "closed" ? <Alert tone="neutral">This request is closed. Open a new one if you still need help.</Alert> : (
          <div className="space-y-2 pt-2">
            <Textarea rows={4} value={reply} onChange={(e) => setReply(e.target.value)} placeholder="Write a reply…" aria-label="Reply" />
            <div className="flex justify-end"><Button loading={busy} disabled={!reply.trim()} onClick={send}>Send reply</Button></div>
          </div>
        )}
      </section>
    </div>
  );
}
