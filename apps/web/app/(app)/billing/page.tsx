"use client";
import { LicensePanel } from "@/components/license-panel";

import { CircleCheck, ExternalLink, ImagePlay, Sparkles, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DashHeader, Panel } from "@/components/dash";
import { LoadError } from "@/components/load-error";
import { ReferralPanel } from "@/components/referral-panel";
import { PricingTable } from "@/components/pricing-table";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Skeleton } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { quotaAvailable } from "@/lib/usage";

const fmt = (d?: string | null) => (d ? formatDate(d, { day: "numeric", month: "long", year: "numeric" }) : "");

function Meter({ label, used, limit, unit = "", available, reserved = 0, showAvailable = false }: { label: string; used: number; limit: number | null | undefined; unit?: string; available?: number | null; reserved?: number; showAvailable?: boolean }) {
  if (limit === undefined || limit === null) return null;
  const balance = quotaAvailable({ used, limit, available, reserved });
  const unlimited = limit === -1;
  const pct = unlimited || !limit ? 0 : Math.min(100, (used / limit) * 100);
  return (
    <div>
      <div className="flex justify-between text-sm"><span className="text-ink-2">{label}</span><span className="tabular-nums text-muted">{used}{unit} / {unlimited ? "Unlimited" : limit === 0 && !balance ? "Not included" : `${limit}${unit}`}</span></div>
      {!unlimited && limit > 0 && <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2"><div className={pct > 85 ? "h-full rounded-full bg-accent-500" : "h-full rounded-full bg-brand-600"} style={{ width: `${Math.max(2, pct)}%` }} /></div>}
      {showAvailable && <p className="mt-1.5 text-xs text-muted">{balance === null ? "Unlimited allowance" : `${balance} available`}{reserved > 0 && ` · ${reserved} reserved for queued work`}</p>}
    </div>
  );
}

function Billing() {
  const params = useSearchParams();
  const { notify } = useToast();
  const { user } = useMe();
  const justPaid = params.get("status") === "success";
  const [waiting, setWaiting] = useState(justPaid);
  const [startingTrial, setStartingTrial] = useState(false);
  const [cancellingCheckout, setCancellingCheckout] = useState(false);
  const { data, error, mutate } = useApi<any>("/billing/subscription", { refreshInterval: (current) => current?.pending_checkout || waiting ? 2000 : 0 });
  const { data: plans } = useApi<{ trial: { enabled: boolean; days: number } }>("/billing/plans");
  const sub = data?.subscription;
  const paid = sub && ["stripe", "dodo"].includes(sub.provider);
  const pending = data?.pending_checkout;
  const confirmed = paid && sub.status === "active" && data?.plan.code !== "free" && !pending;

  // After checkout the gateway confirms by webhook; poll briefly until the new plan shows up.
  useEffect(() => {
    if (!waiting) return;
    if (confirmed) { setWaiting(false); return; }
    const t = setTimeout(() => setWaiting(false), 45_000);
    return () => clearTimeout(t);
  }, [waiting, confirmed]);

  const startTrial = async () => {
    setStartingTrial(true);
    try {
      await api("/auth/trial", { method: "POST" });
      await mutate();
      notify({ tone: "success", title: "Your trial has started" });
    } catch (e) {
      notify({ tone: "error", title: "Couldn't start trial", body: errorMessage(e) });
    } finally { setStartingTrial(false); }
  };

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

  const cancelCheckout = async () => {
    if (!confirm("Close this unpaid checkout before choosing another plan?")) return;
    setCancellingCheckout(true);
    try {
      await api("/billing/checkout/cancel", { method: "POST" });
      await mutate();
      notify({ tone: "success", title: "Unpaid checkout closed" });
    } catch (e) {
      notify({ tone: "error", title: "Couldn't close checkout", body: errorMessage(e) });
    } finally { setCancellingCheckout(false); }
  };

  if (error) return <LoadError label="your plan and billing" retry={mutate} />;
  if (!data) return <Skeleton className="h-96 rounded-3xl" />;
  const trial = data.trial;
  const u = data.usage;

  let title = data.plan.name;
  let line = "";
  if (trial?.active) { title = `${data.plan.name} free trial`; line = `${trial.days_left} day${trial.days_left === 1 ? "" : "s"} left · ends ${fmt(trial.ends_at)}. No card on file, nothing is charged.`; }
  else if (paid && !confirmed) line = "Your payment subscription needs attention. Review payment status in the secure billing portal.";
  else if (paid) line = sub.cancel_at_period_end ? `Cancelled · access until ${fmt(sub.current_period_end)}` : `Billed ${sub.interval === "year" ? "yearly" : "monthly"} · renews ${fmt(sub.current_period_end)}`;
  else if (sub?.provider === "manual") line = `Provided by your school or Clastio${sub.current_period_end ? ` until ${fmt(sub.current_period_end)}` : ""}.`;
  else line = trial?.ended ? "Your free trial has ended. Upgrade any time to unlock full units and more credits." : "Free forever, with limited credits each month.";

  return (
    <div className="space-y-5">
      <DashHeader title="Plan & billing" subtitle="Prices in AED; taxes and discounts are confirmed at checkout. Upgrade, change or cancel any time." />
      {pending && <Panel title="Checkout in progress">
        <p className="text-sm text-muted">{pending.status === "processing" ? "Your payment is awaiting confirmation. Your current plan stays in place until payment is confirmed." : "You have an unfinished checkout. Resume it or wait for it to close before choosing a different plan, trial or license."}</p>
        <div className="mt-4 flex flex-wrap gap-3">
          {pending.url && <Button href={pending.url}>Resume checkout</Button>}
          {pending.provider === "stripe" && pending.status === "open" && <Button variant="outline" loading={cancellingCheckout} onClick={cancelCheckout}>Close unpaid checkout</Button>}
          <Button variant="ghost" href="/support">Contact support</Button>
        </div>
      </Panel>}
      {justPaid && (waiting ? (
        <div className="flex items-center gap-3 rounded-2xl bg-brand-50 px-4 py-3 text-sm text-ink-2"><Sparkles className="h-4 w-4 text-brand-600" />Waiting for secure payment confirmation… this usually takes a few seconds.</div>
      ) : confirmed ? (
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
        <Panel title={trial?.active ? "Your trial allowance" : "This month's usage"} className="xl:col-span-4">
          <div className="space-y-4">
            <Meter label="Credits" {...u.credits} showAvailable />
            <Meter label="AI images in slides" {...u.ai_images} showAvailable />
            <Meter label="WhatsApp messages" {...u.whatsapp_messages} showAvailable />
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
        {pending ? <p className="text-center text-sm text-muted">Complete or close your checkout above before starting another plan.</p> : paid ? <div className="space-y-3 text-center">
          <p className="text-sm text-muted">Your payment account already has a subscription. Change your plan or resolve a payment through the secure billing portal.</p>
          <Button onClick={portal}>Manage subscription</Button>
        </div> : sub?.provider === "manual" && data.plan.code !== "free" ? <div className="space-y-3 text-center">
          <p className="text-sm text-muted">Your school or Clastio provides your current plan. Contact support to change access without overlapping plans.</p>
          <Button href="/support">Contact support</Button>
        </div> : <PricingTable mode="app" currentPlan={data.plan.code} onTrial={!!trial?.active} />}
        {plans?.trial.enabled && data.trial_available !== false && data.plan.code === "free" && !trial?.ended && !trial?.active && !sub && !pending && (
          <div className="mt-6 text-center">
            <Button loading={startingTrial} disabled={!user?.email_verified} onClick={startTrial}>Start {plans.trial.days}-day free trial</Button>
            <p className="mt-2 text-sm text-muted">{user?.email_verified ? "No card needed. You return to Free when the trial ends." : "Verify your email to start your trial."}</p>
          </div>
        )}
      </section>

      {!sub && !pending ? <LicensePanel /> : <p id="license" className="scroll-mt-6 text-sm text-muted">You can redeem a license after your current plan ends and any outstanding subscription or checkout is closed. This prevents overlapping access or recurring charges.</p>}
      <ReferralPanel />

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
