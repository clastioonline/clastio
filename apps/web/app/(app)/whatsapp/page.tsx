"use client";

import { CircleCheck, MessageCircle, Send, Smartphone } from "lucide-react";
import { useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, EmptyState, Field, Input, PageHeader, Skeleton, Toggle } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export default function WhatsAppPage() {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/whatsapp", { refreshInterval: 4000 });
  const [phone, setPhone] = useState("");
  const [link, setLink] = useState<any>(null);
  const [sim, setSim] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  if (!data) return <Skeleton className="h-96" />;
  const c = data.contact;

  const startLink = async () => {
    setBusy("link");
    try {
      setLink(await api("/whatsapp/link", { body: { phone } }));
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't link", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const simulate = async (text: string, payload?: string) => {
    setBusy("sim");
    try {
      await api("/whatsapp/simulate", { body: { text, payload } });
      setSim("");
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Simulation failed", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const updateSettings = async (patch: any) => {
    await api("/whatsapp/settings", { method: "PUT", body: patch });
    mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="WhatsApp" subtitle="Your plan every school morning, a one-tap check-in after class, and your assistant on the go. Official WhatsApp Business Platform only." />
      {!data.enabled_on_plan && (
        <Alert tone="accent" title="WhatsApp isn't included in your plan">Upgrade to get daily plans and chat with your assistant on WhatsApp. <a className="font-medium underline" href="/billing">See plans</a></Alert>
      )}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<Smartphone className="h-5 w-5" />} title="Your number" subtitle={c?.verified ? "Connected" : "Link your WhatsApp number"} />
            <div className="space-y-4 p-5">
              {c?.verified ? (
                <div className="flex items-center gap-3 rounded-xl bg-success-50 p-3 text-sm text-success-700"><CircleCheck className="h-5 w-5" /> {c.phone} is connected{c.opted_in ? "" : " (paused)"}</div>
              ) : (
                <>
                  <Field label="Mobile number" hint="International format, e.g. +971 50 123 4567">
                    <div className="flex gap-2"><Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+971 50 123 4567" /><Button onClick={startLink} loading={busy === "link"} disabled={!phone || !data.enabled_on_plan}>Link</Button></div>
                  </Field>
                  {(link || c?.pending_code) && (
                    <Alert tone="brand" title="Almost there">
                      From WhatsApp on {link?.phone || c?.phone}, send <b>LINK {link?.code || c?.pending_code}</b> to our business number. This confirms it's you and that you want messages.
                    </Alert>
                  )}
                </>
              )}
              {c?.verified && (
                <div className="space-y-3">
                  <Toggle checked={c.opted_in} onChange={(v) => updateSettings({ opted_in: v })} label="Daily messages" description="Reply STOP in WhatsApp any time to pause" />
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Morning plan at"><Input type="time" value={c.daily_time} onChange={(e) => updateSettings({ daily_time: e.target.value })} /></Field>
                    <Field label="After-class check-in at"><Input type="time" value={c.reflection_time} onChange={(e) => updateSettings({ reflection_time: e.target.value })} /></Field>
                    <Field label="Quiet from"><Input type="time" value={c.quiet_start} onChange={(e) => updateSettings({ quiet_start: e.target.value })} /></Field>
                    <Field label="Quiet until"><Input type="time" value={c.quiet_end} onChange={(e) => updateSettings({ quiet_end: e.target.value })} /></Field>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={async () => { const r = await api<any>("/whatsapp/send-today", { method: "POST" }); notify({ tone: "success", title: r.sent ? "Today's plan sent" : "Monthly message limit reached" }); mutate(); }}>
                      <Send className="h-4 w-4" /> Send today's plan now
                    </Button>
                    <Button variant="ghost" onClick={async () => { await api("/whatsapp/unlink", { method: "POST" }); mutate(); }}>Unlink</Button>
                  </div>
                </div>
              )}
            </div>
          </Card>
          <Card className="p-5 text-sm text-muted">
            <div className="font-medium text-ink">What you'll receive</div>
            <ul className="mt-2 space-y-1">
              <li>• One message each school morning with your classes and what's ready</li>
              <li>• Tap “Show details” for lesson links (opens the app, already signed in)</li>
              <li>• A one-tap check-in after class: went well / ran out of time / struggled</li>
              <li>• Ask anything: “Prepare tomorrow's classes”, “Quiz on today's lesson”</li>
            </ul>
          </Card>
        </div>

        <Card className="flex flex-col overflow-hidden">
          <div className="flex items-center gap-3 bg-[#075e54] px-4 py-3 text-white">
            <MessageCircle className="h-5 w-5" />
            <div><div className="text-sm font-semibold">PPT Genie</div><div className="text-xs opacity-80">{data.live ? "Live WhatsApp" : "Simulation (no WhatsApp credentials configured)"}</div></div>
          </div>
          <div className="flex-1 space-y-2 overflow-y-auto bg-[#efeae2] p-4 dark:bg-surface-2" style={{ minHeight: 420, maxHeight: 560 }}>
            {!data.messages.length && <EmptyState title="No messages yet" description="Link your number, then messages will appear here." />}
            {[...data.messages].reverse().map((m: any, i: number) => (
              <div key={i} className={cn("flex", m.direction === "out" ? "justify-start" : "justify-end")}>
                <div className={cn("max-w-[85%] rounded-xl px-3 py-2 text-sm shadow-sm", m.direction === "out" ? "bg-white text-slate-800" : "bg-[#d9fdd3] text-slate-800")}>
                  <div className="whitespace-pre-wrap break-words">{m.body.replace(/https?:\/\/\S{60,}/g, "🔗 link")}</div>
                  <div className="mt-1 flex items-center justify-end gap-1.5 text-[10px] text-slate-500">
                    {m.template && <Badge className="border-0 bg-slate-100 px-1.5 text-[10px] text-slate-600">{m.template} · {m.category}</Badge>}
                    {formatDate(m.created_at, { hour: "2-digit", minute: "2-digit" })} · {m.status}
                  </div>
                </div>
              </div>
            ))}
          </div>
          {!data.live && c && (
            <div className="border-t border-line bg-surface p-3">
              <div className="mb-2 flex flex-wrap gap-2">
                {c.pending_code && <Button size="sm" variant="outline" onClick={() => simulate(`LINK ${c.pending_code}`)}>Send “LINK {c.pending_code}”</Button>}
                {c.verified && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => simulate("Show details", "SHOW_TODAY")}>Tap “Show details”</Button>
                    <Button size="sm" variant="outline" onClick={() => simulate("What should I teach tomorrow?")}>Ask about tomorrow</Button>
                  </>
                )}
              </div>
              <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); sim && simulate(sim); }}>
                <Input value={sim} onChange={(e) => setSim(e.target.value)} placeholder="Type as the teacher (simulation)…" />
                <Button type="submit" loading={busy === "sim"} disabled={!sim}><Send className="h-4 w-4" /></Button>
              </form>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
