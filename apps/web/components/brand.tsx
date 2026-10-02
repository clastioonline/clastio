import Link from "next/link";
import { cn } from "@/lib/utils";

// Display windows into the supplied artwork; the original PNG is preserved unchanged.
export function LogoMark({ className }: { className?: string }) {
  return <svg viewBox="630 425 790 830" className={cn("h-9 w-9 shrink-0 rounded-lg bg-white", className)} role="img" aria-label="Clastio">
    <image href="/brand/clastio-original.png" width="2048" height="2048" />
  </svg>;
}

export function Wordmark({ className }: { className?: string }) {
  return <span className={cn("inline-block rounded bg-white", className)}>
    <svg viewBox="385 1280 1275 340" className="h-7 w-[105px]" role="img" aria-label="Clastio">
      <image href="/brand/clastio-original.png" width="2048" height="2048" />
    </svg>
  </span>;
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5", className)} aria-label="Clastio home">
      <LogoMark />
      <Wordmark />
    </Link>
  );
}
