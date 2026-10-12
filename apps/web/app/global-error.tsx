"use client";

import { SystemStateLayout } from "@/components/system-state-layout";
import { systemPageForSlug } from "@/lib/system-pages";
import { THEME_BOOT_SCRIPT } from "@/lib/theme-boot";

export default function GlobalError({ error, retry, reset }: { error: Error & { digest?: string }; retry?: () => void; reset?: () => void }) {
  const page = systemPageForSlug("500")!;
  const recover = retry || reset || (() => window.location.reload());
  return <html lang="en" data-skin="forest"><head><title>We could not load Clastio | Clastio</title>
    <meta name="viewport" content="width=device-width,initial-scale=1" /><meta name="robots" content="noindex,nofollow" />
    <link rel="icon" href="/brand/favicon.png" /><script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} /></head><body style={{ margin: 0 }}>
    <SystemStateLayout {...page} reference={error.digest}
      actions={<button className="sys-action sys-primary" type="button" onClick={recover}>Try again</button>}
      primaryAction={undefined} secondaryAction={{ href: "/", label: "Go home" }} />
  </body></html>;
}
