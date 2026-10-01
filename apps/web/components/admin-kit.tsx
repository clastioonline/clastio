"use client";

import { Download, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { DashHeader } from "@/components/dash";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Field, Modal, Spinner, Textarea } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { useCan, useMe } from "@/lib/hooks";
import { cn } from "@/lib/utils";

/* Building blocks for the admin console. Every page is gated by a permission here for a clean UI, and the API
   checks the same permission again on the server. */

export function AdminPage({ title, subtitle, perm, actions, children }: {
  title: string; subtitle?: ReactNode; perm: string | string[]; actions?: ReactNode; children: ReactNode;
}) {
  const { user } = useMe();
  const can = useCan();
  const perms = Array.isArray(perm) ? perm : [perm];
  if (!user) return <Spinner />;
  if (!can(...perms)) {
    return (
      <div className="space-y-6">
        <DashHeader title={title} />
        <Alert tone="warn" title="Not available for your role">
          This page needs the {perms.join(", ")} permission. Ask a super admin if you need access.
        </Alert>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <DashHeader title={title} subtitle={subtitle} actions={actions} />
      {children}
    </div>
  );
}

/** Newest-first list with "Load more" (keyset pagination on the server). */
export function useCursorList<T = any>(path: string | null) {
  const [items, setItems] = useState<T[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [extra, setExtra] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async (reset: boolean, from: string | null) => {
    if (!path) return;
    setLoading(true);
    setError(null);
    try {
      const sep = path.includes("?") ? "&" : "?";
      const data = await api<any>(`${path}${!reset && from ? `${sep}cursor=${encodeURIComponent(from)}` : ""}`);
      setItems((xs) => (reset ? data.items : [...xs, ...data.items]));
      setCursor(data.next_cursor || null);
      const { items: _i, next_cursor: _n, ...rest } = data;
      setExtra(rest);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => { setItems([]); setCursor(null); load(true, null); }, [load]);
  return { items, extra, loading, error, hasMore: !!cursor, loadMore: () => load(false, cursor), reload: () => load(true, null) };
}

export type Column<T> = { key: string; label: ReactNode; render?: (row: T) => ReactNode; className?: string };

export function DataTable<T extends Record<string, any>>({ columns, rows, onRowClick, empty = "Nothing here yet.", rowKey = "id" }: {
  columns: Column<T>[]; rows: T[]; onRowClick?: (row: T) => void; empty?: ReactNode; rowKey?: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs uppercase tracking-wide text-muted">
          <tr>{columns.map((c) => <th key={c.key} scope="col" className={cn("px-3 py-3 text-start font-medium", c.className)}>{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} className={cn(onRowClick && "cursor-pointer hover:bg-surface-2")} onClick={onRowClick ? () => onRowClick(r) : undefined}
              tabIndex={onRowClick ? 0 : undefined} onKeyDown={onRowClick ? (e) => e.key === "Enter" && onRowClick(r) : undefined}>
              {columns.map((c) => <td key={c.key} className={cn("px-3 py-3 align-top", c.className)}>{c.render ? c.render(r) : String(r[c.key] ?? "—")}</td>)}
            </tr>
          ))}
          {!rows.length && <tr><td colSpan={columns.length} className="px-3 py-10 text-center text-muted">{empty}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export function LoadMore({ list }: { list: { hasMore: boolean; loading: boolean; loadMore: () => void; error: string | null } }) {
  return (
    <div className="mt-4 flex items-center justify-center gap-3">
      {list.error && <span className="text-sm text-danger-700">{list.error}</span>}
      {list.loading ? <Spinner /> : list.hasMore ? <Button variant="outline" onClick={list.loadMore}>Load more</Button> : null}
    </div>
  );
}

export function FilterBar({ children }: { children: ReactNode }) {
  return <div className="mb-4 flex flex-wrap items-end gap-3">{children}</div>;
}

const TONES: Record<string, "success" | "danger" | "warn" | "neutral" | "brand" | "accent"> = {
  active: "success", processed: "success", paid: "success", sent: "success", succeeded: "success", resolved: "success",
  published: "success", operational: "success", logged: "neutral", closed: "neutral", archived: "neutral", ignored: "neutral",
  draft: "accent", pending: "accent", trialing: "accent", queued: "accent", open: "brand", running: "brand", planned: "brand",
  info: "neutral", warning: "warn", past_due: "warn", pending_deletion: "warn", suspended: "warn", degraded: "warn",
  received: "accent", failed: "danger", critical: "danger", banned: "danger", canceled: "neutral", deleted: "neutral",
  refunded: "neutral", declined: "neutral", urgent: "danger", high: "warn", low: "neutral", normal: "neutral",
};

export function StatusPill({ value }: { value?: string | null }) {
  if (!value) return <span className="text-muted">—</span>;
  return <Badge tone={TONES[value] || "neutral"}>{value.replace(/_/g, " ")}</Badge>;
}

export function When({ at }: { at?: string | null }) {
  if (!at) return <span className="text-muted">—</span>;
  return <time dateTime={at} title={new Date(at).toLocaleString()} className="whitespace-nowrap text-muted">{timeAgo(at)}</time>;
}

export function JsonBlock({ value }: { value: unknown }) {
  if (value == null || (typeof value === "object" && !Object.keys(value as object).length)) return <span className="text-muted">—</span>;
  return <pre className="max-h-60 overflow-auto rounded-xl bg-surface-2 p-3 text-xs leading-relaxed text-ink-2">{JSON.stringify(value, null, 2)}</pre>;
}

export function Mono({ children }: { children: ReactNode }) {
  return <code className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-ink-2">{children}</code>;
}

/** Destructive or sensitive actions: say what will happen and require a reason that goes into the audit log. */
export function ReasonDialog({ open, title, description, confirmLabel, danger, onClose, onConfirm, requireReason = true, children }: {
  open: boolean; title: string; description?: ReactNode; confirmLabel: string; danger?: boolean; requireReason?: boolean;
  onClose: () => void; onConfirm: (reason: string) => Promise<void>; children?: ReactNode;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const { notify } = useToast();
  useEffect(() => { if (open) setReason(""); }, [open]);
  const ok = !requireReason || reason.trim().length >= 3;
  const go = async () => {
    setBusy(true);
    try {
      await onConfirm(reason.trim());
      onClose();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't complete that", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title={title}
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant={danger ? "danger" : "primary"} disabled={!ok} loading={busy} onClick={go}>{confirmLabel}</Button></>}>
      <div className="space-y-4 text-sm">
        {description && (danger ? <Alert tone="danger">{description}</Alert> : <p className="text-ink-2">{description}</p>)}
        {children}
        {requireReason && (
          <Field label="Reason (saved in the audit log)" hint="At least 3 characters. Other staff will see this.">
            <Textarea value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} autoFocus />
          </Field>
        )}
      </div>
    </Modal>
  );
}

export function ExportButton({ dataset, days = 30 }: { dataset: string; days?: number }) {
  const can = useCan();
  const { notify } = useToast();
  if (!can("data.export")) return null;
  const go = async (format: "csv" | "json") => {
    const res = await fetch(`/api/v1/admin/export/${dataset}?format=${format}&days=${days}`, { credentials: "include" });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      notify({ tone: "error", title: "Export failed", body: body?.error?.message });
      return;
    }
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `clastioenie-${dataset}.${format}`;
    a.click();
    notify({ tone: "info", title: "Export downloaded", body: "Exports are recorded in the audit log." });
  };
  return (
    <div className="flex gap-2">
      <Button variant="outline" size="sm" onClick={() => go("csv")}><Download className="h-4 w-4" /> CSV</Button>
      <Button variant="outline" size="sm" onClick={() => go("json")}>JSON</Button>
    </div>
  );
}

export function PrivacyNote({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2 text-xs text-muted">
      <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" /><span>{children}</span>
    </div>
  );
}
