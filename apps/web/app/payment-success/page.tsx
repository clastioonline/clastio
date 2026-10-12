import type { Metadata } from "next";
import { Suspense } from "react";
import { BillingSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Payment confirmation", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Payment confirmation" description="Loading the current account status…" />}><BillingSystemPage kind="payment-success" /></Suspense>;
}
