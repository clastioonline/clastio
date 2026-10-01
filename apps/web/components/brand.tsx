import Link from "next/link";
import { cn } from "@/lib/utils";

/* Clastio mark: a slide on its stand with a spark of magic at the corner. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-9 w-9 shrink-0", className)} role="img" aria-label="Clastio">
      <rect width="64" height="64" rx="18" fill="#155c38" />
      <path d="M0 18A18 18 0 0 1 18 0h28a18 18 0 0 1 18 18v6C44 30 22 36 0 44z" fill="#23955c" />
      <rect x="12" y="19" width="32" height="23" rx="4.5" fill="#fff" />
      <rect x="17" y="24.5" width="14" height="3.4" rx="1.7" fill="#1b7446" />
      <rect x="17" y="31" width="21" height="2.6" rx="1.3" fill="#a8dcbc" />
      <rect x="17" y="35.8" width="15" height="2.6" rx="1.3" fill="#a8dcbc" />
      <path d="M28 42.5v5.5M22 50h12" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M48 8.5l2.7 6.6 6.6 2.7-6.6 2.7-2.7 6.6-2.7-6.6-6.6-2.7 6.6-2.7z" fill="#fbbf24" stroke="#0f3d26" strokeWidth="1.2" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("text-[19px] font-bold leading-none tracking-tight text-ink", className)}>
      PPT <span className="text-brand-600">Genie</span>
    </span>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5", className)} aria-label="Clastio home">
      <LogoMark />
      <Wordmark />
    </Link>
  );
}
