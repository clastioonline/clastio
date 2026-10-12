"use client";

import { SystemStateLayout } from "@/components/system-state-layout";
import { systemPageForSlug } from "@/lib/system-pages";

export default function ErrorPage({ error, retry, reset }: { error: Error & { digest?: string }; retry?: () => void; reset?: () => void }) {
  const page = systemPageForSlug("500")!;
  const recover = retry || reset || (() => window.location.reload());
  return <><title>We could not load this page | Clastio</title><meta name="robots" content="noindex,nofollow" />
    <SystemStateLayout {...page} reference={error.digest}
      actions={<button className="sys-action sys-primary" type="button" onClick={recover}>Try again</button>}
      primaryAction={undefined} secondaryAction={{ href: "/", label: "Go home" }} />
  </>;
}
