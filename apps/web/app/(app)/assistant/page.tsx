"use client";

import { Bot, MessageSquarePlus, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Markdown } from "@/components/markdown";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, Select, Spinner, Textarea } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { cn } from "@/lib/utils";

type Msg = { role: "user" | "assistant"; content: string; actions?: any[]; pending?: boolean };

const SUGGESTIONS = [
  "What should I teach today?",
  "Prepare tomorrow's classes",
  "Prepare my week",
  "What did I teach last week?",
  "Create 3 lessons on fractions for grade 6 maths, 10 slides each",
  "Students struggled with photosynthesis. Give me a remedial lesson",
  "Create homework based on today's lesson",
  "Create a test from everything taught this month",
];

function Assistant() {
  const router = useRouter();
  const params = useSearchParams();
  const conversationId = params.get("conversation");
  const { user } = useMe();
  const { notify } = useToast();
  const { data: convs, mutate: refreshConvs } = useApi<any>("/assistant/conversations", { revalidateOnFocus: true });
  const { data: conversation, error, mutate: refreshConversation } = useApi<any>(conversationId ? `/assistant/conversations/${conversationId}` : null, {
    refreshInterval: (data: any) => ["queued", "running"].includes(data?.job?.status) ? 1500 : 0,
    revalidateOnFocus: true,
  });
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  const bottom = useRef<HTMLDivElement>(null);
  const pending = ["queued", "running"].includes(conversation?.job?.status);
  const sending = submitting || pending;
  const messages: Msg[] = conversation?.messages || [];
  const partial = pending ? conversation?.job?.result?.text || "" : "";

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, partial]);

  const open = (id: string) => router.push(`/assistant?conversation=${encodeURIComponent(id)}`);
  const send = async (value?: string) => {
    const msg = (value ?? text).trim();
    if (!msg || sending || submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    try {
      const result = await api<{ conversation_id: string; job_id: string }>("/assistant/tasks", {
        body: { text: msg, conversation_id: conversationId }, idempotent: true,
      });
      setText("");
      router.replace(`/assistant?conversation=${result.conversation_id}`);
      await refreshConversation();
      await refreshConvs();
      notify({ tone: "info", title: "Your assistant is on it", body: "Feel free to leave this page. Your reply will be saved in this conversation." });
    } catch (e) {
      notify({ tone: "error", title: "Couldn't send message", body: errorMessage(e) });
    } finally {
      setSubmitting(false);
      submittingRef.current = false;
    }
  };

  return (
    <div className="grid h-[calc(100vh-8rem)] gap-5 lg:grid-cols-[260px_1fr]">
      <Card className="hidden flex-col overflow-hidden lg:flex">
        <div className="border-b border-line p-3">
          <Button className="w-full" variant="outline" onClick={() => router.push("/assistant")}><MessageSquarePlus className="h-4 w-4" /> New chat</Button>
        </div>
        <div className="flex-1 space-y-1 overflow-y-auto p-2">
          {(convs?.items || []).map((c: any) => (
            <button key={c.id} onClick={() => open(c.id)}
              className={cn("w-full rounded-lg px-3 py-2 text-start text-sm hover:bg-surface-2", conversationId === c.id && "bg-brand-50 text-brand-700")}>
              <div className="truncate font-medium">{c.title}</div>
              <div className="text-xs text-muted">{timeAgo(c.updated_at)}</div>
            </button>
          ))}
        </div>
      </Card>
      <Card className="flex min-h-0 flex-col overflow-hidden">
        <div className="border-b border-line p-3 lg:hidden">
          <Select aria-label="Choose a conversation" value={conversationId || ""} onChange={(e) => e.target.value ? open(e.target.value) : router.push("/assistant")}>
            <option value="">New conversation</option>
            {(convs?.items || []).map((c: any) => <option key={c.id} value={c.id}>{c.title}</option>)}
          </Select>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-5 sm:p-6">
          {error && <Alert tone="warn" title="Couldn't load this conversation"><Button variant="outline" onClick={() => refreshConversation()}>Try again</Button></Alert>}
          {conversationId && !conversation && !error && <Spinner />}
          {conversation?.job?.status === "failed" && <Alert tone="warn" title="This reply couldn't finish">Your message is saved. You can send it again or try another question.</Alert>}
          {pending && <Alert tone="brand" title="Thinking in the background">You can switch pages or close the browser. Your reply will be saved here and in Activity.</Alert>}
          {!conversationId && !messages.length && (
            <div className="mx-auto max-w-2xl py-8 text-center">
              <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Sparkles className="h-7 w-7" /></div>
              <h1 className="mt-4 text-2xl font-semibold tracking-tight text-ink">How can I help, {user?.name?.split(" ")[0] || "teacher"}?</h1>
              <p className="mt-1 text-muted">I know your classes, timetable, curriculum progress and preferences.</p>
              <div className="mt-6 grid gap-2 sm:grid-cols-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="focus-ring rounded-xl border border-line bg-surface px-4 py-3 text-start text-sm text-ink-2 hover:border-brand-200 hover:bg-surface-2">{s}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m, i) => (
            <div key={i} className={cn("flex gap-3", m.role === "user" && "justify-end")}>
              {m.role === "assistant" && <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-600 text-white"><Bot className="h-4 w-4" /></div>}
              <div className={cn("max-w-[85%] rounded-2xl px-4 py-3", m.role === "user" ? "bg-brand-600 text-white" : "border border-line bg-surface-2/60")}>
                {m.role === "user" ? <div className="whitespace-pre-wrap text-sm">{m.content}</div> :
                  m.pending && !m.content ? <Spinner className="h-4 w-4" /> : <Markdown text={m.content} />}
                {!!m.actions?.filter((a) => a.type === "open").length && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {m.actions.filter((a) => a.type === "open").map((a, k) => (
                      <Link key={k} href={a.href} className="rounded-lg bg-surface px-3 py-1.5 text-xs font-medium text-brand-700 shadow-sm hover:bg-brand-50">{a.label} →</Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {pending && <div className="flex gap-3"><div className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-600 text-white"><Bot className="h-4 w-4" /></div><div className="max-w-[85%] rounded-2xl border border-line bg-surface-2/60 px-4 py-3">{partial ? <Markdown text={partial} /> : <span className="flex items-center gap-2 text-sm text-muted"><Spinner className="h-4 w-4" />{conversation.job.stage || "Preparing your reply"}</span>}</div></div>}
          <div ref={bottom} />
        </div>
        <form className="border-t border-line p-3 sm:p-4" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <div className="flex items-end gap-2">
            <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={1} className="min-h-[48px] resize-none"
              placeholder="Ask anything… e.g. “Create 2 lessons on magnets for grade 5”"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <Button type="submit" size="lg" loading={submitting} disabled={!text.trim() || sending || (!!conversationId && !conversation)} aria-label="Send"><Send className="h-4 w-4 rtl:rotate-180" /></Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

export default function AssistantPage() {
  return <Suspense fallback={<Spinner />}><Assistant /></Suspense>;
}
