"use client";

import { GraduationCap, Pencil, Plus, Trash } from "lucide-react";
import { useEffect, useState } from "react";
import { ClassChip } from "@/components/common";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, EmptyState, Field, Input, Modal, PageHeader, Progress, Select, Skeleton, Textarea } from "@/components/ui";
import { UploadDropzone } from "@/components/upload";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { CURRICULA, GRADES, SUBJECTS, cn } from "@/lib/utils";

const COLORS = ["#4f46e5", "#0f766e", "#2563eb", "#9333ea", "#db2777", "#ea580c", "#16a34a", "#0891b2"];
const EMPTY = { name: "", grade: "8", subject: "Science", curriculum: "", pace: "standard", ability_mix: "mixed", eal_percent: 0, send_notes: "", notes: "", color: COLORS[0] };

function ClassDialog({ open, onClose, initial, onSaved }: { open: boolean; onClose: () => void; initial?: any; onSaved: () => void }) {
  const { notify } = useToast();
  const [f, setF] = useState<any>(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => setF(initial ? { ...EMPTY, ...initial, curriculum: initial.curriculum || "" } : EMPTY), [initial, open]);
  const save = async () => {
    setBusy(true);
    try {
      const body = { ...f, curriculum: f.curriculum || null, send_notes: f.send_notes || null, notes: f.notes || null };
      if (initial?.id) await api(`/classes/${initial.id}`, { method: "PUT", body });
      else await api("/classes", { body });
      onSaved();
      onClose();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title={initial?.id ? `Edit ${initial.name}` : "Add a class"}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={save} loading={busy} disabled={!f.name}>Save</Button></>}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Class name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="8A" /></Field>
        <Field label="Colour">
          <div className="flex gap-1.5 pt-1">{COLORS.map((c) => <button key={c} type="button" onClick={() => setF({ ...f, color: c })} className={cn("h-7 w-7 rounded-full ring-offset-2", f.color === c && "ring-2 ring-ink")} style={{ background: c }} aria-label={c} />)}</div>
        </Field>
        <Field label="Grade"><Select value={f.grade} onChange={(e) => setF({ ...f, grade: e.target.value })}>{GRADES.map((g) => <option key={g}>{g}</option>)}</Select></Field>
        <Field label="Subject"><Select value={f.subject} onChange={(e) => setF({ ...f, subject: e.target.value })}>{SUBJECTS.map((s) => <option key={s}>{s}</option>)}</Select></Field>
        <Field label="Curriculum (if different)"><Select value={f.curriculum} onChange={(e) => setF({ ...f, curriculum: e.target.value })}><option value="">Same as my profile</option>{CURRICULA.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}</Select></Field>
        <Field label="Pace"><Select value={f.pace} onChange={(e) => setF({ ...f, pace: e.target.value })}><option value="slower">Slower</option><option value="standard">Standard</option><option value="faster">Faster</option></Select></Field>
        <Field label="Ability mix"><Select value={f.ability_mix} onChange={(e) => setF({ ...f, ability_mix: e.target.value })}><option value="mixed">Mixed</option><option value="mostly support">Mostly needs support</option><option value="mostly core">Mostly core</option><option value="high attaining">High attaining</option></Select></Field>
        <Field label="EAL learners (approx. %)"><Input type="number" min={0} max={100} value={f.eal_percent} onChange={(e) => setF({ ...f, eal_percent: Number(e.target.value) })} /></Field>
        <Field label="Support needs (whole class, no names)" className="sm:col-span-2" hint="e.g. 3 students need visual supports and extra time"><Textarea className="min-h-[60px]" value={f.send_notes} onChange={(e) => setF({ ...f, send_notes: e.target.value })} /></Field>
        <Field label="Notes" className="sm:col-span-2" hint="e.g. loves hands-on experiments; chatty after lunch"><Textarea className="min-h-[60px]" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
    </Modal>
  );
}

function Coverage({ classId }: { classId: string }) {
  const { data } = useApi<any>(`/curriculum/coverage?class_id=${classId}`);
  if (!data) return <Skeleton className="h-24" />;
  const { summary } = data;
  if (!summary.total) return <p className="text-sm text-muted">No outcomes loaded for this grade/subject yet. Add your scheme of work as custom outcomes.</p>;
  const tone: Record<string, any> = { taught: "success", in_progress: "brand", planned: "accent", not_covered: "neutral" };
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <Progress value={(summary.taught / summary.total) * 100} tone="success" />
        <span className="shrink-0 text-xs text-muted tabular-nums">{summary.taught}/{summary.total} taught</span>
      </div>
      <ul className="space-y-1.5">
        {data.items.map((o: any) => (
          <li key={o.code} className="flex items-start justify-between gap-3 text-sm">
            <span className="text-ink-2"><span className="font-medium text-ink">{o.strand}</span> — {o.text}</span>
            <Badge tone={tone[o.status]} className="shrink-0 whitespace-nowrap">{o.status.replace("_", " ")}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Curriculum() {
  const { data, mutate } = useApi<any>("/classes");
  const [editing, setEditing] = useState<any>(null);
  const [open, setOpen] = useState(false);
  return (
    <div className="space-y-6">
      <PageHeader title="Classes" subtitle="Each class keeps its own progress, pace and history. Coverage shows which outcomes you've taught."
        actions={<Button onClick={() => { setEditing(null); setOpen(true); }}><Plus className="h-4 w-4" /> Add class</Button>} />
      {!data ? <Skeleton className="h-64" /> : data.items.length ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {data.items.map((c: any) => (
            <Card key={c.id}>
              <CardHeader title={<span className="flex items-center gap-2"><ClassChip name={c.name} color={c.color} /> Grade {c.grade} {c.subject}</span>}
                subtitle={[`${c.pace} pace`, c.ability_mix !== "mixed" ? c.ability_mix : "mixed ability", c.eal_percent ? `~${c.eal_percent}% EAL` : null].filter(Boolean).join(" · ")}
                action={
                  <div className="flex gap-1">
                    <Button variant="ghost" size="icon" onClick={() => { setEditing(c); setOpen(true); }} aria-label="Edit"><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={async () => { if (confirm(`Delete ${c.name}?`)) { await api(`/classes/${c.id}`, { method: "DELETE" }); mutate(); } }} aria-label="Delete"><Trash className="h-4 w-4" /></Button>
                  </div>
                } />
              <div className="p-5">
                {c.notes && <p className="mb-3 text-sm text-muted">{c.notes}</p>}
                <Coverage classId={c.id} />
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <EmptyState icon={<GraduationCap className="h-6 w-6" />} title="No classes yet" description="Add each section you teach (e.g. 8A, 8B) so lessons and progress are tracked per class."
          action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> Add class</Button>} />
      )}
      <Card>
        <CardHeader title="Reference material" subtitle="Upload textbook chapters or your scheme of work. Lessons will prefer these facts and cite pages in the notes." />
        <div className="p-5"><UploadDropzone kind="source" compact /></div>
      </Card>
      <ClassDialog open={open} onClose={() => setOpen(false)} initial={editing} onSaved={mutate} />
    </div>
  );
}
