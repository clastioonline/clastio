import Link from "next/link";
import { cn } from "@/lib/utils";

/* Clastio mark: a slide on its stand with a spark of magic at the corner. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("h-9 w-9 shrink-0", className)} role="img" aria-label="Clastio">
      <g strokeWidth="2" strokeLinejoin="round">
        {/* Bottom/Shadow Layer (Dark Blue) */}
        <path d="M12,38 L32,50 L52,38 L52,42 L32,54 L12,42 Z" fill="#20225d" stroke="#20225d" />
        <path d="M12,30 L32,42 L52,30 L52,34 L32,46 L12,34 Z" fill="#36399b" stroke="#36399b" />
        
        {/* Middle Layer (Royal Blue) */}
        <path d="M16,24 L32,34 L48,24 L32,14 Z" fill="#4d53df" stroke="#4d53df" />
        <path d="M16,24 L32,34 L48,24 L48,28 L32,38 L16,28 Z" fill="#3c41bc" stroke="#3c41bc" />
        <path d="M48,30 L32,40 L16,30 L16,34 L32,44 L48,34 Z" fill="#4d53df" stroke="#4d53df" />
        
        {/* Top Layer (Teal/Green) */}
        <path d="M12,18 L28,28 L44,18 L28,8 Z" fill="#14b88b" stroke="#14b88b" />
        <path d="M12,18 L28,28 L44,18 L44,22 L28,32 L12,22 Z" fill="#0d946d" stroke="#0d946d" />
      </g>
    </svg>
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn("text-[19px] font-bold leading-none tracking-tight text-ink", className)}>
      Clastio
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
