"use client";

import { Alert, Button } from "@/components/ui";
export function LoadError({ retry, label = "this content" }: { retry: () => unknown; label?: string }) {
  return <Alert tone="danger"><div className="flex flex-wrap items-center justify-between gap-3"><p>We couldn’t load {label}. Check your connection and try again.</p><Button size="sm" variant="outline" onClick={() => { void retry(); }}>Try again</Button></div></Alert>;
}
