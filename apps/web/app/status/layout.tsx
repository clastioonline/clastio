import { pageMetadata } from "@/lib/seo";

export const metadata = pageMetadata("Clastio system status", "Check the current Clastio app, API, AI generation and lesson building queue status.", "/status");

export default function StatusLayout({ children }: { children: React.ReactNode }) {
  return children;
}
