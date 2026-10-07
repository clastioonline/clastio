"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import { useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/* Dashboard building blocks: big rounded white cards on a soft panel, one filled "hero" KPI, pill charts
   with striped "not yet" bars, and a half-donut progress gauge. Used by the teacher and admin dashboards. */

export const STRIPES =
  "repeating-linear-gradient(135deg, var(--color-line-strong) 0 3px, transparent 3px 8px)";

export function DashHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-3xl font-bold tracking-tight text-ink sm:text-[2.6rem] sm:leading-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("min-w-0 rounded-3xl bg-surface p-5 sm:p-6", className)}>
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          {title && <h2 className="text-lg font-semibold text-ink sm:text-xl">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function KpiCard({ label, value, hint, trend, href, hero = false }: {
  label: string; value: ReactNode; hint?: ReactNode; trend?: number | null; href?: string; hero?: boolean;
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <span className={cn("text-base font-medium sm:text-lg", hero ? "text-white" : "text-ink")}>{label}</span>
        <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-full border transition-transform group-hover:rotate-45",
          hero ? "border-white bg-white text-brand-800" : "border-line-strong text-ink")}>
          <ArrowUpRight className="h-5 w-5" />
        </span>
      </div>
      <div className={cn("mt-4 text-3xl sm:text-5xl font-bold tracking-tight tabular-nums", hero ? "text-white" : "text-ink")}>{value}</div>
      {(hint || trend != null) && (
        <div className={cn("mt-4 flex items-center gap-2 text-sm", hero ? "text-accent-100" : "text-brand-600")}>
          {trend != null && (
            <span className={cn("inline-flex items-center gap-0.5 rounded-md border px-1.5 text-xs font-semibold",
              hero ? "border-accent-100/70" : "border-brand-300")}>{trend}<span aria-hidden>▴</span></span>
          )}
          {hint}
        </div>
      )}
    </>
  );
  const cls = cn("group block rounded-3xl p-3 sm:p-6 transition-shadow hover:shadow-[var(--shadow-pop)]",
    hero ? "ui-hero bg-brand-800 text-white" : "bg-surface");
  return href ? <Link href={href} className={cls}>{body}</Link> : <div className={cls}>{body}</div>;
}

export type PillPoint = { label: string; value: number; future?: boolean; highlight?: boolean; title?: string };

/* Pill columns. Days with activity are filled (the highlighted one darker, with its value on top);
   days with nothing yet, or still to come, are striped. Hover/focus shows the value; a table mirrors it. */
export function PillChart({ points, unit, height = 170 }: { points: PillPoint[]; unit: string; height?: number }) {
  const [active, setActive] = useState<number | null>(null);
  const max = Math.max(1, ...points.map((p) => p.value));
  return (
    <div>
      <div className="flex items-end justify-between gap-2 sm:gap-3" style={{ height: height + 44 }} role="img"
        aria-label={`${unit} per day: ${points.map((p) => `${p.label} ${p.value}`).join(", ")}`}>
        {points.map((p, i) => {
          const empty = p.future || p.value === 0;
          const h = empty ? height * 0.78 : Math.max(height * 0.3, (p.value / max) * height);
          const show = active === i || (active === null && p.highlight && !empty);
          return (
            <div key={i} className="relative flex min-w-0 flex-1 flex-col items-center gap-2">
              {show && (
                <span className="absolute z-10 whitespace-nowrap rounded-full border border-brand-300 bg-surface px-2 py-0.5 text-[11px] font-semibold text-brand-700 shadow-sm"
                  style={{ bottom: h + 34 }}>
                  {p.title || `${p.value} ${unit}`}
                </span>
              )}
              <button type="button" tabIndex={0} aria-label={`${p.label}: ${p.value} ${unit}`}
                onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(i)} onBlur={() => setActive(null)}
                className={cn("focus-ring w-full max-w-[64px] rounded-full transition-[height]",
                  empty ? "border border-line-strong" : p.highlight ? "bg-brand-800" : "bg-brand-500")}
                style={{ height: h, background: empty ? STRIPES : undefined }} />
              <span className={cn("text-sm", p.highlight ? "font-semibold text-ink" : "text-muted")}>{p.label}</span>
            </div>
          );
        })}
      </div>
      <table className="sr-only">
        <caption>{unit} per day</caption>
        <tbody>{points.map((p, i) => <tr key={i}><th>{p.label}</th><td>{p.value}</td></tr>)}</tbody>
      </table>
    </div>
  );
}

/* Half-donut gauge: filled segments in order, then a striped remainder. */
export function HalfDonut({ segments, total, center, caption }: {
  segments: { label: string; value: number; className: string }[]; total: number; center: ReactNode; caption: ReactNode;
}) {
  const r = 80;
  const len = Math.PI * r;
  let offset = 0;
  const safeTotal = Math.max(total, 1);
  return (
    <div className="relative mx-auto w-full max-w-[300px]">
      <svg viewBox="0 0 200 112" className="w-full" aria-hidden>
        <defs>
          <pattern id="donut-stripes" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="var(--color-surface)" />
            <rect width="2.5" height="6" fill="var(--color-line-strong)" />
          </pattern>
        </defs>
        <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="url(#donut-stripes)" strokeWidth="26" strokeLinecap="round" />
        {segments.map((s) => {
          const seg = (Math.min(s.value, safeTotal) / safeTotal) * len;
          const el = seg > 0 ? (
            <path key={s.label} d="M20 100 A80 80 0 0 1 180 100" fill="none" strokeWidth="26" strokeLinecap="round"
              className={s.className} stroke="currentColor" strokeDasharray={`${Math.max(seg - 2, 0.01)} ${len}`} strokeDashoffset={-offset} />
          ) : null;
          offset += seg;
          return el;
        })}
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="text-4xl font-bold tracking-tight text-ink tabular-nums">{center}</div>
        <div className="text-sm text-muted">{caption}</div>
      </div>
    </div>
  );
}

export function Legend({ items }: { items: { label: string; className?: string; striped?: boolean; value?: ReactNode }[] }) {
  return (
    <ul className="mt-5 flex flex-wrap justify-center gap-x-5 gap-y-2 text-sm text-ink-2">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2">
          <span className={cn("h-3.5 w-3.5 rounded-full", i.className)} style={i.striped ? { background: STRIPES, border: "1px solid var(--color-line-strong)" } : undefined} />
          {i.label}{i.value != null && <span className="font-semibold tabular-nums text-ink">{i.value}</span>}
        </li>
      ))}
    </ul>
  );
}

export function PillButton({ href, onClick, children, variant = "solid", disabled }: {
  href?: string; onClick?: () => void; children: ReactNode; variant?: "solid" | "outline"; disabled?: boolean;
}) {
  const cls = cn("focus-ring inline-flex h-12 items-center gap-2 rounded-full px-6 text-[15px] font-semibold transition disabled:opacity-60",
    variant === "solid" ? "ui-hero bg-brand-800 text-white hover:brightness-110" : "border-2 border-brand-700 text-brand-700 hover:bg-brand-50");
  return href ? <Link href={href} className={cls}>{children}</Link> : <button onClick={onClick} disabled={disabled} className={cls}>{children}</button>;
}
