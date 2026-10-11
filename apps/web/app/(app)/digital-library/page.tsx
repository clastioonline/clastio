"use client";

import { BookOpen, LibraryBig, Sparkles } from "lucide-react";
import { Suspense, useState } from "react";
import { bookCurriculum, type LibraryBook } from "@/components/book-library-card";
import { EDUCATION_STAGES, EducatorContextFields, EducatorDocument, EducatorJobStatus, EducatorSources, SavedEducatorItems, useEducatorContext, useEducatorSelection, type EducatorItem } from "@/components/educator-workspace";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageHeader, Select, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";

function savedBookStage(book: LibraryBook): string {
  const recorded = book.metadata?.education_stage;
  if (EDUCATION_STAGES.some(stage => stage.value === recorded)) return recorded!;
  const grade = (book.metadata?.grade || "").trim();
  if (/university|undergraduate|postgraduate|college/i.test(grade)) return "university";
  if (/nursery|reception|kindergarten|early years|^kg\b|^fs[12]$/i.test(grade)) return "early_years";
  const year = Number(grade.replace(/^(?:grade|year)\s*/i, ""));
  return year >= 1 && year <= 6 ? "primary" : year >= 7 && year <= 13 ? "secondary" : "";
}

function DigitalLibraryPage() {
  const { notify } = useToast();
  const [stage, setStage] = useState("");
  const [subject, setSubject] = useState("");
  const [context, setContext] = useEducatorContext();
  const [kind, setKind] = useState("subject_primer");
  const [chapterCount, setChapterCount] = useState(4);
  const [instructions, setInstructions] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useEducatorSelection();
  const [jobId, setJobId] = useState<string | null>(null);
  const { data: books, error: booksError } = useApi<{ items: LibraryBook[] }>("/books");
  const { data: catalogue, error: catalogueError } = useApi<{ items: LibraryBook[] }>("/books/catalogue");
  const query = new URLSearchParams(); if (stage) query.set("education_stage", stage); if (subject.trim()) query.set("subject", subject.trim());
  const { data: list, error: listError, mutate: refreshList } = useApi<{ items: EducatorItem[] }>(`/digital-resources?${query}`, { refreshInterval: data => data?.items.some((item: EducatorItem) => ["queued", "generating"].includes(item.status)) ? 3000 : 0 });
  const { data: detail, error: detailError, mutate: refreshDetail } = useApi<EducatorItem>(selected ? `/digital-resources/${selected}` : null, { refreshInterval: data => data && ["queued", "generating"].includes(data.status) ? 2000 : 0 });
  const job = useJob(jobId || detail?.job?.id, async finished => { await refreshDetail(); await refreshList(); if (finished.status === "failed") notify({ tone: "error", title: "Could not generate guide", body: finished.error || "Check your inputs and try again." }); });
  const savedBooks = new Map((books?.items || []).filter(book => book.status === "ready").map(book => [book.id, book]));
  for (const book of catalogue?.items || []) if (book.status === "ready" && !savedBooks.has(book.id)) savedBooks.set(book.id, book);
  const visibleBooks = Array.from(savedBooks.values()).filter(book => (!stage || savedBookStage(book) === stage) && (!subject.trim() || book.metadata?.subject?.toLowerCase().includes(subject.trim().toLowerCase())));
  const browseStage = (next: string) => {
    setStage(next);
    if (next) setContext(previous => ({ ...previous, education_stage: next, framework: next === "university" ? "not_specified" : previous.framework }));
  };
  const generate = async (event: React.FormEvent) => {
    event.preventDefault(); if (busy || blocked) return; setBusy(true);
    try {
      const { framework: _framework, ...resourceContext } = context;
      const result = await api<any>("/digital-resources/generate", { body: { ...resourceContext, kind, chapter_count: chapterCount, instructions }, idempotent: true });
      setSelected(result.resource_id || result.resource?.id); setJobId(result.job_id || null); await refreshList(); notify({ tone: result.cached ? "success" : "info", title: result.cached ? "Saved resource reused" : "Preparing your study resource", body: result.cached ? "No new generation was needed for this matching request." : "Chapters, explanations, UAE examples and answer keys will be saved for reuse." });
    } catch (error) { notify({ tone: "error", title: "Could not prepare resource", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  const retry = async () => {
    if (!detail || busy) return; setBusy(true);
    try { const result = await api<any>(`/digital-resources/${detail.id}/regenerate`, { body: {}, idempotent: true }); setJobId(result.job_id); await refreshDetail(); await refreshList(); }
    catch (error) { notify({ tone: "error", title: "Could not retry guide", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  return <div className="space-y-5"><PageHeader title="Digital library" eyebrow="Early Years to University" subtitle="Keep books, subject primers and study guides available for future lessons." actions={<Button href="/books" variant="outline"><BookOpen className="h-4 w-4" /> Books & uploaded PDFs</Button>} />
    <Card className="p-4 sm:p-5"><div className="mb-4 flex items-center gap-2 font-semibold"><LibraryBig className="h-5 w-5 text-brand-600" /> Browse your saved resources</div><div className="flex flex-wrap gap-2"><Button variant={stage === "" ? "primary" : "outline"} size="sm" aria-pressed={stage === ""} onClick={() => browseStage("")}>All stages</Button>{EDUCATION_STAGES.map(item => <Button key={item.value} variant={stage === item.value ? "primary" : "outline"} size="sm" aria-pressed={stage === item.value} onClick={() => browseStage(item.value)}>{item.label}</Button>)}</div><Field label="Subject filter" className="mt-4 max-w-md" hint="Use the saved subject name to filter guides."><Input value={subject} onChange={event => setSubject(event.target.value)} placeholder="Science, Mathematics, Arabic…" /></Field></Card>
    <section aria-label="Saved books and notes" className="space-y-3"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold">Saved books & notes</h2><Button href="/books" variant="outline" size="sm">Manage book collection</Button></div>
      {(booksError || catalogueError) && <Alert tone="warn">Some saved books could not be loaded. Open Books & notes to retry.</Alert>}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">{visibleBooks.slice(0, 12).map(book => <Card key={book.id} className="flex min-w-0 flex-col gap-3 p-4"><div className="flex flex-wrap items-center gap-2"><Badge tone="success">Saved file ready</Badge>{book.catalogue?.published && <Badge>School catalogue</Badge>}</div><h3 className="break-words font-semibold">{book.metadata?.title || book.filename}</h3><p className="text-sm text-muted">{[book.metadata?.subject, book.metadata?.grade && `Grade / level ${book.metadata.grade}`, book.metadata?.curriculum || bookCurriculum(book), book.metadata?.edition].filter(Boolean).join(" · ")}</p><Button href={book.download} variant="outline" size="sm" className="mt-auto">Open saved book</Button></Card>)}</div>
      {!visibleBooks.length && <Alert tone="neutral">No saved book matches this category. Add an authorised book in Books & notes, or create a teaching guide below. Books without a recorded stage or grade appear under All stages.</Alert>}{visibleBooks.length > 12 && <Button href="/books" variant="outline">View all {visibleBooks.length} saved books</Button>}
    </section>
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_340px]"><div className="min-w-0 space-y-5"><Card><CardHeader title="Create a missing primer or study guide" icon={<Sparkles className="h-5 w-5" />} subtitle="Matching saved resources are reused automatically. New guides are clearly labelled as AI-generated teaching materials." /><form onSubmit={generate} className="space-y-4 p-5"><EducatorContextFields value={context} onChange={setContext} showFramework={false} /><div className="grid gap-4 sm:grid-cols-2"><Field label="Resource type"><Select value={kind} onChange={event => setKind(event.target.value)}><option value="subject_primer">Subject primer</option><option value="study_guide">Study guide</option></Select></Field><Field label="Number of chapters"><Input type="number" required min={1} max={6} value={chapterCount} onChange={event => setChapterCount(Number(event.target.value))} /></Field></div><Field label="Coverage and instructions"><Textarea value={instructions} maxLength={6000} onChange={event => setInstructions(event.target.value)} placeholder="Include key definitions, solved examples, UAE case studies, chapter summaries and practice questions with answers." /></Field><Button type="submit" loading={busy} disabled={blocked || job?.status === "queued" || job?.status === "running"}>Find or create resource</Button></form></Card><EducatorSources value={context} onChange={setContext} onBlocked={setBlocked} /><EducatorJobStatus job={job} />
      {detailError && <Alert tone="danger" title="Could not open resource">{errorMessage(detailError)}</Alert>}{selected && !detail && !detailError && <Spinner />}{detail?.error && <Alert tone="danger" title="Resource generation failed">{detail.error}{detail.status === "failed" && detail.origin === "generated" && <div className="mt-3"><Button variant="outline" loading={busy} onClick={retry}>Retry saved request</Button></div>}</Alert>}{detail?.content && Object.keys(detail.content).length > 0 && <EducatorDocument language={detail.language} title={detail.title} content={detail.content} downloads={detail.downloads}><Alert tone="neutral" className="mb-5">{detail.origin === "generated" ? "AI-generated teaching resource. Review accuracy and sources before classroom use; this is not an official textbook." : "Check the resource’s edition, source and usage rights before classroom use."}</Alert></EducatorDocument>}
      {!selected && <EmptyState icon={<BookOpen className="h-6 w-6" />} title="Your reusable teaching collection" description="Choose a saved resource to read, print or download it. Official and uploaded textbooks stay in Books & notes." />}
    </div><div className="min-w-0 space-y-3">{listError && <Alert tone="danger">{errorMessage(listError)}</Alert>}<SavedEducatorItems title="Saved library resources" items={list?.items || []} selected={selected} onSelect={id => { setSelected(id); setJobId(null); }} empty="No resources match these filters" /></div></div></div>;
}

export default function Page() { return <Suspense fallback={<Spinner />}><DigitalLibraryPage /></Suspense>; }
