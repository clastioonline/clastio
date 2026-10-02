"use client";

import { Brain, Check, Plus, Trash } from "lucide-react";
import { useState } from "react";
import { LoadError } from "@/components/load-error";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Input, PageHeader, Select, Skeleton, Tabs, Textarea } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function fmt(v: any) {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.join(", ");
  return String(v);
}

export default function TeacherMemory() {
  const { notify } = useToast();
  const [kind, setKind] = useState<string>("all");
  const { data, error, mutate } = useApi<any>(`/memory${kind !== "all" ? `?kind=${kind}` : ""}`);
  const [newPref, setNewPref] = useState({ key: "language_level", value: "" });
  const [note, setNote] = useState("");

  const setPref = async (key: string, value: any) => {
    try {
      await api(`/memory/preferences/${key}`, { method: "PUT", body: { value } });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };
  const [savingNote, setSavingNote] = useState(false);
  const addNote = async () => {
    setSavingNote(true);
    try {
      await api("/memory/items", { body: { kind: "note", content: note } });
      setNote("");
      await mutate();
    } catch (e) { notify({ tone: "error", title: "Couldn't save note", body: errorMessage(e) }); }
    finally { setSavingNote(false); }
  };
  const updateMemory = async (path: string, method: "POST" | "DELETE") => {
    try { await api(path, { method }); await mutate(); }
    catch (e) { notify({ tone: "error", title: "Couldn't update memory", body: errorMessage(e) }); }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Teacher memory" subtitle="What the assistant knows about how you teach. Everything here is applied to new lessons, and you can edit or delete any of it." />
      {error && <LoadError retry={mutate} label="teacher memory" />}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <Card className="min-w-0">
          <CardHeader icon={<Brain className="h-5 w-5" />} title="Preferences" subtitle="Stated by you, or learned from your slides and edits (unconfirmed)" />
          <div className="divide-y divide-line">
            {!data ? <div className="p-5"><Skeleton className="h-40" /></div> : data.preferences.map((p: any) => (
              <div key={p.key} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink">{p.label}</div>
                  <div className="truncate text-sm text-muted">{fmt(p.value)}</div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {p.confirmed ? <Badge tone="success">You set this</Badge> : (
                    <>
                      <Badge tone="accent">Learned</Badge>
                      <Button size="icon" variant="ghost" aria-label="Confirm" onClick={() => updateMemory(`/memory/preferences/${p.key}/confirm`, "POST")}><Check className="h-4 w-4" /></Button>
                    </>
                  )}
                  <Button size="icon" variant="ghost" aria-label="Forget" onClick={() => updateMemory(`/memory/preferences/${p.key}`, "DELETE")}><Trash className="h-4 w-4" /></Button>
                </div>
              </div>
            ))}
          </div>
          <div className="space-y-3 border-t border-line p-5">
            <div className="text-sm font-medium text-ink">Add or change a preference</div>
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
              <Select value={newPref.key} onChange={(e) => setNewPref({ ...newPref, key: e.target.value })}>
                {Object.entries(data?.known_preferences || {}).map(([k, label]: any) => <option key={k} value={k}>{label}</option>)}
              </Select>
              <Input value={newPref.value} onChange={(e) => setNewPref({ ...newPref, value: e.target.value })} placeholder="e.g. simple English" />
              <Button disabled={!newPref.value} onClick={() => {
                const v = newPref.value.trim();
                const parsed = v === "yes" || v === "true" ? true : v === "no" || v === "false" ? false : /^\d+$/.test(v) ? Number(v) : v;
                setPref(newPref.key, parsed);
                setNewPref({ ...newPref, value: "" });
              }}><Plus className="h-4 w-4" /> Save</Button>
            </div>
          </div>
        </Card>
        <Card className="min-w-0">
          <CardHeader title="Memory timeline" subtitle="Lesson summaries, reflections, misconceptions and notes"
            action={<Tabs value={kind} onChange={setKind} tabs={[{ value: "all", label: "All" }, { value: "lesson_summary", label: "Lessons" }, { value: "misconception", label: "Misconceptions" }, { value: "note", label: "Notes" }]} />} />
          <div className="space-y-3 p-5">
            <div className="flex gap-2">
              <Textarea className="min-h-[44px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Tell the assistant something to remember, e.g. “8B responds well to competitive games”" />
              <Button onClick={addNote} loading={savingNote} disabled={note.trim().length < 3}>Add</Button>
            </div>
            {data?.items?.length ? data.items.map((m: any) => (
              <div key={m.id} className="group flex items-start justify-between gap-3 rounded-xl border border-line p-3">
                <div>
                  <div className="flex items-center gap-2 text-xs text-muted"><Badge>{m.kind.replace("_", " ")}</Badge>{formatDate(m.created_at)}</div>
                  <div className="mt-1 break-words text-sm text-ink-2">{m.content}</div>
                </div>
                <Button size="icon" variant="ghost" className="shrink-0" aria-label="Delete" onClick={() => updateMemory(`/memory/items/${m.id}`, "DELETE")}><Trash className="h-4 w-4" /></Button>
              </div>
            )) : data && <EmptyState title="Nothing here yet" description="Lesson summaries and reflections appear automatically as you teach." />}
          </div>
        </Card>
      </div>
    </div>
  );
}
