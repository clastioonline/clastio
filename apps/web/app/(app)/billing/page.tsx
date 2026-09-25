"use client";

import { ExternalLink } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { PricingTable } from "@/components/pricing-table";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Progress, Skeleton } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";

function Usage({ label, used, limit, unit = "" }: { label: string; used: number; limit: number | null | undefined; unit?: string }) {
  if (limit === undefined || limit === null) return null;
  const unlimited = limit === -1;
  const pct = unlimited || !limit ? 0 : (used / limit) * 100;
  return (
    <div>
      <div className="flex justify-between text-sm"><span className="text-ink-2">{label}</span><span className="tabular-nums text-muted">{used}{unit} / {unlimited ? "∞" : `${limit}${unit}`}</span></div>
      {!unlimited && limit > 0 && <Progress value={pct} className="mt-1.5 h-1.5" tone={pct > 85 ? "accent" : "brand"} />}
    </div>
  );
}

function Billing() {
  const params = useSearchParams();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/billing/subscription");
  const { data: plans } = useApi<any>("/billing/plans");
  const [busy, setBusy] = useState<string | null>(null);

  const choose = async (plan: string, interval: "month" | "year") => {
    setBusy(plan);
    try {
      const r = await api<{ url: string }>("/billing/checkout", { body: { plan, interval } });
      window.location.href = r.url;
    } catch (e) {
      notify({ tone: "error", title: "Checkout unavailable", body: errorMessage(e) });
      setBusy(null);
    }
  };
  const portal = async () => {
    try {
      const r = await api<{ url: string }>("/billing/portal", { method: "POST" });
      window.location.href = r.url;
    } catch (e) {
      notify({ tone: "error", title: "Couldn't open billing portal", body: errorMessage(e) });
    }
  };
  const cancel = async () => {
    if (!confirm("Cancel at the end of this billing period? You keep access until then.")) return;
    try {
      await api("/billing/cancel", { method: "POST" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't cancel", body: errorMessage(e) });
    }
  };

  if (!data) return <Skeleton className="h-96" />;
  const sub = data.subscription;
  return (
    <div className="space-y-6">
      <PageHeader title="Plan & billing" subtitle="Prices in AED, plus 5% VAT. Change or cancel any time." />
      {params.get("status") === "success" && <Alert tone="success" title="Thank you!">Your subscription is being activated. It can take a few seconds.</Alert>}
      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title={data.plan.name} subtitle={sub ? `${sub.status}${sub.current_period_end ? ` · renews ${formatDate(sub.current_period_end, { day: "numeric", month: "short", year: "numeric" })}` : ""}` : "Free plan"}
            action={sub?.cancel_at_period_end ? <Badge tone="accent">Cancels at period end</Badge> : undefined} />
          <div className="space-y-4 p-5">
            <Usage label="Credits" used={data.usage.credits.used} limit={data.usage.credits.limit} />
            <Usage label="AI images" used={data.usage.ai_images.used} limit={data.usage.ai_images.limit} />
            <Usage label="WhatsApp messages" used={data.usage.whatsapp_messages.used} limit={data.usage.whatsapp_messages.limit} />
            <Usage label="Storage" used={data.usage.storage_mb.used} limit={data.usage.storage_mb.limit} unit=" MB" />
            {sub?.provider === "stripe" && (
              <div className="flex flex-wrap gap-2 pt-2">
                <Button variant="outline" size="sm" onClick={portal}><ExternalLink className="h-4 w-4" /> Manage payment</Button>
                {!sub.cancel_at_period_end && <Button variant="ghost" size="sm" onClick={cancel}>Cancel plan</Button>}
              </div>
            )}
            {sub?.provider === "manual" && <p className="text-xs text-muted">This plan was granted by your school or an administrator.</p>}
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Invoices" />
          <div className="p-5">
            {data.payments.length ? (
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted"><tr><th className="py-2 text-start">Date</th><th className="text-start">Amount</th><th className="text-start">VAT</th><th className="text-start">Status</th><th /></tr></thead>
                <tbody className="divide-y divide-line">
                  {data.payments.map((p: any, i: number) => (
                    <tr key={i}><td className="py-2">{formatDate(p.date)}</td><td>{p.currency} {p.amount.toFixed(2)}</td><td>{p.tax.toFixed(2)}</td><td><Badge tone="success">{p.status}</Badge></td>
                      <td className="text-end">{p.invoice_url && <a href={p.invoice_url} target="_blank" rel="noreferrer" className="text-brand-600 hover:underline">Invoice</a>}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="text-sm text-muted">No payments yet.</p>}
          </div>
        </Card>
      </div>
      {plans && !plans.online_payments && <Alert tone="neutral">Online payments aren't configured on this server yet (Stripe keys missing). Plans can be granted by an administrator.</Alert>}
      <PricingTable currentPlan={data.plan.code} onChoose={choose} busy={busy} />
    </div>
  );
}

export default function BillingPage() {
  return <Suspense><Billing /></Suspense>;
}
