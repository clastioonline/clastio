"use client";

import { Check, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Field, Input, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export type Plan = { code: string; name: string; price_monthly_aed: number; price_annual_aed: number; features: string[]; limits: Record<string, any> };
type PlansResponse = { items: Plan[]; vat_rate: number; online_payments: boolean; payment_provider: string | null; trial: { enabled: boolean; plan: string; days: number; credits: number } };

/* Starts checkout for a plan and sends the teacher to the payment page. */
export function useCheckout() {
  const { notify } = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const choose = async (plan: string, interval: "month" | "year", couponCode?: string) => {
    setBusy(plan);
    try {
      const r = await api<{ url: string }>("/billing/checkout", { body: { plan, interval, coupon_code: couponCode?.trim() || undefined } });
      window.location.href = r.url;
    } catch (e) {
      notify({ tone: "error", title: "Checkout isn't available right now", body: errorMessage(e) });
      setBusy(null);
    }
  };
  return { choose, busy };
}

/**
 * Plan cards. `mode="public"` (pricing page) links to sign-up; `mode="app"` starts checkout for signed-in teachers.
 * `paidOnly` hides the Free plan (upgrade dialog).
 */
export function PricingTable({ mode = "app", currentPlan, onTrial = false, paidOnly = false, compact = false }: {
  mode?: "public" | "app"; currentPlan?: string; onTrial?: boolean; paidOnly?: boolean; compact?: boolean;
}) {
  const { data } = useApi<PlansResponse>("/billing/plans");
  const [interval, setInterval] = useState<"month" | "year">("month");
  const { choose, busy } = useCheckout();
  const [couponCode, setCouponCode] = useState("");
  const plans = (data?.items || []).filter((p) => !paidOnly || p.code !== "free");
  const trial = data?.trial;
  const canPay = mode === "public" || !!data?.online_payments;

  return (
    <div>
      <div className="mb-6 flex flex-col items-center gap-3">
        <Tabs tabs={[{ value: "month", label: "Monthly" }, { value: "year", label: "Yearly · 2 months free" }]} value={interval} onChange={setInterval} />
        {mode === "public" && trial?.enabled && (
          <p className="flex items-center gap-1.5 text-sm text-ink-2"><Sparkles className="h-4 w-4 text-accent-500" />
            Every new account starts with a {trial.days}-day free trial of {data?.items.find((p) => p.code === trial.plan)?.name || "a paid plan"}, with {trial.credits} trial credits. No card needed.</p>
        )}
      </div>
      {mode === "app" && <div className="mx-auto mb-6 max-w-sm"><Field label="Have a coupon code?" hint="Your discount and final total are confirmed on the secure payment page."><Input value={couponCode} maxLength={100} onChange={(e) => setCouponCode(e.target.value)} placeholder="Enter coupon code" autoComplete="off" /></Field></div>}
      <div className={cn("grid gap-5", paidOnly ? "md:grid-cols-3" : "md:grid-cols-2 xl:grid-cols-4")}>
        {plans.map((p) => {
          const popular = p.code === "pro";
          const monthly = interval === "year" ? p.price_annual_aed / 12 : p.price_monthly_aed;
          const current = currentPlan === p.code && !onTrial;
          return (
            <div key={p.code} className={cn("relative flex flex-col rounded-3xl p-6",
              popular ? "ui-hero bg-brand-800 text-white" : "bg-surface ring-1 ring-line")}>
              {popular && <span className="absolute -top-3 start-6 rounded-full bg-accent-400 px-3 py-1 text-xs font-bold text-[#141414]">Most popular</span>}
              <h3 className={cn("text-lg font-semibold", popular ? "text-white" : "text-ink")}>{p.name}</h3>
              <div className="mt-3 flex items-baseline gap-1">
                <span className={cn("text-4xl font-bold tracking-tight", popular ? "text-white" : "text-ink")}>{p.price_monthly_aed ? `AED ${Math.round(monthly)}` : "Free"}</span>
                {p.price_monthly_aed > 0 && <span className={cn("text-sm", popular ? "text-white/70" : "text-muted")}>/month</span>}
              </div>
              <p className={cn("mt-1 text-xs", popular ? "text-white/70" : "text-muted")}>
                {p.price_monthly_aed ? (interval === "year" ? `AED ${p.price_annual_aed} billed yearly · ` : "") + "+5% VAT" : "For trying things out"}
              </p>
              {!compact && (
                <ul className="mt-5 flex-1 space-y-2.5 text-sm">
                  <li className={cn("flex gap-2 font-medium", popular ? "text-white" : "text-ink")}>
                    <Check className={cn("mt-0.5 h-4 w-4 shrink-0", popular ? "text-accent-400" : "text-brand-600")} />
                    {p.limits.credits} credits a month · up to {p.limits.max_lectures} lessons per unit
                  </li>
                  {p.features.map((f) => (
                    <li key={f} className={cn("flex gap-2", popular ? "text-white/85" : "text-ink-2")}>
                      <Check className={cn("mt-0.5 h-4 w-4 shrink-0", popular ? "text-accent-400" : "text-brand-600")} />{f}
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-6">
                {mode === "public" ? (
                  <Link href="/signup" className={cn("flex h-12 items-center justify-center rounded-full font-semibold",
                    popular ? "bg-white text-brand-800 hover:bg-white/90" : "bg-[#141414] text-white hover:bg-black")}>
                    {p.code === "free" ? "Start free" : trial?.enabled ? "Start free trial" : `Get ${p.name}`}
                  </Link>
                ) : p.code === "free" ? (
                  <p className="flex h-12 items-center justify-center rounded-full bg-surface-2 text-sm font-medium text-muted">
                    {currentPlan === "free" ? "Your plan" : "Where you land after a trial"}
                  </p>
                ) : (
                  <button disabled={current || !canPay || busy !== null} onClick={() => choose(p.code, interval, couponCode)}
                    className={cn("flex h-12 w-full items-center justify-center rounded-full font-semibold transition disabled:cursor-not-allowed disabled:opacity-60",
                      popular ? "bg-white text-brand-800 hover:bg-white/90" : "bg-brand-800 text-white hover:brightness-110")}>
                    {busy === p.code ? "Opening checkout…" : current ? "Your plan" : onTrial && currentPlan === p.code ? "Keep this plan" : "Upgrade"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {mode === "app" && data && !data.online_payments && (
        <p className="mt-4 text-center text-sm text-muted">Online payment is being set up. Please check back soon, or contact support to upgrade.</p>
      )}
    </div>
  );
}
