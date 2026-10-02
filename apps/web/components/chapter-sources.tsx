"use client";

import { Upload, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, CardHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export function ChapterSources({ value, onChange, onBlocked }: {
  value: string[]; onChange: (ids: string[]) => void; onBlocked: (blocked: boolean) => void;
}) {
  const { data, mutate } = useApi<any>("/uploads?kind=source");
  const { notify } = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const items: any[] = data?.items || [];
  const pending = items.some((file) => ["queued", "processing"].includes(file.status));
  const selectedNotReady = value.some((id) => !items.some((file) => file.id === id && file.status === "ready"));
  useEffect(() => { onBlocked(uploading || selectedNotReady); }, [uploading, selectedNotReady, onBlocked]);
  useEffect(() => {
    if (!pending && !selectedNotReady) return;
    const timer = setInterval(() => mutate(), 2000);
    return () => clearInterval(timer);
  }, [pending, selectedNotReady, mutate]);
  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    let ids = [...value];
    try {
      for (const file of Array.from(files)) {
        if (ids.length >= 10) throw new Error("Choose up to 10 books or notes per chapter.");
        const form = new FormData();
        form.append("file", file);
        form.append("kind", "source");
        const result = await api<any>("/uploads", { form });
        ids = Array.from(new Set([...ids, result.file.id]));
        onChange(ids);
        await mutate();
      }
    } catch (error) {
      notify({ tone: "error", title: "Couldn't upload source", body: errorMessage(error) });
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  };
  return <div data-tour="chapter-sources"><Card>
    <CardHeader title="Books & notes" subtitle="Upload a textbook chapter, teaching notes or an existing lesson. Only the sources you select here will ground this chapter." />
    <div className="space-y-3 p-5">
      <input ref={input} type="file" className="hidden" multiple accept=".pdf,.docx,.txt,.pptx,.ppt" aria-label="Choose books and notes" onChange={(e) => upload(e.target.files)} />
      <Button variant="outline" loading={uploading} onClick={() => input.current?.click()} disabled={value.length >= 10}><Upload className="h-4 w-4" /> Upload books / notes</Button>
      <p className="text-xs text-muted">PDF, Word, text or PowerPoint. For scanned books, use a PDF with searchable text. Mention the chapter or relevant pages in your instructions.</p>
      {items.map((file) => {
        const selected = value.includes(file.id);
        return <div key={file.id} className="rounded-xl border border-line p-3 text-sm">
          <label className="flex items-start gap-3">
            <input type="checkbox" className="mt-1" checked={selected} disabled={!selected && (file.status !== "ready" || value.length >= 10)} onChange={() => onChange(selected ? value.filter((id) => id !== file.id) : [...value, file.id])} />
            <span className="min-w-0 flex-1"><span className="break-words font-medium">{file.filename}</span><span className="mt-1 block text-xs text-muted">{file.status === "ready" ? `Ready · ${file.page_count || 0} pages` : file.stage || file.status}</span></span>
            {selected && <button type="button" aria-label={`Remove ${file.filename} from chapter`} onClick={() => onChange(value.filter((id) => id !== file.id))}><X className="h-4 w-4" /></button>}
          </label>
          {file.error && <p className="mt-2 text-xs text-red-600">{file.error}</p>}
        </div>;
      })}
      {selectedNotReady && <Alert tone="neutral">Wait for the selected sources to finish processing, or remove a source that failed.</Alert>}
    </div>
  </Card></div>;
}
