"use client";

import { useEffect, useState } from "react";
import { PricingTable } from "@/components/pricing-table";
import { Modal } from "@/components/ui";
import { useApi } from "@/lib/hooks";

/* Opens whenever the API reports a plan limit (HTTP 402), so a limit is a path to upgrade, not a dead end. */
export function UpgradeDialog() {
  const [reason, setReason] = useState<string | null>(null);
  const { data: usage } = useApi<any>(reason ? "/me/usage" : null);
  useEffect(() => {
    const onLimit = (e: Event) => {
      const d = (e as CustomEvent).detail || {};
      // Media credits are bought as packs in the Media studio, not with a plan.
      if (d.details?.resource === "media_credits") return;
      setReason(d.message || "You've reached a limit of your current plan.");
    };
    window.addEventListener("pptg:limit", onLimit);
    return () => window.removeEventListener("pptg:limit", onLimit);
  }, []);
  return (
    <Modal open={!!reason} onClose={() => setReason(null)} title="Upgrade to keep going" size="xl">
      <p className="mb-6 text-ink-2">{reason} Choose a plan to unlock more lessons, slides and features. You can cancel any time.</p>
      <PricingTable mode="app" paidOnly compact currentPlan={usage?.plan?.code} onTrial={!!usage?.trial?.active} />
    </Modal>
  );
}
