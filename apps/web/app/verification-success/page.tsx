import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Email verification status", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Email verification status" description="Loading the current account status…" />}><AccountSystemPage kind="verification-success" /></Suspense>;
}
