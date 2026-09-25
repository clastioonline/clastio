"use client";

import { Check } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Tabs } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export type Plan = { code: string; name: string; price_monthly_aed: number; price_annual_aed: number; features: string[]; limits: Record<string, any> };

export function PricingTable({ currentPlan, onChoose, busy }: { currentPlan?: string; onChoose?: (plan: string, interval: "month" | "year") => void; busy?: string | null }) {
  const { data } = useApi<{ items: Plan[]; vat_rate: number }>("/billing/plans");
  const [interval, setInterval] = useState<"month" | "year">("month");
  const plans = data?.items || [];
  return (
    <div>
      <div className="mb-6 flex items-center justify-center gap-3">
        <Tabs tabs={[{ value: "month", label: "Monthly" }, { value: "year", label: "Annual · 2 months free" }]} value={interval} onChange={setInterval} />
      </div>
      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {plans.map((p) => {
          const highlight = p.code === "assistant";
          const price = interval === "year" ? p.price_annual_aed : p.price_monthly_aed;
          const current = currentPlan === p.code;
          return (
            <div key={p.code} className={cn("relative flex flex-col rounded-2xl border bg-surface p-6 shadow-[var(--shadow-card)]",
              highlight ? "border-brand-500 ring-2 ring-brand-500/20" : "border-line")}>
              {highlight && <Badge tone="brand" className="absolute -top-3 start-6 bg-brand-600 text-white">Most complete</Badge>}
              <h3 className="font-semibold text-ink">{p.name}</h3>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-3xl font-semibold tracking-tight text-ink">{price ? `AED ${price}` : "Free"}</span>
                {price > 0 && <span className="text-sm text-muted">/{interval === "year" ? "year" : "month"}</span>}
              </div>
              {price > 0 && <p className="mt-1 text-xs text-muted">+5% VAT · {p.limits.credits} credits / month</p>}
              <ul className="mt-5 flex-1 space-y-2.5 text-sm">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2 text-ink-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-success-500" />{f}</li>
                ))}
              </ul>
              <div className="mt-6">
                {onChoose ? (
                  <Button className="w-full" variant={highlight ? "primary" : "outline"} disabled={current || p.code === "free"}
                    loading={busy === p.code} onClick={() => onChoose(p.code, interval)}>
                    {current ? "Current plan" : p.code === "free" ? "Included" : `Choose ${p.name}`}
                  </Button>
                ) : (
                  <Button className="w-full" variant={highlight ? "primary" : "outline"} href="/signup">
                    {p.code === "free" ? "Start free" : "Start with a free trial"}
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p className="mt-6 text-center text-sm text-muted">
        Schools and departments: per-seat annual pricing with shared templates, SSO and invoicing. Contact us for a quote.
      </p>
    </div>
  );
}
