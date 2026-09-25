"use client";

import { useState } from "react";
import { AdminPage, DataTable, ReasonDialog, StatusPill, When } from "@/components/admin-kit";
import { Markdown } from "@/components/markdown";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Field, Input, Modal, Select, Tabs, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const EMPTY = { id: null as string | null, document_type: "terms", version: "", title: "", content: "", summary_of_changes: "", requires_acceptance: true };

export default function LegalAdmin() {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/admin/legal");
  const [edit, setEdit] = useState<typeof EMPTY | null>(null);
  const [view, setView] = useState<"write" | "preview">("write");
  const [publishing, setPublishing] = useState<any>(null);
  const open = async (d?: any) => {
    if (!d) return setEdit({ ...EMPTY });
    const full = await api<any>(`/admin/legal/${d.id}`);
    setEdit(d.status === "draft" ? { id: d.id, document_type: d.type, version: d.version, title: d.title, content: full.content, summary_of_changes: d.summary_of_changes || "", requires_acceptance: d.requires_acceptance }
      : { ...EMPTY, document_type: d.type, title: d.title, content: full.content, version: "" });
  };
  const save = async () => {
    if (!edit) return;
    const { id, ...body } = edit;
    try {
      await api(id ? `/admin/legal/${id}` : "/admin/legal", { method: id ? "PUT" : "POST", body });
      notify({ tone: "success", title: "Draft saved" }); setEdit(null); mutate();
    } catch (e) { notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) }); }
  };
  return (
    <AdminPage title="Legal documents" perm="legal.manage" subtitle="Versioned Terms, Privacy, Acceptable Use, Cookie and Refund policies. Published versions are immutable; publishing one that needs acceptance asks every teacher to accept it."
      actions={<Button onClick={() => open()}>New draft</Button>}>
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <DataTable rows={data?.items || []} onRowClick={open} columns={[
          { key: "title", label: "Document", render: (d) => <><span className="block font-medium text-ink">{d.title}</span><span className="text-xs text-muted">{d.type}</span></> },
          { key: "version", label: "Version" }, { key: "status", label: "Status", render: (d) => <StatusPill value={d.status} /> },
          { key: "requires_acceptance", label: "Needs acceptance", render: (d) => (d.requires_acceptance ? "Yes" : "No") },
          { key: "accepted_by", label: "Accepted by" },
          { key: "published_at", label: "Published", render: (d) => <When at={d.published_at} /> },
          { key: "x", label: "", render: (d) => d.status === "draft" && <Button size="sm" onClick={(e) => { e.stopPropagation(); setPublishing(d); }}>Publish…</Button> }]} />
      </section>
      <Modal open={!!edit} onClose={() => setEdit(null)} size="xl" title={edit?.id ? "Edit draft" : "New version (draft)"}
        footer={<><Button variant="ghost" onClick={() => setEdit(null)}>Cancel</Button><Button onClick={save} disabled={!edit?.version || !edit?.title || (edit?.content.length || 0) < 20}>Save draft</Button></>}>
        {edit && (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Document"><Select value={edit.document_type} disabled={!!edit.id} onChange={(e) => setEdit({ ...edit, document_type: e.target.value })}>
                {Object.entries(data?.types || {}).map(([k, v]: any) => <option key={k} value={k}>{v}</option>)}</Select></Field>
              <Field label="Version" hint="New number, e.g. 1.1"><Input value={edit.version} onChange={(e) => setEdit({ ...edit, version: e.target.value })} /></Field>
              <Field label="Title"><Input value={edit.title} onChange={(e) => setEdit({ ...edit, title: e.target.value })} /></Field>
            </div>
            <Field label="Summary of changes (shown to teachers)"><Input value={edit.summary_of_changes} onChange={(e) => setEdit({ ...edit, summary_of_changes: e.target.value })} /></Field>
            <Toggle checked={edit.requires_acceptance} onChange={(v) => setEdit({ ...edit, requires_acceptance: v })} label="Teachers must accept this version" description="They'll see an 'updated terms' prompt when they next use the app." />
            <Tabs value={view} onChange={setView} tabs={[{ value: "write", label: "Write" }, { value: "preview", label: "Preview" }]} />
            {view === "write" ? <Textarea rows={16} className="font-mono text-xs" value={edit.content} onChange={(e) => setEdit({ ...edit, content: e.target.value })} />
              : <div className="max-h-96 overflow-auto rounded-xl bg-surface-2 p-4"><Markdown text={edit.content} /></div>}
          </div>
        )}
      </Modal>
      <ReasonDialog open={!!publishing} onClose={() => setPublishing(null)} requireReason={false} confirmLabel="Publish" title={`Publish ${publishing?.title} v${publishing?.version}?`}
        description={publishing?.requires_acceptance ? "Every teacher will be asked to accept this version and notified. It can't be edited after publishing." : "It becomes the current version and can't be edited after publishing."}
        onConfirm={async () => { await api(`/admin/legal/${publishing.id}/publish`, { method: "POST" }); notify({ tone: "success", title: "Published" }); mutate(); }} />
    </AdminPage>
  );
}
