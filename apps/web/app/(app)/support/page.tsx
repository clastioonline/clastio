"use client";

import { LifeBuoy, Lightbulb, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { StatusPill, When } from "@/components/admin-kit";
import { DashHeader } from "@/components/dash";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Chips, EmptyState, Field, Input, Modal, Select, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const KINDS = [
  { value: "support", label: "Question or problem" },
  { value: "bug", label: "Something is broken" },
  { value: "billing", label: "Billing" },
  { value: "feature_request", label: "Feature request" },
];

export default function SupportPage() {
  const { notify } = useToast();
  const [filter, setFilter] = useState("all");
  const { data, mutate } = useApi<{ items: any[] }>(`/support/tickets${filter === "feature_request" ? "?kind=feature_request" : ""}`);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ kind: "support", subject: "", body: "" });
  const [busy, setBusy] = useState(false);
  const items = (data?.items || []).filter((t) => filter !== "support" || t.kind !== "feature_request");

  const submit = async () => {
    setBusy(true);
    try {
      await api("/support/tickets", { body: form, idempotent: true });
      notify({ tone: "success", title: form.kind === "feature_request" ? "Thanks for the idea!" : "Request sent", body: "We'll reply here and by email." });
      setOpen(false);
      setForm({ kind: "support", subject: "", body: "" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't send", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const start = (kind: string) => { setForm({ ...form, kind }); setOpen(true); };

  return (
    <div className="space-y-6">
      <DashHeader title="Help & support" subtitle="Ask a question, report a problem or suggest a feature. We reply here and by email."
        actions={<>
          <Button variant="outline" onClick={() => start("feature_request")}><Lightbulb className="h-4 w-4" /> Suggest a feature</Button>
          <Button onClick={() => start("support")}><Plus className="h-4 w-4" /> New request</Button>
        </>} />
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <div className="mb-4"><Chips options={[{ value: "all", label: "All" }, { value: "support", label: "Support" }, { value: "feature_request", label: "Feature requests" }]} value={filter} onChange={setFilter} /></div>
        {!items.length ? (
          <EmptyState icon={<LifeBuoy className="h-6 w-6" />} title="No requests yet" description="Stuck on something? Check the tutorials, or send us a request." action={<Button href="/tutorials" variant="outline">Open tutorials</Button>} />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((t) => (
              <li key={t.id}>
                <Link href={`/support/${t.id}`} className="flex flex-wrap items-center gap-3 py-3 hover:opacity-80">
                  <span className="w-16 shrink-0 text-sm text-muted">#{t.number}</span>
                  <span className="min-w-0 flex-1"><span className="block truncate font-medium text-ink">{t.subject}</span><span className="text-xs text-muted">{KINDS.find((k) => k.value === t.kind)?.label}</span></span>
                  <StatusPill value={t.status} />
                  <When at={t.updated_at} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      <Modal open={open} onClose={() => setOpen(false)} title={form.kind === "feature_request" ? "Suggest a feature" : "New support request"}
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button loading={busy} disabled={form.subject.trim().length < 3 || form.body.trim().length < 5} onClick={submit}>Send</Button></>}>
        <div className="space-y-4">
          <Field label="Type"><Select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}</Select></Field>
          <Field label="Subject"><Input value={form.subject} maxLength={200} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder={form.kind === "feature_request" ? "e.g. Arabic voice-over for slides" : "e.g. Lesson 3 downloads blank slides"} /></Field>
          <Field label="Details" hint="Please don't include students' personal information.">
            <Textarea rows={6} maxLength={10000} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          </Field>
        </div>
      </Modal>
    </div>
  );
}
