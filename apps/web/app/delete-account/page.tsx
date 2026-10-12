import type { Metadata } from "next";
import { Suspense } from "react";
import { DeleteAccountPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Request account deletion", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Request account deletion" description="Loading the current account status…" />}><DeleteAccountPage /></Suspense>;
}
