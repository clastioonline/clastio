"use client";

import { useMemo, useState } from "react";

/* Single-series charts (one validated hue, --color-chart-1): the card title names the series, so no legend box.
   Marks: columns <= 24px with a 4px rounded data-end, 2px lines, hairline solid gridlines, per-mark hover/focus
   tooltips, and a table view so no value is gated behind hover. */

export function compact(n: number, currency?: string) {
  const f = new Intl.NumberFormat(undefined, { notation: Math.abs(n) >= 10000 ? "compact" : "standard", maximumFractionDigits: Math.abs(n) < 10 && n % 1 ? 2 : 1 });
  return (currency ? `${currency} ` : "") + f.format(n);
}

function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) || raw;
  const out = [];
  for (let v = 0; v <= max + step * 0.001; v += step) out.push(Number(v.toFixed(6)));
  if (out[out.length - 1] < max) out.push(Number((out[out.length - 1] + step).toFixed(6)));
  return out;
}

type Point = { date: string; value: number };

function fillDays(points: Point[], days: number): Point[] {
  const map = new Map(points.map((p) => [p.date, p.value]));
  const out: Point[] = [];
  const today = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    out.push({ date: key, value: map.get(key) || 0 });
  }
  return out;
}

const fmtDay = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" });

export function ColumnChart({ points, days = 30, format = (v: number) => compact(v), height = 180, label }: {
  points: Point[]; days?: number; format?: (v: number) => string; height?: number; label: string;
}) {
  const data = useMemo(() => fillDays(points, days), [points, days]);
  const [hover, setHover] = useState<number | null>(null);
  const [table, setTable] = useState(false);
  const W = 640, H = height, padL = 40, padB = 22, padT = 10;
  const max = Math.max(...data.map((d) => d.value), 0);
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const band = (W - padL) / data.length;
  const bw = Math.min(24, band - 2);
  const y = (v: number) => padT + (H - padT - padB) * (1 - v / top);
  const total = data.reduce((a, d) => a + d.value, 0);
  const h = hover !== null ? data[hover] : null;

  return (
    <div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${label}: ${format(total)} over ${days} days`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={W} y1={y(t)} y2={y(t)} stroke="var(--color-chart-grid)" strokeWidth={1} />
              <text x={padL - 6} y={y(t)} dy="0.32em" textAnchor="end" fontSize="10" fill="var(--color-muted)">{format(t)}</text>
            </g>
          ))}
          {data.map((d, i) => {
            const x = padL + i * band + (band - bw) / 2;
            const yy = y(d.value);
            const hgt = H - padB - yy;
            const r = Math.min(4, hgt / 2, bw / 2);
            const path = d.value > 0
              ? `M${x},${H - padB} V${yy + r} Q${x},${yy} ${x + r},${yy} H${x + bw - r} Q${x + bw},${yy} ${x + bw},${yy + r} V${H - padB} Z`
              : "";
            return (
              <g key={d.date} tabIndex={0} role="img" aria-label={`${fmtDay(d.date)}: ${format(d.value)}`}
                onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                className="outline-none">
                <rect x={padL + i * band} y={padT} width={band} height={H - padT - padB} fill="transparent" />
                {path && <path d={path} fill="var(--color-chart-1)" opacity={hover === null || hover === i ? 1 : 0.55} />}
              </g>
            );
          })}
          <line x1={padL} x2={W} y1={H - padB} y2={H - padB} stroke="var(--color-line-strong)" strokeWidth={1} />
          {[0, Math.floor(data.length / 2), data.length - 1].map((i) => (
            <text key={i} x={padL + i * band + band / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="var(--color-muted)">{fmtDay(data[i].date)}</text>
          ))}
        </svg>
        {h && hover !== null && (
          <div className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs shadow-[var(--shadow-pop)]"
            style={{ left: `${((padL + hover * band + band / 2) / W) * 100}%` }}>
            <div className="font-semibold text-ink tabular-nums">{format(h.value)}</div>
            <div className="text-muted">{fmtDay(h.date)}</div>
          </div>
        )}
      </div>
      <button className="mt-1 text-xs text-muted underline-offset-2 hover:text-ink hover:underline" onClick={() => setTable(!table)}>
        {table ? "Hide table" : "View as table"}
      </button>
      {table && (
        <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-line">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-surface-2 text-muted"><tr><th className="px-3 py-1.5 text-start">Date</th><th className="px-3 py-1.5 text-end">{label}</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data.filter((d) => d.value).map((d) => <tr key={d.date}><td className="px-3 py-1">{fmtDay(d.date)}</td><td className="px-3 py-1 text-end tabular-nums">{format(d.value)}</td></tr>)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function BarList({ items, format = (v: number) => compact(v), empty = "No data yet" }: {
  items: { name: string; value: number; hint?: string }[]; format?: (v: number) => string; empty?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  if (!items.length) return <p className="text-sm text-muted">{empty}</p>;
  const max = Math.max(...items.map((i) => i.value)) || 1;
  return (
    <ul className="space-y-2.5">
      {items.map((it, i) => (
        <li key={it.name} tabIndex={0} onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
          className="focus-ring rounded-lg" title={it.hint ? `${it.name}: ${format(it.value)} (${it.hint})` : `${it.name}: ${format(it.value)}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate text-ink-2">{it.name}</span>
            <span className="shrink-0 font-medium text-ink tabular-nums">{format(it.value)}</span>
          </div>
          <div className="h-2.5 w-full rounded-e-[4px]">
            <div className="h-full rounded-e-[4px] transition-opacity" style={{ width: `${Math.max(2, (it.value / max) * 100)}%`, background: "var(--color-chart-1)", opacity: hover === null || hover === i ? 1 : 0.55 }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
