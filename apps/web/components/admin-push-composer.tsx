"use client";

import { Bell, Check, Smartphone } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, Button, Card, Field, Input, Select, Textarea } from "@/components/ui";
import { errorMessage, useToast } from "@/components/toast";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const TEMPLATES = {
  custom: { name: "Custom message", title: "", body: "", link: "/notifications" },
  update: { name: "Product update", title: "Something new in Clastio", body: "Explore the latest improvements to your teaching workspace.", link: "/dashboard" },
  maintenance: { name: "Scheduled maintenance", title: "Scheduled maintenance", body: "Clastio will be briefly unavailable on [date] from [start] to [end]. Your saved lessons will be safe.", link: "/notifications" },
  reminder: { name: "Teaching reminder", title: "Ready for your next class?", body: "Open your lessons to review your slides and teaching notes before class.", link: "/lessons" },
  welcome: { name: "Welcome", title: "Welcome to Clastio", body: "Upload your notes, choose a template, and prepare your first lesson. We’re glad you’re here.", link: "/projects/new" },
};
type Template = keyof typeof TEMPLATES;
type Preview = { users: number; devices: number; audience_users: number; configured: boolean };

export function AdminPushComposer() {
  const { notify } = useToast();
  const { data: history, mutate } = useApi<any>("/admin/push-campaigns", { refreshInterval: 10000 });
  const [template, setTemplate] = useState<Template>("update");
  const [title, setTitle] = useState(TEMPLATES.update.title);
  const [body, setBody] = useState(TEMPLATES.update.body);
  const [link, setLink] = useState(TEMPLATES.update.link);
  const [audience, setAudience] = useState("teachers");
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const { data: recipients } = useApi<any>(audience === "selected" ? `/admin/push-campaigns/recipients?q=${encodeURIComponent(search)}` : null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setPreview(null); }, [title, body, link, audience, selected, template]);
  const payload = { template, title, body, link, audience, user_ids: Object.keys(selected) };
  const choose = (key: Template) => { setTemplate(key); setTitle(TEMPLATES[key].title); setBody(TEMPLATES[key].body); setLink(TEMPLATES[key].link); };
  const review = async () => {
    setBusy(true);
    try { setPreview(await api<Preview>("/admin/push-campaigns/preview", { body: payload })); }
    catch (error) { notify({ tone: "error", title: "Couldn't preview recipients", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  const send = async () => {
    setBusy(true);
    try {
      await api("/admin/push-campaigns", { body: payload, idempotent: true });
      setPreview(null); mutate();
      notify({ tone: "success", title: "Push campaign queued", body: "The worker will queue eligible devices. Delivery status appears below." });
    } catch (error) { notify({ tone: "error", title: "Couldn't queue campaign", body: errorMessage(error) }); }
    finally { setBusy(false); }
  };
  return <section className="space-y-5" aria-label="Admin push notifications">
    <div><h2 className="text-xl font-semibold">Send push notifications</h2><p className="mt-1 text-sm text-muted">Choose a template, edit your message, and review who can receive it. Sends only to active accounts with browser push and announcement consent.</p></div>
    {history?.configured === false && <Alert tone="warn" title="Web Push is not configured">Set the server’s Web Push public key, private key, and contact subject before sending. You can still compose and preview.</Alert>}
    <div className="grid gap-5 lg:grid-cols-2">
      <Card className="space-y-4 p-4 sm:p-5"><fieldset disabled={busy} className="space-y-4">
        <Field label="Template"><Select aria-label="Template" value={template} onChange={(event) => choose(event.target.value as Template)}>{Object.entries(TEMPLATES).map(([key, value]) => <option key={key} value={key}>{value.name}</option>)}</Select></Field>
        <Field label={`Title · ${title.length}/200`}><Input aria-label="Push title" value={title} maxLength={200} onChange={(event) => setTitle(event.target.value)} /></Field>
        <Field label={`Message · ${body.length}/500`}><Textarea aria-label="Push message" value={body} maxLength={500} onChange={(event) => setBody(event.target.value)} /></Field>
        <Field label="Open this page when tapped" hint="Internal app path, for example /lessons. Browser notifications support plain text."><Input value={link} onChange={(event) => setLink(event.target.value)} /></Field>
        <Field label="Recipients"><Select aria-label="Recipients" value={audience} onChange={(event) => setAudience(event.target.value)}><option value="teachers">All active teachers</option><option value="staff">All active staff</option><option value="everyone">Everyone active</option><option value="selected">Selected users</option></Select></Field>
        {audience === "selected" && <div className="space-y-2"><Input aria-label="Search recipients" placeholder="Search name or email" value={search} onChange={(event) => setSearch(event.target.value)} />
          <div className="max-h-48 space-y-1 overflow-y-auto">{recipients?.items?.map((person: any) => <label key={person.id} className="flex min-h-11 items-center gap-3 rounded-lg border border-line p-2 text-sm"><input type="checkbox" checked={person.id in selected} onChange={(event) => { const next = { ...selected }; if (event.target.checked) next[person.id] = person.name || person.email; else delete next[person.id]; setSelected(next); }} /><span className="min-w-0 break-words">{person.name}<span className="block text-xs text-muted">{person.email}</span></span></label>)}</div>
          <p className="text-xs text-muted">{Object.keys(selected).length} selected. Search returns up to 30 active users at a time.</p><div className="flex flex-wrap gap-2">{Object.entries(selected).map(([id, name]) => <Button size="sm" variant="outline" key={id} onClick={() => { const next = { ...selected }; delete next[id]; setSelected(next); }}>{name} ×</Button>)}</div>
        </div>}
        <Button loading={busy} disabled={title.trim().length < 3 || !body.trim() || audience === "selected" && !Object.keys(selected).length} onClick={review}>Review recipients</Button>
      </fieldset></Card>
      <div className="space-y-4"><Card className="bg-surface-2 p-5 sm:p-8"><div className="mb-5 flex items-center gap-2 text-sm text-muted"><Smartphone className="h-4 w-4" /> Notification preview</div>
        <div className="mx-auto max-w-sm rounded-2xl border border-line bg-surface p-4 shadow-lg"><div className="mb-2 flex items-center gap-2 text-xs text-muted"><Bell className="h-4 w-4 text-brand-600" /> Clastio <span className="ml-auto">now</span></div><h3 className="break-words font-semibold">{title || "Notification title"}</h3><p className="mt-1 whitespace-pre-wrap break-words text-sm text-ink-2">{body || "Your message appears here."}</p></div>
        <p className="mt-4 text-xs text-muted">Appearance varies by device and browser. Tap destination: {link || "/notifications"}</p>
      </Card>
      {preview && <Card className="space-y-3 p-5"><h3 className="flex items-center gap-2 font-semibold"><Check className="h-4 w-4" /> Ready for review</h3><p>{preview.users} opted-in users · {preview.devices} eligible devices</p><p className="text-sm text-muted">{preview.audience_users} active accounts match your audience. Accounts without announcement consent or an active browser subscription are excluded. Eligibility is checked again when sending.</p><Button loading={busy} disabled={!preview.configured || !preview.devices} onClick={send}>Send to {preview.users} users</Button></Card>}
      </div>
    </div>
    <Card className="space-y-3 p-4 sm:p-5"><h3 className="font-semibold">Recent push campaigns</h3>{!history ? <p className="text-sm text-muted">Loading campaigns…</p> : !history.items.length ? <p className="text-sm text-muted">No campaigns yet.</p> : history.items.map((campaign: any) => <div key={campaign.id} className="space-y-1 border-t border-line pt-3"><div className="flex flex-wrap justify-between gap-2"><strong>{campaign.title}</strong><span className="text-xs text-muted">{campaign.status} · {new Date(campaign.created_at).toLocaleString()}</span></div><p className="text-sm text-muted">{campaign.audience} · {Object.entries(campaign.delivery).map(([status, count]) => `${count} ${status}`).join(" · ") || (campaign.status === "succeeded" ? "No retained delivery records" : "Preparing delivery")}</p>{campaign.error && <p className="text-sm text-danger-700">{campaign.error}</p>}</div>)}</Card>
  </section>;
}
