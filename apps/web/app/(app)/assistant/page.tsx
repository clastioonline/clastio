"use client";

import { Bot, MessageSquarePlus, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Markdown } from "@/components/markdown";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Card, Spinner, Textarea } from "@/components/ui";
import { api, streamPost, timeAgo } from "@/lib/api";
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

export default function Assistant() {
  const { user } = useMe();
  const { notify } = useToast();
  const { data: convs, mutate: refreshConvs } = useApi<any>("/assistant/conversations");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => bottom.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  const open = async (id: string) => {
    const c = await api<any>(`/assistant/conversations/${id}`);
    setConversationId(id);
    setMessages(c.messages.map((m: any) => ({ role: m.role, content: m.content, actions: m.actions })));
  };

  const send = async (value?: string) => {
    const msg = (value ?? text).trim();
    if (!msg || sending) return;
    setText("");
    setSending(true);
    setMessages((m) => [...m, { role: "user", content: msg }, { role: "assistant", content: "", actions: [], pending: true }]);
    try {
      await streamPost("/assistant/messages", { text: msg, conversation_id: conversationId }, ({ event, data }) => {
        if (event === "conversation") setConversationId(data.id);
        if (event === "token") setMessages((m) => { const c = [...m]; const last = c[c.length - 1]; c[c.length - 1] = { ...last, content: last.content + data.text }; return c; });
        if (event === "action") setMessages((m) => { const c = [...m]; const last = c[c.length - 1]; c[c.length - 1] = { ...last, actions: [...(last.actions || []), data] }; return c; });
      });
    } catch (e) {
      notify({ tone: "error", title: "Assistant unavailable", body: errorMessage(e) });
    } finally {
      setMessages((m) => { const c = [...m]; c[c.length - 1] = { ...c[c.length - 1], pending: false }; return c; });
      setSending(false);
      refreshConvs();
    }
  };

  return (
    <div className="grid h-[calc(100vh-8rem)] gap-5 lg:grid-cols-[260px_1fr]">
      <Card className="hidden flex-col overflow-hidden lg:flex">
        <div className="border-b border-line p-3">
          <Button className="w-full" variant="outline" onClick={() => { setConversationId(null); setMessages([]); }}><MessageSquarePlus className="h-4 w-4" /> New chat</Button>
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
        <div className="flex-1 space-y-5 overflow-y-auto p-5 sm:p-6">
          {!messages.length && (
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
          <div ref={bottom} />
        </div>
        <form className="border-t border-line p-3 sm:p-4" onSubmit={(e) => { e.preventDefault(); send(); }}>
          <div className="flex items-end gap-2">
            <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={1} className="min-h-[48px] resize-none"
              placeholder="Ask anything… e.g. “Create 2 lessons on magnets for grade 5”"
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <Button type="submit" size="lg" loading={sending} disabled={!text.trim()} aria-label="Send"><Send className="h-4 w-4 rtl:rotate-180" /></Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
