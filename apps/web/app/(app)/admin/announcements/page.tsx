"use client";

import { useState } from "react";
import { AdminPage, DataTable, StatusPill, When } from "@/components/admin-kit";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Field, Input, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const EMPTY = { kind: "product", title: "", body: "", link: "", audience: "teachers", ends_at: "", notify_users: false };

export default function Announcements() {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/admin/announcements");
  const [f, setF] = useState<any>(EMPTY);
  const [busy, setBusy] = useState(false);
  const create = async () => {
    setBusy(true);
    try {
      await api("/admin/announcements", { body: { ...f, link: f.link || null, ends_at: f.ends_at ? new Date(f.ends_at).toISOString() : null }, idempotent: true });
      notify({ tone: "success", title: "Announcement published" });
      setF(EMPTY);
      mutate();
    } catch (e) { notify({ tone: "error", title: "Couldn't publish", body: errorMessage(e) }); } finally { setBusy(false); }
  };
  const toggle = async (a: any) => {
    await api(`/admin/announcements/${a.id}`, { method: "PUT", body: { kind: a.kind, title: a.title, body: a.body, link: a.link, audience: a.audience, ends_at: a.ends_at, active: !a.active } });
    mutate();
  };
  return (
    <AdminPage title="Announcements" perm="announcements.manage" subtitle="Banners at the top of the app for maintenance, new features and important notices. Optionally also sent as a notification.">
      <section className="grid gap-4 rounded-3xl bg-surface p-5 sm:p-6 md:grid-cols-2">
        <Field label="Title"><Input value={f.title} maxLength={200} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Kind"><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{["product", "feature", "maintenance", "important"].map((k) => <option key={k}>{k}</option>)}</Select></Field>
          <Field label="Audience"><Select value={f.audience} onChange={(e) => setF({ ...f, audience: e.target.value })}><option value="teachers">Teachers</option><option value="everyone">Everyone</option><option value="staff">Staff</option></Select></Field>
        </div>
        <Field label="Message" className="md:col-span-2"><Textarea value={f.body} maxLength={2000} onChange={(e) => setF({ ...f, body: e.target.value })} /></Field>
        <Field label="Link (optional)" hint="An app path like /media or an https:// URL"><Input value={f.link} onChange={(e) => setF({ ...f, link: e.target.value })} /></Field>
        <Field label="Ends (optional)"><Input type="datetime-local" value={f.ends_at} onChange={(e) => setF({ ...f, ends_at: e.target.value })} /></Field>
        <Toggle checked={f.notify_users} onChange={(v) => setF({ ...f, notify_users: v })} label="Also send as a notification" description="Appears in each person's bell (respects their preferences)." />
        <div className="flex items-end justify-end"><Button loading={busy} disabled={f.title.trim().length < 3} onClick={create}>Publish</Button></div>
      </section>
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <DataTable rows={data?.items || []} columns={[
          { key: "title", label: "Announcement", render: (a) => <><span className="block font-medium text-ink">{a.title}</span><span className="text-xs text-muted">{a.body}</span></> },
          { key: "kind", label: "Kind" }, { key: "audience", label: "Audience" },
          { key: "active", label: "State", render: (a) => <StatusPill value={a.active ? "active" : "archived"} /> },
          { key: "created_at", label: "Created", render: (a) => <When at={a.created_at} /> },
          { key: "x", label: "", render: (a) => <Button size="sm" variant="ghost" onClick={() => toggle(a)}>{a.active ? "Hide" : "Show"}</Button> }]} />
      </section>
    </AdminPage>
  );
}
