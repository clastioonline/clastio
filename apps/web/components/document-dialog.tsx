"use client";

import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { JobLine } from "@/components/common";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Chips, Field, Input, Modal, Select, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";

const KINDS = [
  { value: "worksheet", label: "Worksheet" },
  { value: "quiz", label: "Quiz" },
  { value: "assessment", label: "Test" },
  { value: "homework", label: "Homework" },
];

export const FILE_LABELS: Record<string, string> = {
  pdf: "Student PDF", docx: "Student Word", key_pdf: "Answer key PDF", key_docx: "Answer key Word",
  csv: "Kahoot / Quizizz CSV", gift: "Moodle GIFT",
};

export function DocumentFiles({ files }: { files: Record<string, string> }) {
  return (
    <div className="flex flex-wrap gap-2">
      {Object.entries(files).map(([k, url]) => (
        <a key={k} href={url} className="inline-flex items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-surface-2">
          <Download className="h-4 w-4 text-brand-600" /> {FILE_LABELS[k] || k}
        </a>
      ))}
    </div>
  );
}

export function DocumentDialog({ open, onClose, kind: initialKind = "worksheet", lessonId }: { open: boolean; onClose: () => void; kind?: string; lessonId?: string }) {
  const { notify } = useToast();
  const { data: creditInfo } = useApi<any>(open ? "/usage/estimates" : null);
  const { data: lessons } = useApi<any>(open && !lessonId ? "/lessons?limit=60" : null);
  const [kind, setKind] = useState(initialKind);
  const [source, setSource] = useState<"lesson" | "month" | "topic">("lesson");
  const [lesson, setLesson] = useState<string>(lessonId || "");
  const [topic, setTopic] = useState("");
  const [difficulty, setDifficulty] = useState("mixed");
  const [num, setNum] = useState(10);
  const [caseStudy, setCaseStudy] = useState(false);
  const [instructions, setInstructions] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [doc, setDoc] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setKind(initialKind);
      setJobId(null);
      setDoc(null);
      setDocId(null);
      setLesson(lessonId || "");
    }
  }, [open, initialKind, lessonId]);
  useEffect(() => {
    if (!lesson && lessons?.items?.length) {
      const withPlan = lessons.items.find((l: any) => l.has_pptx);
      if (withPlan) setLesson(withPlan.id);
    }
  }, [lessons, lesson]);

  const job = useJob(jobId, async (j) => {
    if (j.status === "succeeded" && docId) setDoc(await api(`/documents/${docId}`));
    if (j.status === "failed") notify({ tone: "error", title: "Generation failed", body: j.error || undefined });
  });

  const create = async () => {
    setBusy(true);
    try {
      const body: any = { kind, difficulty, num_questions: num, include_case_study: caseStudy, instructions: instructions || undefined };
      if (source === "lesson") body.lesson_id = lesson;
      if (source === "month") body.scope = "month";
      if (source === "topic") body.topic = topic;
      const r = await api<any>("/documents", { body, idempotent: true });
      setDocId(r.document.id);
      setJobId(r.job_id);
      if (r.document.status === "ready") setDoc(r.document);
      else notify({ tone: "info", title: "Your assessment is on its way", body: "You can close this window. Find progress in Activity and the finished files in your library." });
    } catch (e) {
      notify({ tone: "error", title: "Couldn't create", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Create an assessment" size="lg"
      footer={doc ? <Button onClick={onClose}>Done</Button> : jobId ? (
        <Button onClick={onClose}>{job?.status === "failed" ? "Close" : "Continue in background"}</Button>
      ) : (
        <>
          {creditInfo && <span className="text-xs text-muted">{creditInfo.costs[kind]} credits · {creditInfo.remaining === null ? "Unlimited plan" : `${creditInfo.remaining} available`}</span>}
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={create} loading={busy || (!!jobId && !doc)} disabled={(source === "lesson" && !lesson) || (source === "topic" && !topic)}>Create</Button>
        </>
      )}>
      {doc ? (
        <div className="space-y-4">
          <Alert tone="success" title={doc.title}>Ready — with a separate answer key.</Alert>
          <DocumentFiles files={doc.files} />
        </div>
      ) : jobId ? (
        <div className="space-y-4 py-4"><JobLine job={job} />
          <Alert tone={job?.status === "failed" ? "warn" : "brand"} title={job?.status === "failed" ? "This assessment needs attention" : "No need to wait here"}>
            {job?.status === "failed" ? "Close this window and create a new assessment when you’re ready." : "Keep planning, explore another lesson, or close the browser. We’ll save your files in Library → Documents and notify you when they’re ready."}
          </Alert>
        </div>
      ) : (
        <div className="space-y-5">
          <Field label="Type"><Chips options={KINDS} value={kind} onChange={setKind} /></Field>
          {!lessonId && (
            <Field label="Based on">
              <Chips options={[{ value: "lesson", label: "A lesson" }, { value: "month", label: "Everything taught this month" }, { value: "topic", label: "A topic" }]}
                value={source} onChange={setSource} />
            </Field>
          )}
          {source === "lesson" && !lessonId && (
            <Field label="Lesson">
              <Select value={lesson} onChange={(e) => setLesson(e.target.value)}>
                <option value="">Choose a lesson…</option>
                {(lessons?.items || []).filter((l: any) => l.has_pptx).map((l: any) => (
                  <option key={l.id} value={l.id}>{l.topic} — L{l.number}: {l.title} (Grade {l.grade})</option>
                ))}
              </Select>
            </Field>
          )}
          {source === "topic" && <Field label="Topic"><Input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Equivalent fractions, Grade 5" /></Field>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Difficulty">
              <Select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                {["easy", "medium", "hard", "mixed", "tiered"].map((d) => <option key={d} value={d}>{d === "tiered" ? "Tiered (support / core / stretch)" : d}</option>)}
              </Select>
            </Field>
            <Field label="Questions">
              <Select value={num} onChange={(e) => setNum(Number(e.target.value))}>
                {[5, 10, 15, 20].map((n) => <option key={n} value={n}>{n} questions</option>)}
              </Select>
            </Field>
          </div>
          <Toggle checked={caseStudy} onChange={setCaseStudy} label="Include a case study" description="A short real-world scenario with application questions" />
          <Field label="Anything else? (optional)"><Textarea value={instructions} onChange={(e) => setInstructions(e.target.value)} placeholder="e.g. focus on the diagram of a leaf; avoid true/false" /></Field>
        </div>
      )}
    </Modal>
  );
}
