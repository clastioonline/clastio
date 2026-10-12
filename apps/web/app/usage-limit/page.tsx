import type { Metadata } from "next";
import { Suspense } from "react";
import { BillingSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Usage and allowances", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Usage and allowances" description="Loading the current account status…" />}><BillingSystemPage kind="usage-limit" /></Suspense>;
}
