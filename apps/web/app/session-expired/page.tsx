import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Sign-in status", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Sign-in status" description="Loading the current account status…" />}><AccountSystemPage kind="session-expired" /></Suspense>;
}
