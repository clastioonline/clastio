"use client";

import { Bot, MessageSquare, MessageSquarePlus, Send, Sparkles } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { EducatorContextFields, EducatorDocument, EducatorJobStatus, EducatorSources, INITIAL_EDUCATOR_CONTEXT, SavedEducatorItems, useEducatorContext, useEducatorSelection, type EducatorContext, type EducatorItem } from "@/components/educator-workspace";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, PageHeader, Spinner, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useJob } from "@/lib/hooks";
import { SUBJECTS } from "@/lib/utils";

const TASK_IDEAS = [
  "Generate a differentiated reading task for Grade 6 Science about ecosystems, linking it to UAE mangroves. Include SEN scaffolds, ELL sentence frames and an answer key.",
  "Create a formative assessment with a hinge question, exit ticket and expected responses for this topic.",
  "Prepare a collaborative problem-solving activity with a UAE case study and an extension challenge.",
];

type CopilotConversation = { id: string; title: string; updated_at?: string; messages?: { id: string; role: "user" | "assistant"; content: string; actions?: { type: string; resource_id?: string; href?: string }[] }[] };
type ResumeContext = { resource_id?: string; conversation_id?: string; context_revision: number };

function savedTaskContext(item: EducatorItem, previous: EducatorContext): EducatorContext {
  const saved = item.request && typeof item.request === "object" ? item.request as Record<string, unknown> : {};
  const next = { ...previous };
  for (const key of ["topic", "subject", "grade", "education_stage", "curriculum", "language", "framework"] as const) {
    const value = saved[key] ?? item[key];
    if (typeof value === "string") next[key] = value;
  }
  next.source_file_ids = Array.isArray(saved.source_file_ids) ? saved.source_file_ids.filter((id): id is string => typeof id === "string").slice(0, 5) : [];
  next.source_page_ranges = {};
  if (saved.source_page_ranges && typeof saved.source_page_ranges === "object") {
    for (const [id, pages] of Object.entries(saved.source_page_ranges)) {
      if (next.source_file_ids.includes(id) && Array.isArray(pages) && pages.length === 2 && pages.every(Number.isInteger)) next.source_page_ranges[id] = [pages[0], pages[1]];
    }
  }
  if (next.education_stage === "university" && ["khda", "adek", "moe"].includes(next.framework)) next.framework = "not_specified";
  return next;
}

/** Explicit details in the teacher's latest request override saved profile defaults. */
function requestedContext(text: string, previous: EducatorContext): EducatorContext {
  const next = { ...previous };
  const gradeMatches = [...text.matchAll(/\b(grade|year)\s*(1[0-3]|[1-9])\b/gi)];
  const grades = new Set(gradeMatches.map(match => match[2]));
  if (grades.size === 1) {
    const gradeMatch = gradeMatches[0];
    next.grade = gradeMatch[2];
    const university = /\b(?:university|undergraduate|postgraduate|college)\b/i.test(text)
      || (gradeMatch[1].toLowerCase() === "year" && previous.education_stage === "university");
    next.education_stage = university ? "university" : Number(next.grade) <= 6 ? "primary" : "secondary";
  }
  const names = SUBJECTS.map(subject => ({ subject, pattern: subject.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") }));
  const matches = names.filter(item => new RegExp(`\\b${item.pattern}\\b`, "i").test(text));
  const directSubject = matches.find(item => new RegExp(`\\b(?:grade|year)\\s*(?:1[0-3]|[1-9])\\s*[,;:–-]?\\s*(?:in\\s+)?${item.pattern}\\b|\\b${item.pattern}\\s+(?:for\\s+)?(?:grade|year)\\s*(?:1[0-3]|[1-9])\\b`, "i").test(text));
  if (directSubject) next.subject = directSubject.subject;
  else if (matches.length === 1) next.subject = matches[0].subject;
  const about = /\babout\s+(.+)/i.exec(text);
  const topic = about?.[1].split(/,\s*(?:link(?:ing)?|connect(?:ing)?|includ(?:e|ing)|with|using|and\s+include)\b|[.!?](?:\s|$)|\n/i)[0].trim();
  if (topic && topic.length <= 300 && !/^(?:it|this|this topic|the topic|same topic|that topic)$/i.test(topic)) next.topic = topic;
  if (next.education_stage === "university" && ["khda", "adek", "moe"].includes(next.framework)) next.framework = "not_specified";
  return next;
}

function CopilotPage() {
  const { notify } = useToast();
  const [context, setContext] = useEducatorContext({ ...INITIAL_EDUCATOR_CONTEXT });
  const [request, setRequest] = useState("");
  const [submittedRequest, setSubmittedRequest] = useState("");
  const [blocked, setBlocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useEducatorSelection();
  const contextRevision = useRef(0);
  const [resumeContext, setResumeContext] = useState<ResumeContext | null>(() => selected ? { resource_id: selected, context_revision: 0 } : null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [showContext, setShowContext] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const { data: conversations, mutate: refreshConversations } = useApi<{ items: CopilotConversation[] }>("/copilot/conversations");
  const { data: conversation, error: conversationError, mutate: refreshConversation } = useApi<CopilotConversation>(conversationId ? `/copilot/conversations/${conversationId}` : null, { refreshInterval: jobId ? 3000 : 0 });
  const { data: history, error: historyError, mutate: refreshHistory } = useApi<{ items: EducatorItem[] }>("/copilot/resources", { refreshInterval: data => data?.items.some((item: EducatorItem) => ["queued", "generating"].includes(item.status)) ? 3000 : 0 });
  const { data: detail, error: detailError, mutate: refreshDetail } = useApi<EducatorItem>(selected ? `/digital-resources/${selected}` : null, { refreshInterval: data => data && ["queued", "generating"].includes(data.status) ? 2000 : 0 });
  useEffect(() => {
    if (!resumeContext?.conversation_id || conversation?.id !== resumeContext.conversation_id) return;
    const latest = [...(conversation.messages || [])].reverse().flatMap(message => message.actions || []).find(action => action.type === "copilot_resource" && action.resource_id);
    if (!latest?.resource_id) { setResumeContext(null); return; }
    setResumeContext({ resource_id: latest.resource_id, context_revision: resumeContext.context_revision });
    setSelected(latest.resource_id);
  }, [conversation, resumeContext, setSelected]);
  useEffect(() => {
    if (!resumeContext?.resource_id || detail?.id !== resumeContext.resource_id) return;
    // A teacher can adjust scope while the saved request is loading. That edit wins.
    if (contextRevision.current === resumeContext.context_revision) setContext(previous => savedTaskContext(detail, previous));
    setResumeContext(null);
  }, [detail, resumeContext, setContext]);
  useEffect(() => {
    if ((resumeContext?.resource_id && detailError) || (resumeContext?.conversation_id && conversationError)) setResumeContext(null);
  }, [detailError, conversationError, resumeContext]);
  const editContext = (next: EducatorContext) => { contextRevision.current += 1; setResumeContext(null); setContext(next); };
  const openTask = (id: string, saved = false) => {
    setResumeContext({ resource_id: id, context_revision: contextRevision.current });
    setSelected(id); if (saved) setConversationId(null); setSubmittedRequest(""); setJobId(null);
  };
  const openConversation = (id: string) => {
    setResumeContext({ conversation_id: id, context_revision: contextRevision.current });
    setConversationId(id); setSelected(null); setSubmittedRequest(""); setJobId(null);
  };
  useEffect(() => {
    const saved = detail?.request as { conversation_id?: string } | undefined;
    if (!conversationId && detail?.id === selected && saved?.conversation_id) setConversationId(saved.conversation_id);
  }, [detail, conversationId, selected]);
  const job = useJob(jobId || detail?.job?.id, async finished => { await Promise.all([refreshDetail(), refreshHistory(), refreshConversation(), refreshConversations()]); setJobId(null); if (finished.status === "failed") notify({ tone: "error", title: "Could not prepare classroom task", body: finished.error || "Your request is saved; check your inputs and try again." }); });
  const send = async (value?: string) => {
    const text = (value ?? request).trim(); if (!text || busy || blocked || resumeContext || job?.status === "running" || job?.status === "queued") return;
    setBusy(true);
    try {
      const outgoing = requestedContext(text, context);
      setContext(outgoing);
      const result = await api<any>("/copilot/resources", { body: { request: text, ...outgoing, topic: outgoing.topic.trim() || null, conversation_id: conversationId }, idempotent: true });
      setSubmittedRequest(text); setRequest(""); setSelected(result.resource.id); setJobId(result.job_id || null); setConversationId(result.conversation_id || conversationId); await Promise.all([refreshHistory(), refreshConversations(), refreshConversation()]);
      if (result.cached) notify({ tone: "success", title: "Saved task reused", body: "This matching task is already available; no new generation was needed." });
    } catch (error) { notify({ tone: "error", title: "Could not send request", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  const task = detail?.content?.printable_task || detail?.content;
  const savedRequest = (detail?.request as { request?: string } | undefined)?.request;
  const retry = async () => {
    if (!detail || busy) return; setBusy(true);
    try { const result = await api<any>(`/digital-resources/${detail.id}/regenerate`, { body: {}, idempotent: true }); setJobId(result.job_id); await refreshDetail(); await refreshHistory(); }
    catch (error) { notify({ tone: "error", title: "Could not retry task", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  return <div className="space-y-5"><PageHeader title="AI teacher copilot" eyebrow="Your classroom assistant" subtitle="Ask for a differentiated task, formative check or UAE-connected activity. Get a saved, printable classroom resource." actions={<Button href="/assistant" variant="outline"><MessageSquare className="h-4 w-4" /> Open teaching chat</Button>} />
    <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,1fr)_320px]"><div className="min-w-0 space-y-5"><Card className="space-y-4 p-4 sm:p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">Classroom context</h2><p className="text-sm text-muted">{context.subject} · {context.grade} · {context.curriculum} · {context.language === "ar" ? "Arabic" : "English"}</p><p className="mt-1 break-words text-xs text-muted capitalize">{context.education_stage.replaceAll("_", " ")}{context.topic && ` · ${context.topic}`}</p></div><Button variant="outline" size="sm" aria-expanded={showContext} onClick={() => setShowContext(value => !value)}>{showContext ? "Hide context" : "Adjust context"}</Button></div>{showContext && <><EducatorContextFields value={context} onChange={editContext} /><EducatorSources value={context} onChange={editContext} onBlocked={setBlocked} /></>}</Card>
      <Card className="min-w-0 overflow-hidden"><div className="space-y-5 p-4 sm:p-6">{!selected && !conversationId && <div className="mx-auto max-w-2xl py-5 text-center"><div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Sparkles className="h-6 w-6" /></div><h2 className="mt-3 text-xl font-semibold">What does your class need next?</h2><p className="mt-2 text-sm text-muted">Clastio prepares a student task with inclusive scaffolds, teacher guidance and expected answers.</p><div className="mt-5 grid gap-2">{TASK_IDEAS.map(idea => <button key={idea} type="button" onClick={() => setRequest(idea)} className="focus-ring rounded-xl border border-line p-3 text-start text-sm hover:border-brand-300 hover:bg-surface-2">{idea}</button>)}</div></div>}
        {conversationError && <Alert tone="warn">Could not load this conversation. Your saved classroom tasks remain available.</Alert>}
        {conversation?.messages?.map(message => <div key={message.id} className={`flex min-w-0 ${message.role === "user" ? "justify-end" : "justify-start"}`}><div className={`max-w-[95%] min-w-0 rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "bg-brand-600 text-white whitespace-pre-wrap break-words" : "border border-line bg-surface-2"}`}>{message.role === "user" ? message.content : <Markdown text={message.content} />}{message.actions?.filter(action => action.type === "copilot_resource" && action.resource_id).map(action => <Button key={action.resource_id} variant="outline" size="sm" className="mt-3" onClick={() => openTask(action.resource_id!)}>Open printable classroom task</Button>)}</div></div>)}
        {(submittedRequest || savedRequest) && !conversation?.messages?.some(message => message.role === "user" && message.content === (submittedRequest || savedRequest)) && <div className="flex justify-end"><div className="max-w-[95%] rounded-2xl bg-brand-600 px-4 py-3 text-sm leading-6 text-white whitespace-pre-wrap break-words">{submittedRequest || savedRequest}</div></div>}
        {(selected || busy) && <div className="flex min-w-0 items-start gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-600 text-white"><Bot className="h-4 w-4" /></div><div className="min-w-0 flex-1 space-y-3"><EducatorJobStatus job={job} />{detailError && <Alert tone="danger" title="Could not open task">{errorMessage(detailError)}</Alert>}{((selected && !detail && !detailError) || busy) && <Spinner />}{detail?.error && <Alert tone="danger" title="Task generation failed">{detail.error}{detail.status === "failed" && <div className="mt-3"><Button variant="outline" loading={busy} onClick={retry}>Retry saved request</Button></div>}</Alert>}{detail && task && typeof task === "object" && Object.keys(task).length > 0 && <EducatorDocument language={detail.language} title={detail.title} content={task} downloads={detail.downloads}><p className="mb-4 text-xs text-muted">AI-generated teaching task · review the answer key and classroom suitability before use.</p></EducatorDocument>}</div></div>}
      </div><form className="border-t border-line p-4" onSubmit={event => { event.preventDefault(); send(); }}>{blocked && <Alert tone="warn" className="mb-3">A selected source is still indexing or needs attention. Open classroom context to check the book’s status before generating.</Alert>}<label className="mb-2 block text-sm font-medium" htmlFor="copilot-request">Ask your teacher copilot</label><div className="flex items-end gap-2"><Textarea id="copilot-request" value={request} onChange={event => setRequest(event.target.value)} rows={3} maxLength={2000} placeholder="Create a differentiated reading task about UAE mangroves…" onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); send(); } }} /><Button type="submit" size="icon" loading={busy} disabled={!request.trim() || blocked || !!resumeContext || job?.status === "running" || job?.status === "queued"} aria-label="Generate printable classroom task"><Send className="h-4 w-4 rtl:rotate-180" /></Button></div><p className="mt-2 text-xs text-muted">Enter sends · Shift+Enter adds a line. Include learning needs without individual student names or diagnoses.</p></form></Card>
    </div><div className="min-w-0 space-y-3"><Button variant="outline" className="w-full" disabled={busy || job?.status === "queued" || job?.status === "running"} onClick={() => { setResumeContext(null); setConversationId(null); setSelected(null); setSubmittedRequest(""); setRequest(""); setJobId(null); }}><MessageSquarePlus className="h-4 w-4" /> New copilot conversation</Button>{!!conversations?.items.length && <Card className="space-y-3 p-4"><h2 className="font-semibold">Saved conversations</h2>{conversations.items.map(item => <button key={item.id} type="button" aria-pressed={conversationId === item.id} onClick={() => openConversation(item.id)} className="focus-ring block w-full break-words rounded-xl border border-line p-3 text-start text-sm hover:bg-surface-2">{item.title}</button>)}</Card>}{historyError && <Alert tone="danger">{errorMessage(historyError)}</Alert>}<SavedEducatorItems title="My saved classroom tasks" items={history?.items || []} selected={selected} onSelect={id => openTask(id, true)} empty="Your copilot tasks will appear here" /><Button variant="outline" className="w-full" href="/digital-library">Browse all library resources</Button></div></div></div>;
}

export default function Page() { return <Suspense fallback={<Spinner />}><CopilotPage /></Suspense>; }
