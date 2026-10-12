import type { Metadata } from "next";
import { Suspense } from "react";
import { ConsentSystemPage } from "@/components/account-system-pages";
import { SystemStateLayout } from "@/components/system-state-layout";

export const metadata: Metadata = { title: "Email preferences", robots: { index: false, follow: false } };

export default function Page() {
  return <Suspense fallback={<SystemStateLayout title="Email preferences" description="Loading the current account status…" />}><ConsentSystemPage kind="email-unsubscribe" /></Suspense>;
}
