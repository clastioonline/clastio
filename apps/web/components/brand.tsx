import Link from "next/link";
import { cn } from "@/lib/utils";

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-8 w-8", className)} aria-hidden>
      <rect width="64" height="64" rx="16" fill="#4f46e5" />
      <path d="M16 20c6-3 11-3 16 1 5-4 10-4 16-1v24c-6-3-11-3-16 1-5-4-10-4-16-1z" fill="#fff" opacity=".95" />
      <path d="M32 21v24" stroke="#4f46e5" strokeWidth="2.5" />
      <path d="M47 10l2 5 5 2-5 2-2 5-2-5-5-2 5-2z" fill="#fbbf24" />
    </svg>
  );
}

export function Logo({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} className={cn("flex items-center gap-2.5 font-semibold tracking-tight text-ink", className)}>
      <LogoMark />
      <span className="text-[15px] leading-tight">
        AI Teacher
        <span className="block text-xs font-medium text-muted">Assistant</span>
      </span>
    </Link>
  );
}
