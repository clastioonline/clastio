import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Account availability", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Account availability" description="Loading the current account status…" />}><AccountSystemPage kind="account-deactivated" /></Suspense>;
}
