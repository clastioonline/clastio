"use client";

import { CircleCheck, CreditCard, Gift, ImagePlay, Palette, Plus, Trash, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, Field, Input, PageHeader, Select, Skeleton, Stat, Toggle } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";


function Check({ ok, label, env }: { ok: boolean; label: string; env: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className="flex items-center gap-2 text-ink-2">
        {ok ? <CircleCheck className="h-4 w-4 text-success-500" /> : <TriangleAlert className="h-4 w-4 text-accent-500" />}{label}
      </span>
      <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-muted">{env}</code>
    </div>
  );
}

const list = (v: string) => v.split(",").map((x) => x.trim()).filter(Boolean);

export default function AdminMedia() {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/admin/media");
  const { data: settings, mutate: mutateSettings } = useApi<any>("/admin/settings");
  const { data: planList } = useApi<any>("/admin/plans");
  const PLANS = (planList?.items || []).filter((p: any) => p.code !== "free");
  const [media, setMedia] = useState<any>(null);
  const [billing, setBilling] = useState<any>(null);
  const [skin, setSkin] = useState("classic");
  const [grant, setGrant] = useState({ email: "", amount: 50, note: "" });
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    if (settings) {
      setMedia(settings.media);
      setBilling(settings.billing);
      setSkin(settings.ui?.default_skin || "classic");
    }
  }, [settings]);

  const save = async (key: string, value: any, label: string) => {
    setBusy(key);
    try {
      await api(`/admin/settings/${key}`, { method: "PUT", body: value });
      notify({ tone: "success", title: `${label} saved` });
      mutate();
      mutateSettings();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const doGrant = async () => {
    setBusy("grant");
    try {
      const r = await api<any>("/admin/media/grant", { body: grant });
      notify({ tone: "success", title: "Credits updated", body: `${r.email} now has ${r.balance} media credits.` });
      setGrant({ ...grant, email: "", note: "" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't update credits", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };

  if (!data || !media || !billing) return <Skeleton className="h-96" />;
  const conf = data.billing.configured;
  const setPack = (i: number, patch: any) => setMedia({ ...media, packs: media.packs.map((p: any, j: number) => (j === i ? { ...p, ...patch } : p)) });
  const products = billing.dodo_products || {};
  const count = (kind: string, status?: string) => data.usage.filter((u: any) => u.kind === kind && (!status || u.status === status)).reduce((a: number, u: any) => a + u.count, 0);

  return (
    <div className="space-y-6">
      <PageHeader title="Payments & media" subtitle="Choose the payment gateway, price the media studio and manage credits. Changes apply immediately." />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Images (30 days)" value={count("image")} hint={`${count("image", "failed")} failed`} />
        <Stat label="Videos (30 days)" value={count("video")} hint={`${count("video", "failed")} failed`} />
        <Stat label="Credits spent" value={data.usage.filter((u: any) => u.status !== "failed").reduce((a: number, u: any) => a + u.credits, 0)} />
        <Stat label="Credits sold" value={data.credits_sold} hint="from packs, 30 days" />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader icon={<CreditCard className="h-5 w-5" />} title="Payment gateway"
            subtitle={data.billing.active ? `Checkout currently uses ${data.billing.active === "dodo" ? "Dodo Payments" : "Stripe"}.` : "No gateway is configured, so plans can only be assigned manually."} />
          <div className="space-y-5 p-5">
            <Field label="Gateway">
              <Select value={billing.provider} onChange={(e) => setBilling({ ...billing, provider: e.target.value })}>
                <option value="auto">Automatic (Dodo Payments if configured, else Stripe)</option>
                <option value="dodo">Dodo Payments</option>
                <option value="stripe">Stripe</option>
              </Select>
            </Field>
            <div className="rounded-xl border border-line px-4 py-2">
              <div className="py-1 text-xs font-semibold uppercase tracking-wide text-muted">Server keys (set in .env, never here)</div>
              <Check ok={conf.dodo} label={`Dodo Payments API key (${conf.dodo_environment === "live_mode" ? "live" : "test"} mode)`} env="DODO_PAYMENTS_API_KEY" />
              <Check ok={conf.dodo_webhook} label="Dodo webhook secret" env="DODO_PAYMENTS_WEBHOOK_KEY" />
              <Check ok={conf.stripe} label="Stripe secret key" env="STRIPE_SECRET_KEY" />
              <Check ok={conf.stripe_webhook} label="Stripe webhook secret" env="STRIPE_WEBHOOK_SECRET" />
            </div>
            <div>
              <div className="mb-2 text-sm font-medium text-ink">Dodo product ids for plans</div>
              <p className="mb-3 text-xs text-muted">Create a subscription product per plan and interval in the Dodo dashboard and paste its id (pdt_…).</p>
              <div className="space-y-2">
                {PLANS.map((p: any) => (
                  <div key={p.code} className="grid grid-cols-[8rem_1fr_1fr] items-center gap-2 text-sm">
                    <span className="truncate text-ink-2">{p.name}</span>
                    {(["month", "year"] as const).map((iv) => (
                      <Input key={iv} aria-label={`${p.name} ${iv}ly product id`} placeholder={iv === "month" ? "Monthly pdt_…" : "Yearly pdt_…"}
                        value={products[`${p.code}_${iv}`] || ""}
                        onChange={(e) => setBilling({ ...billing, dodo_products: { ...products, [`${p.code}_${iv}`]: e.target.value.trim() } })} />
                    ))}
                  </div>
                ))}
              </div>
            </div>
            <p className="text-xs text-muted">Webhook URLs: <code>/api/v1/webhooks/dodo</code> (Dodo) and <code>/api/v1/webhooks/stripe</code> (Stripe) on your public domain.</p>
            <div className="flex justify-end"><Button loading={busy === "billing"} onClick={() => save("billing", billing, "Payment settings")}>Save payments</Button></div>
          </div>
        </Card>

        <Card>
          <CardHeader icon={<ImagePlay className="h-5 w-5" />} title="Media studio" subtitle="AI images and videos, paid with media credits (separate from lesson credits)." />
          <div className="space-y-4 p-5">
            <Toggle checked={!!media.enabled} onChange={(v) => setMedia({ ...media, enabled: v })} label="Media studio is on" description="When off, teachers can see their media but can't create more." />
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Image (credits)"><Input type="number" min={0} value={media.image_credits} onChange={(e) => setMedia({ ...media, image_credits: Number(e.target.value) })} /></Field>
              <Field label="Video (credits/sec)"><Input type="number" min={0} value={media.video_credits_per_second} onChange={(e) => setMedia({ ...media, video_credits_per_second: Number(e.target.value) })} /></Field>
              <Field label="Video lengths" hint="seconds, comma separated"><Input value={(media.video_seconds || []).join(", ")} onChange={(e) => setMedia({ ...media, video_seconds: list(e.target.value).map(Number).filter((n) => n > 0) })} /></Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Image model" hint="empty = default routing, e.g. openai:gpt-image-1"><Input value={media.image_model} onChange={(e) => setMedia({ ...media, image_model: e.target.value.trim() })} /></Field>
              <Field label="Video model" hint="e.g. openai:sora-2 or gemini:veo-3.0-fast-generate-001"><Input value={media.video_model} onChange={(e) => setMedia({ ...media, video_model: e.target.value.trim() })} /></Field>
            </div>
            <Field label="Styles teachers can pick" hint="comma separated"><Input value={(media.styles || []).join(", ")} onChange={(e) => setMedia({ ...media, styles: list(e.target.value) })} /></Field>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-ink">Credit packs</span>
                <Button size="sm" variant="ghost" onClick={() => setMedia({ ...media, packs: [...media.packs, { code: `pack${media.packs.length + 1}`, name: "New pack", credits: 100, price_aed: 29, dodo_product_id: "", active: true }] })}><Plus className="h-4 w-4" /> Add pack</Button>
              </div>
              <div className="space-y-2">
                {media.packs.map((p: any, i: number) => (
                  <div key={i} className="space-y-2 rounded-xl border border-line p-3">
                    <div className="grid grid-cols-[1fr_6rem_6rem] gap-2">
                      <Field label="Pack name"><Input value={p.name} onChange={(e) => setPack(i, { name: e.target.value })} /></Field>
                      <Field label="Credits"><Input type="number" value={p.credits} onChange={(e) => setPack(i, { credits: Number(e.target.value) })} /></Field>
                      <Field label="AED"><Input type="number" value={p.price_aed} onChange={(e) => setPack(i, { price_aed: Number(e.target.value) })} /></Field>
                    </div>
                    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                      <Input aria-label="Dodo product id" placeholder="Dodo one-time product id (pdt_…)" value={p.dodo_product_id || ""} onChange={(e) => setPack(i, { dodo_product_id: e.target.value.trim() })} />
                      <label className="flex items-center gap-1.5 whitespace-nowrap text-xs text-muted"><input type="checkbox" checked={p.active !== false} onChange={(e) => setPack(i, { active: e.target.checked })} />On sale</label>
                      <Button size="icon" variant="ghost" aria-label="Remove pack" onClick={() => setMedia({ ...media, packs: media.packs.filter((_: any, j: number) => j !== i) })}><Trash className="h-4 w-4" /></Button>
                    </div>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-xs text-muted">Credits, AED price for Stripe, and the one-time Dodo product id (Dodo charges the product's own price).</p>
            </div>
            <div className="flex justify-end"><Button loading={busy === "media"} onClick={() => save("media", media, "Media settings")}>Save media studio</Button></div>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <div className="space-y-6">
          <Card>
            <CardHeader icon={<Gift className="h-5 w-5" />} title="Give or remove media credits" subtitle="For schools, refunds and promotions. Every change is audit-logged." />
            <div className="space-y-3 p-5">
              <Field label="Teacher's email"><Input type="email" value={grant.email} onChange={(e) => setGrant({ ...grant, email: e.target.value })} /></Field>
              <div className="grid grid-cols-[7rem_1fr] gap-3">
                <Field label="Credits" hint="negative removes"><Input type="number" value={grant.amount} onChange={(e) => setGrant({ ...grant, amount: Number(e.target.value) })} /></Field>
                <Field label="Note"><Input value={grant.note} onChange={(e) => setGrant({ ...grant, note: e.target.value })} placeholder="e.g. Al Noor pilot" /></Field>
              </div>
              <div className="flex justify-end"><Button loading={busy === "grant"} disabled={!grant.email || !grant.amount} onClick={doGrant}>Update credits</Button></div>
            </div>
          </Card>
          <Card>
            <CardHeader icon={<Palette className="h-5 w-5" />} title="Default look" subtitle="Used by teachers who haven't picked a theme in Settings." />
            <div className="flex items-end gap-3 p-5">
              <Field label="Theme" className="flex-1">
                <Select value={skin} onChange={(e) => setSkin(e.target.value)}>
                  <option value="classic">Classic (indigo)</option>
                  <option value="forest">Forest (green)</option>
                </Select>
              </Field>
              <Button loading={busy === "ui"} onClick={() => save("ui", { default_skin: skin }, "Default theme")}>Save</Button>
            </div>
          </Card>
        </div>
        <Card>
          <CardHeader title="Recent media" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-muted"><tr><th className="px-5 py-2 font-medium">Teacher</th><th className="px-2 py-2 font-medium">Item</th><th className="px-2 py-2 font-medium">Model</th><th className="px-2 py-2 text-right font-medium">Credits</th><th className="px-5 py-2 font-medium">Status</th></tr></thead>
              <tbody className="divide-y divide-line">
                {data.recent.length ? data.recent.map((m: any) => (
                  <tr key={m.id}>
                    <td className="px-5 py-2.5"><div className="max-w-[12rem] truncate text-ink">{m.owner}</div><div className="text-xs text-muted">{formatDate(m.created_at)}</div></td>
                    <td className="px-2 py-2.5"><div className="max-w-[16rem] truncate text-ink-2">{m.prompt}</div><div className="text-xs text-muted">{m.kind}{m.seconds ? ` · ${m.seconds}s` : ""}</div></td>
                    <td className="px-2 py-2.5 text-xs text-muted">{m.model || "—"}</td>
                    <td className="px-2 py-2.5 text-right tabular-nums">{m.credits}</td>
                    <td className="px-5 py-2.5"><Badge tone={m.status === "ready" ? "success" : m.status === "failed" ? "danger" : "neutral"}>{m.status}</Badge></td>
                  </tr>
                )) : <tr><td colSpan={5} className="px-5 py-8 text-center text-muted">No media generated yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
