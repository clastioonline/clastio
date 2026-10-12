import type { Metadata } from "next";
import { Suspense } from "react";
import { BillingSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Cancellation status", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Cancellation status" description="Loading the current account status…" />}><BillingSystemPage kind="subscription-cancelled" /></Suspense>;
}
