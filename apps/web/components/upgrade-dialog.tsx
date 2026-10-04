"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PricingTable } from "@/components/pricing-table";
import { Modal } from "@/components/ui";
import { useApi } from "@/lib/hooks";

/* Opens whenever the API reports a plan limit (HTTP 402), so a limit is a path to upgrade, not a dead end. */
export function UpgradeDialog() {
  const [reason, setReason] = useState<string | null>(null);
  const { data: usage } = useApi<any>(reason ? "/billing/subscription" : null);
  const existingPlan = usage?.pending_checkout || (usage?.subscription && (['stripe', 'dodo'].includes(usage.subscription.provider) || (usage.subscription.provider === 'manual' && usage.plan.code !== 'free')));
  useEffect(() => {
    const onLimit = (e: Event) => {
      const d = (e as CustomEvent).detail || {};
      // Media credits are bought as packs in the Media studio, not with a plan.
      if (d.details?.resource === "media_credits") return;
      setReason(d.message || "You've reached a limit of your current plan.");
    };
    window.addEventListener("clastio:limit", onLimit);
    return () => window.removeEventListener("clastio:limit", onLimit);
  }, []);
  return (
    <Modal open={!!reason} onClose={() => setReason(null)} title="Upgrade to keep going" size="xl">
      <p className="mb-6 text-ink-2">{reason} Choose a plan to unlock more lessons, slides and features. You can cancel any time.</p>
      {existingPlan ? <Link href="/billing" onClick={() => setReason(null)} className="focus-ring inline-flex rounded-full bg-brand-800 px-5 py-3 font-semibold text-white">Manage plan and billing</Link>
        : usage ? <PricingTable mode="app" paidOnly compact currentPlan={usage.plan.code} onTrial={!!usage.trial?.active} />
        : <Link href="/billing" onClick={() => setReason(null)} className="focus-ring inline-flex rounded-full bg-brand-800 px-5 py-3 font-semibold text-white">View plan and billing</Link>}
    </Modal>
  );
}
