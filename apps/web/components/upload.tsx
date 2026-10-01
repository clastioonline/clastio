"use client";

import { CircleCheck, FileUp, LoaderCircle, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button } from "@/components/ui";
import { useToast } from "@/components/toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const STAGES = ["Uploaded", "Analysing", "Extracting design", "Understanding content", "Creating template", "Ready"];

type UploadResult = { file: { id: string; status: string; stage: string | null; error: string | null }; job_id: string | null };

export function UploadDropzone({ kind = "style", onReady, onQueued, compact = false }: { kind?: "style" | "source"; onReady?: (info: { fileId: string; templateId?: string }) => void; onQueued?: () => void; compact?: boolean }) {
  const { notify } = useToast();
  const [drag, setDrag] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [stage, setStage] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rights, setRights] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const readyRef = useRef(onReady);
  const queuedRef = useRef(onQueued);
  readyRef.current = onReady;
  queuedRef.current = onQueued;

  const start = useCallback(async (f: File) => {
    setFile(f);
    setFileId(null);
    setError(null);
    setStatus("uploading");
    setStage("Uploading");
    const form = new FormData();
    form.append("file", f);
    form.append("kind", kind);
    form.append("name", f.name.replace(/\.(pptx?|pdf|docx|txt)$/i, ""));
    form.append("rights_confirmed", String(rights));
    try {
      const res = await api<UploadResult>("/uploads", { form });
      setFileId(res.file.id);
      if (res.file.status !== "failed") queuedRef.current?.();
      if (res.job_id && res.file.status !== "ready") notify({ tone: "info", title: "Upload received", body: "Processing continues in the background. You can carry on; we’ll notify you when it’s ready." });
      // Always fetch the completed upload detail: it contains the template id,
      // including when a fast worker finishes before the upload response arrives.
      setStatus(res.file.status === "ready" ? "processing" : res.file.status);
      setStage(res.file.stage);
      if (res.file.status === "failed") setError(res.file.error || "We couldn't analyse this file.");
    } catch (e: any) {
      setError(e.message);
      setStatus("failed");
    }
  }, [kind, rights, notify]);

  useEffect(() => {
    if (!fileId || status === "ready" || status === "failed") return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const res = await api<{ file: UploadResult["file"]; template_id: string | null }>(`/uploads/${fileId}`, { signal: controller.signal });
        if (stopped) return;
        setStage(res.file.stage);
        setStatus(res.file.status);
        if (res.file.status === "ready") {
          readyRef.current?.({ fileId, templateId: res.template_id || undefined });
          return;
        } else if (res.file.status === "failed") {
          setError(res.file.error || "We couldn't analyse this file.");
          return;
        }
      } catch {}
      if (!stopped) timer = setTimeout(poll, 1200);
    };
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [fileId, status]);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) start(f);
  };

  const idx = Math.max(0, STAGES.indexOf(stage || "Uploaded"));
  const busy = status && !["ready", "failed"].includes(status);

  if (file && status) {
    return (
      <div className="rounded-2xl border border-line bg-surface p-5">
        <div className="flex items-center gap-3">
          <div className={cn("grid h-10 w-10 place-items-center rounded-xl", status === "ready" ? "bg-success-50 text-success-500" : status === "failed" ? "bg-danger-50 text-danger-500" : "bg-brand-50 text-brand-600")}>
            {status === "ready" ? <CircleCheck className="h-5 w-5" /> : status === "failed" ? <TriangleAlert className="h-5 w-5" /> : <LoaderCircle className="h-5 w-5 animate-spin" />}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-ink">{file.name}</div>
            <div className="text-xs text-muted">{status === "ready" ? (kind === "style" ? "Your style is ready" : "Indexed for grounding") : stage || "Working…"}</div>
          </div>
          {!busy && <Button size="sm" variant="ghost" onClick={() => { setFile(null); setStatus(null); setFileId(null); }}>Upload another</Button>}
        </div>
        {kind === "style" && (
          <ol className="mt-4 grid grid-cols-3 gap-2 text-[11px] sm:grid-cols-6">
            {STAGES.map((s, i) => (
              <li key={s} className={cn("rounded-lg px-2 py-1.5 text-center", i < idx || status === "ready" ? "bg-success-50 text-success-700" : i === idx && busy ? "bg-brand-50 font-medium text-brand-700" : "bg-surface-2 text-muted")}>
                {s}
              </li>
            ))}
          </ol>
        )}
        {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
        {busy && <p className="mt-4 text-sm text-muted">{status === "uploading" ? "Transferring your file. Keep this tab open until the upload is received." : "You can leave this page. Track progress in Activity; your file keeps processing in the background."}</p>}
      </div>
    );
  }

  return (
    <div>
      <div role="button" tabIndex={0} onClick={() => inputRef.current?.click()} onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
        className={cn("focus-ring flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 text-center transition-colors",
          compact ? "py-8" : "py-12", drag ? "border-brand-500 bg-brand-50" : "border-line-strong bg-surface hover:border-brand-300 hover:bg-surface-2/60")}>
        <div className="grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600"><FileUp className="h-6 w-6" /></div>
        <div className="mt-3 font-medium text-ink">{kind === "style" ? "Drop a presentation you've taught with" : "Drop a textbook chapter or syllabus"}</div>
        <div className="mt-1 text-sm text-muted">{kind === "style" ? "PPTX, PPT or PDF · up to 100 MB · we never modify your original" : "PDF, PPTX, DOCX or TXT"}</div>
        <input ref={inputRef} type="file" className="hidden"
          accept={kind === "style" ? ".pptx,.ppt,.pdf" : ".pdf,.pptx,.ppt,.docx,.txt"}
          onChange={(e) => e.target.files?.[0] && start(e.target.files[0])} />
      </div>
      {kind === "source" && (
        <label className="mt-3 flex items-start gap-2 text-xs text-muted">
          <input type="checkbox" className="mt-0.5" checked={rights} onChange={(e) => setRights(e.target.checked)} />
          I have the right to use this material with my classes (e.g. school-provided textbook).
        </label>
      )}
    </div>
  );
}
