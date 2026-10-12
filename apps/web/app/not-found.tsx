import { SystemStateLayout } from "@/components/system-state-layout";
import { systemPageForSlug } from "@/lib/system-pages";

export default function NotFound() {
  const page = systemPageForSlug("404")!;
  return <><title>Page not found | Clastio</title><meta name="robots" content="noindex,nofollow" /><SystemStateLayout {...page} /></>;
}
