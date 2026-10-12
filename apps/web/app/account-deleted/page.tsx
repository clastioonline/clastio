import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Account closure status", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Account closure status" description="Loading the current account status…" />}><AccountSystemPage kind="account-deleted" /></Suspense>;
}
