import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";

// The signed-in app is private: keep it out of search engines.
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
