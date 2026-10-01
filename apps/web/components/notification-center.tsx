"use client";

import {
  AlertTriangle,
  Bell,
  CheckCheck,
  CreditCard,
  FileCheck2,
  LifeBuoy,
  Megaphone,
  Scale,
  ShieldCheck,
  Sparkles,
  UserCog,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api, timeAgo } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

export type Notice = { id: string; type: string; title: string; body: string; link: string | null; read: boolean; created_at: string };

export const NOTICE_STYLE: Record<string, { icon: any; className: string; label: string }> = {
  security: { icon: ShieldCheck, className: "bg-danger-50 text-danger-700", label: "Security" },
  billing: { icon: CreditCard, className: "bg-brand-50 text-brand-700", label: "Billing" },
  billing_alert: { icon: AlertTriangle, className: "bg-warn-50 text-warn-600", label: "Payment issue" },
  usage: { icon: Sparkles, className: "bg-accent-50 text-accent-600", label: "Usage" },
  product: { icon: FileCheck2, className: "bg-success-50 text-success-700", label: "Your work" },
  support: { icon: LifeBuoy, className: "bg-brand-50 text-brand-700", label: "Support" },
  account: { icon: LifeBuoy, className: "bg-brand-50 text-brand-700", label: "Account" },
  announcement: { icon: Megaphone, className: "bg-accent-50 text-accent-600", label: "News" },
  legal: { icon: Scale, className: "bg-surface-2 text-ink-2", label: "Policies" },
  staff: { icon: UserCog, className: "bg-warn-50 text-warn-600", label: "Staff alert" },
  system: { icon: Bell, className: "bg-surface-2 text-ink-2", label: "System" },
};

export function NoticeIcon({ type }: { type: string }) {
  const s = NOTICE_STYLE[type] || NOTICE_STYLE.system;
  const Icon = s.icon;
  return <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-full", s.className)}><Icon className="h-4 w-4" /></span>;
}

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { data, mutate } = useApi<{ items: Notice[]; unread: number }>("/me/notifications?limit=8", { refreshInterval: 30_000 });
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", close); document.removeEventListener("keydown", esc); };
  }, []);
  const unread = data?.unread || 0;
  const openItem = async (n: Notice) => {
    setOpen(false);
    if (!n.read) { await api("/me/notifications/read", { body: { ids: [n.id] } }).catch(() => {}); mutate(); }
    if (n.link) router.push(n.link);
  };
  const readAll = async () => { await api("/me/notifications/read", { body: { all: true } }); mutate(); };
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"} aria-expanded={open}
        className="focus-ring relative grid h-11 w-11 place-items-center rounded-full bg-surface text-ink-2 hover:text-ink">
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -end-0.5 -top-0.5 grid h-5 min-w-5 place-items-center rounded-full bg-accent-500 px-1 text-[11px] font-bold text-ink">
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute end-0 top-13 z-50 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-2xl border border-line bg-surface shadow-[var(--shadow-pop)]" role="dialog" aria-label="Notifications">
          <div className="flex items-center justify-between border-b border-line px-4 py-3">
            <span className="font-semibold text-ink">Notifications</span>
            {unread > 0 && <button onClick={readAll} className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:underline"><CheckCheck className="h-4 w-4" /> Mark all read</button>}
          </div>
          <div className="max-h-[26rem] overflow-y-auto p-2">
            {data?.items?.length ? data.items.map((n) => (
              <button key={n.id} onClick={() => openItem(n)} className={cn("flex w-full items-start gap-3 rounded-xl px-2.5 py-2.5 text-start hover:bg-surface-2", !n.read && "bg-brand-50/50")}>
                <NoticeIcon type={n.type} />
                <span className="min-w-0 flex-1">
                  <span className={cn("block text-sm text-ink", !n.read && "font-semibold")}>{n.title}</span>
                  {n.body && <span className="mt-0.5 line-clamp-2 block text-xs text-muted">{n.body}</span>}
                  <span className="mt-1 block text-[11px] text-muted">{timeAgo(n.created_at)}</span>
                </span>
                {!n.read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand-600" aria-label="Unread" />}
              </button>
            )) : <div className="px-3 py-8 text-center text-sm text-muted">You're all caught up.</div>}
          </div>
          <Link href="/notifications" onClick={() => setOpen(false)} className="block border-t border-line px-4 py-3 text-center text-sm font-medium text-brand-600 hover:bg-surface-2">
            See all notifications
          </Link>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ banners above every page */

function useDismissed(key: string) {
  const [dismissed, setDismissed] = useState<string[]>([]);
  useEffect(() => {
    try { setDismissed(JSON.parse(localStorage.getItem(key) || "[]")); } catch { /* storage unavailable */ }
  }, [key]);
  const dismiss = (id: string) => {
    const next = [...dismissed, id];
    setDismissed(next);
    try { localStorage.setItem(key, JSON.stringify(next.slice(-50))); } catch { /* ignore */ }
  };
  return { dismissed, dismiss };
}

export function AnnouncementBanners() {
  const { data } = useApi<{ items: any[] }>("/announcements", { refreshInterval: 300_000 });
  const { dismissed, dismiss } = useDismissed("clastio:dismissed-announcements");
  const items = (data?.items || []).filter((a) => !dismissed.includes(a.id));
  if (!items.length) return null;
  return (
    <div className="mb-6 space-y-2">
      {items.map((a) => (
        <div key={a.id} role="status" className={cn("flex items-start gap-3 rounded-2xl px-4 py-3 text-sm",
          a.kind === "maintenance" || a.kind === "important" ? "bg-warn-50 text-warn-600" : "bg-brand-50 text-brand-700")}>
          <Megaphone className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="min-w-0 flex-1">
            <span className="font-semibold">{a.title}</span>{a.body && <span className="text-ink-2"> — {a.body}</span>}
            {a.link && <Link href={a.link} className="ms-2 font-medium underline">Learn more</Link>}
          </div>
          <button onClick={() => dismiss(a.id)} aria-label="Dismiss announcement" className="text-muted hover:text-ink"><X className="h-4 w-4" /></button>
        </div>
      ))}
    </div>
  );
}

export function VerifyEmailBanner({ email }: { email: string }) {
  const [state, setState] = useState<"idle" | "sent" | "error">("idle");
  const resend = async () => {
    try { await api("/auth/resend-verification", { method: "POST" }); setState("sent"); } catch { setState("error"); }
  };
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-accent-50 px-4 py-3 text-sm text-ink-2">
      <span>Please confirm your email address. We sent a link to <b>{email}</b>.</span>
      {state === "sent" ? <span className="font-medium text-success-700">Sent — check your inbox.</span> :
        <button onClick={resend} className="rounded-full bg-brand-800 px-4 py-2 font-semibold text-white hover:brightness-110">
          {state === "error" ? "Try again later" : "Resend link"}
        </button>}
    </div>
  );
}

export function MaintenanceBanner() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    const on = (e: Event) => setMsg((e as CustomEvent).detail?.message || "Clastio is down for maintenance.");
    window.addEventListener("clastio:maintenance", on);
    return () => window.removeEventListener("clastio:maintenance", on);
  }, []);
  if (!msg) return null;
  return <div role="alert" className="mb-6 rounded-2xl bg-warn-50 px-4 py-3 text-sm font-medium text-warn-600">{msg} Your work is saved; please try again shortly.</div>;
}
