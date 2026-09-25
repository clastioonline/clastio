"use client";

import { CircleCheck, ExternalLink, ImagePlay, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DashHeader, Panel } from "@/components/dash";
import { PricingTable } from "@/components/pricing-table";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Skeleton } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const fmt = (d?: string | null) => (d ? formatDate(d, { day: "numeric", month: "long", year: "numeric" }) : "");

function Meter({ label, used, limit, unit = "" }: { label: string; used: number; limit: number | null | undefined; unit?: string }) {
  if (limit === undefined || limit === null) return null;
  const unlimited = limit === -1;
  const pct = unlimited || !limit ? 0 : Math.min(100, (used / limit) * 100);
  return (
    <div>
      <div className="flex justify-between text-sm"><span className="text-ink-2">{label}</span><span className="tabular-nums text-muted">{used}{unit} / {unlimited ? "Unlimited" : limit === 0 ? "Not included" : `${limit}${unit}`}</span></div>
      {!unlimited && limit > 0 && <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2"><div className={pct > 85 ? "h-full rounded-full bg-accent-500" : "h-full rounded-full bg-brand-600"} style={{ width: `${Math.max(2, pct)}%` }} /></div>}
    </div>
  );
}

function Billing() {
  const params = useSearchParams();
  const { notify } = useToast();
  const justPaid = params.get("status") === "success";
  const [waiting, setWaiting] = useState(justPaid);
  const { data, mutate } = useApi<any>("/billing/subscription", { refreshInterval: waiting ? 2000 : 0 });
  const sub = data?.subscription;
  const paid = sub && ["stripe", "dodo"].includes(sub.provider);

  // After checkout the gateway confirms by webhook; poll briefly until the new plan shows up.
  useEffect(() => {
    if (!waiting) return;
    if (paid) { setWaiting(false); return; }
    const t = setTimeout(() => setWaiting(false), 45_000);
    return () => clearTimeout(t);
  }, [waiting, paid]);

  const portal = async () => {
    try {
      const r = await api<{ url: string }>("/billing/portal", { method: "POST" });
      window.location.href = r.url;
    } catch (e) {
      notify({ tone: "error", title: "Couldn't open payment settings", body: errorMessage(e) });
    }
  };
  const cancel = async () => {
    if (!confirm("Cancel at the end of this billing period? You keep full access until then.")) return;
    try {
      await api("/billing/cancel", { method: "POST" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't cancel", body: errorMessage(e) });
    }
  };

  if (!data) return <Skeleton className="h-96 rounded-3xl" />;
  const trial = data.trial;
  const u = data.usage;

  let title = data.plan.name;
  let line = "";
  if (trial?.active) { title = `${data.plan.name} free trial`; line = `${trial.days_left} day${trial.days_left === 1 ? "" : "s"} left · ends ${fmt(trial.ends_at)}. No card on file, nothing is charged.`; }
  else if (paid) line = sub.cancel_at_period_end ? `Cancelled · access until ${fmt(sub.current_period_end)}` : `Billed ${sub.interval === "year" ? "yearly" : "monthly"} · renews ${fmt(sub.current_period_end)}`;
  else if (sub?.provider === "manual") line = `Provided by your school or PPT Genie${sub.current_period_end ? ` until ${fmt(sub.current_period_end)}` : ""}.`;
  else line = trial?.ended ? "Your free trial has ended. Upgrade any time to unlock full units and more credits." : "Free forever, with limited credits each month.";

  return (
    <div className="space-y-5">
      <DashHeader title="Plan & billing" subtitle="Prices in AED plus 5% VAT. Upgrade, change or cancel any time." />
      {justPaid && (waiting ? (
        <div className="flex items-center gap-3 rounded-2xl bg-brand-50 px-4 py-3 text-sm text-ink-2"><Sparkles className="h-4 w-4 text-brand-600" />Payment received. Activating your plan… this usually takes a few seconds.</div>
      ) : paid ? (
        <div className="flex items-center gap-3 rounded-2xl bg-brand-50 px-4 py-3 text-sm text-ink-2"><CircleCheck className="h-4 w-4 text-brand-600" />You're on {data.plan.name}. Thank you!</div>
      ) : (
        <div className="flex items-center gap-3 rounded-2xl bg-accent-50 px-4 py-3 text-sm text-ink-2"><TriangleAlert className="h-4 w-4 text-accent-600" />We're still waiting for the payment confirmation. Refresh in a minute, or contact support if your plan doesn't change.</div>
      ))}
      {sub?.status === "past_due" && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-danger-50 px-4 py-3 text-sm text-ink-2">
          <span>Your last payment didn't go through. Update your payment method to keep your plan.</span>
          <Button size="sm" onClick={portal}>Update payment</Button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-12">
        <section className="ui-hero flex flex-col rounded-3xl bg-brand-800 p-6 text-white xl:col-span-5">
          <div className="text-sm text-white/75">{trial?.active ? "You're trying" : "Current plan"}</div>
          <div className="mt-1 text-3xl font-bold tracking-tight">{title}</div>
          <p className="mt-2 text-white/80">{line}</p>
          <div className="mt-auto flex flex-wrap gap-2 pt-6">
            {paid ? (
              <>
                <button onClick={portal} className="inline-flex h-11 items-center gap-2 rounded-full bg-white px-5 text-sm font-semibold text-brand-800 hover:bg-white/90"><ExternalLink className="h-4 w-4" />Manage payment & invoices</button>
                {!sub.cancel_at_period_end && <button onClick={cancel} className="inline-flex h-11 items-center rounded-full px-4 text-sm font-semibold text-white/85 hover:bg-white/10">Cancel plan</button>}
              </>
            ) : (
              <a href="#plans" className="inline-flex h-11 items-center rounded-full bg-white px-5 text-sm font-semibold text-brand-800 hover:bg-white/90">{trial?.active ? "Choose a plan" : "See plans"}</a>
            )}
          </div>
        </section>
        <Panel title="This month's usage" className="xl:col-span-4">
          <div className="space-y-4">
            <Meter label="Credits" used={u.credits.used} limit={u.credits.limit} />
            <Meter label="AI images in slides" used={u.ai_images.used} limit={u.ai_images.limit} />
            <Meter label="WhatsApp messages" used={u.whatsapp_messages.used} limit={u.whatsapp_messages.limit} />
            <Meter label="Storage" used={u.storage_mb.used} limit={u.storage_mb.limit} unit=" MB" />
          </div>
        </Panel>
        <Panel title="Media credits" className="flex flex-col xl:col-span-3">
          <p className="text-sm text-muted">Images and videos from the Media studio use media credits, bought as packs separately from your plan.</p>
          <div className="mt-auto pt-5"><Link href="/media" className="inline-flex h-11 items-center gap-2 rounded-full border-2 border-brand-700 px-5 text-sm font-semibold text-brand-700 hover:bg-brand-50"><ImagePlay className="h-4 w-4" />Open Media studio</Link></div>
        </Panel>
      </div>

      <section id="plans" className="scroll-mt-6 rounded-3xl bg-surface p-5 sm:p-8">
        <h2 className="mb-1 text-center text-2xl font-bold tracking-tight text-ink">{paid ? "Change plan" : "Choose your plan"}</h2>
        <p className="mb-6 text-center text-muted">All plans include your own slide design, worksheets, quizzes and homework.</p>
        <PricingTable mode="app" currentPlan={data.plan.code} onTrial={!!trial?.active} />
      </section>

      <Panel title="Payments">
        {data.payments.length ? (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted"><tr><th className="py-2 text-start font-medium">Date</th><th className="text-start font-medium">Amount</th><th className="text-start font-medium">VAT</th><th className="text-start font-medium">Status</th><th /></tr></thead>
            <tbody className="divide-y divide-line">
              {data.payments.map((p: any, i: number) => (
                <tr key={i}><td className="py-2.5">{formatDate(p.date)}</td><td>{p.currency} {p.amount.toFixed(2)}</td><td>{p.tax.toFixed(2)}</td><td><Badge tone="success">{p.status}</Badge></td>
                  <td className="text-end">{p.invoice_url && <a href={p.invoice_url} target="_blank" rel="noreferrer" className="font-semibold text-brand-600 hover:underline">Invoice</a>}</td></tr>
              ))}
            </tbody>
          </table>
        ) : <p className="text-sm text-muted">No payments yet.</p>}
      </Panel>
    </div>
  );
}

export default function BillingPage() {
  return <Suspense><Billing /></Suspense>;
}
