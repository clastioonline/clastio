"use client";

import { NotebookPen, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { StatusBadge } from "@/components/common";
import { DocumentDialog, DocumentFiles } from "@/components/document-dialog";
import { Badge, Button, Card, EmptyState, Input, PageHeader, Skeleton, Tabs } from "@/components/ui";
import { formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function Library() {
  const params = useSearchParams();
  const [tab, setTab] = useState<"lessons" | "documents" | "questions">((params.get("tab") as any) || "lessons");
  const [q, setQ] = useState("");
  const [docOpen, setDocOpen] = useState(false);
  const { data: lessons } = useApi<any>(tab === "lessons" ? "/lessons?limit=200" : null);
  const { data: docs, mutate: refreshDocs } = useApi<any>(tab === "documents" ? "/documents" : null, { refreshInterval: 4000 });
  const { data: questions } = useApi<any>(tab === "questions" ? `/questions?limit=200${q ? `&q=${encodeURIComponent(q)}` : ""}` : null);
  const filt = (s: string) => !q || s.toLowerCase().includes(q.toLowerCase());

  return (
    <div>
      <PageHeader title="Lessons & documents" subtitle="Everything you've prepared: slides, worksheets, quizzes, homework and your question bank."
        actions={<Button onClick={() => setDocOpen(true)}><Plus className="h-4 w-4" /> New worksheet or quiz</Button>} />
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={tab} onChange={setTab} tabs={[{ value: "lessons", label: "Lessons" }, { value: "documents", label: "Documents" }, { value: "questions", label: "Question bank" }]} />
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input className="ps-9" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {tab === "lessons" && (!lessons ? <Skeleton className="h-64" /> : lessons.items.length ? (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2 text-start text-xs uppercase tracking-wide text-muted">
              <tr><th className="px-4 py-3 text-start">Lesson</th><th className="hidden px-4 py-3 text-start sm:table-cell">Course</th><th className="hidden px-4 py-3 text-start md:table-cell">Date</th><th className="px-4 py-3 text-start">Status</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {lessons.items.filter((l: any) => filt(l.title + l.topic)).map((l: any) => (
                <tr key={l.id} className="hover:bg-surface-2/50">
                  <td className="px-4 py-3"><Link href={`/lessons/${l.id}`} className="font-medium text-ink hover:text-brand-700">L{l.number}: {l.title}</Link></td>
                  <td className="hidden px-4 py-3 text-muted sm:table-cell">{l.topic} · Grade {l.grade}</td>
                  <td className="hidden px-4 py-3 text-muted md:table-cell">{l.scheduled_date ? formatDate(l.scheduled_date) : "—"}</td>
                  <td className="px-4 py-3"><StatusBadge status={l.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : <EmptyState icon={<NotebookPen className="h-6 w-6" />} title="No lessons yet" action={<Button href="/projects/new">Create lessons</Button>} />)}

      {tab === "documents" && (!docs ? <Skeleton className="h-64" /> : docs.items.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {docs.items.filter((d: any) => filt(d.title)).map((d: any) => (
            <Card key={d.id} className="p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium text-ink">{d.title}</div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-muted"><Badge>{d.kind.replace("_", " ")}</Badge>{d.difficulty} · {formatDate(d.created_at)}</div>
                </div>
                <StatusBadge status={d.status} />
              </div>
              {d.status === "ready" && <div className="mt-3"><DocumentFiles files={d.files} /></div>}
              {d.error && <div className="mt-2 text-xs text-danger-700">{d.error}</div>}
            </Card>
          ))}
        </div>
      ) : <EmptyState title="No documents yet" description="Worksheets, quizzes, tests and homework you create appear here." action={<Button onClick={() => setDocOpen(true)}>Create one</Button>} />)}

      {tab === "questions" && (!questions ? <Skeleton className="h-64" /> : questions.items.length ? (
        <div className="space-y-3">
          {questions.items.map((x: any) => (
            <Card key={x.id} className="p-4 text-sm">
              <div className="flex flex-wrap items-center gap-2"><Badge tone="brand">{x.qtype.replace("_", " ")}</Badge><Badge>{x.difficulty}</Badge>{x.bloom && <Badge>{x.bloom}</Badge>}<span className="text-xs text-muted">used {x.used_count}×</span></div>
              <div className="mt-2 font-medium text-ink">{x.stem}</div>
              {x.options?.length > 0 && <div className="mt-1 text-muted">{x.options.map((o: string, i: number) => `${"ABCD"[i]}) ${o}`).join("   ")}</div>}
              <div className="mt-1 text-success-700">Answer: {x.answer}</div>
            </Card>
          ))}
        </div>
      ) : <EmptyState title="Your question bank is empty" description="Every question you generate is saved here, so future quizzes avoid repeats." />)}

      <DocumentDialog open={docOpen} onClose={() => { setDocOpen(false); refreshDocs(); }} />
    </div>
  );
}

export default function LessonsPage() {
  return <Suspense><Library /></Suspense>;
}
