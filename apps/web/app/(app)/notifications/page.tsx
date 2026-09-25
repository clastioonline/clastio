"use client";

import { CheckCheck, Settings2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LoadMore, useCursorList } from "@/components/admin-kit";
import { DashHeader } from "@/components/dash";
import { NOTICE_STYLE, NoticeIcon, type Notice } from "@/components/notification-center";
import { Button, Chips, EmptyState } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { cn } from "@/lib/utils";
import { Bell } from "lucide-react";

export default function NotificationsPage() {
  const router = useRouter();
  const [unreadOnly, setUnreadOnly] = useState("all");
  const list = useCursorList<Notice>(`/me/notifications?limit=30${unreadOnly === "unread" ? "&unread=true" : ""}`);
  const [removed, setRemoved] = useState<string[]>([]);
  const [readIds, setReadIds] = useState<string[]>([]);
  const items = list.items.filter((n) => !removed.includes(n.id)).map((n) => (readIds.includes(n.id) ? { ...n, read: true } : n));
  const unread = list.extra?.unread ?? 0;

  const open = async (n: Notice) => {
    if (!n.read) { await api("/me/notifications/read", { body: { ids: [n.id] } }).catch(() => {}); setReadIds((x) => [...x, n.id]); }
    if (n.link) router.push(n.link);
  };
  const remove = async (n: Notice) => {
    await api(`/me/notifications/${n.id}`, { method: "DELETE" }).catch(() => {});
    setRemoved((x) => [...x, n.id]);
  };
  const readAll = async () => { await api("/me/notifications/read", { body: { all: true } }); list.reload(); };

  return (
    <div className="space-y-6">
      <DashHeader title="Notifications" subtitle="Reminders about your plan and payments, finished lessons, support replies and security alerts."
        actions={<>
          <Button variant="outline" href="/settings#notifications"><Settings2 className="h-4 w-4" /> Preferences</Button>
          {unread > 0 && <Button onClick={readAll}><CheckCheck className="h-4 w-4" /> Mark all read</Button>}
        </>} />
      <section className="rounded-3xl bg-surface p-5 sm:p-6">
        <div className="mb-4">
          <Chips options={[{ value: "all", label: "All" }, { value: "unread", label: `Unread${unread ? ` (${unread})` : ""}` }]} value={unreadOnly} onChange={setUnreadOnly} />
        </div>
        {!items.length && !list.loading ? (
          <EmptyState icon={<Bell className="h-6 w-6" />} title="Nothing here" description="We'll let you know when a lesson is ready, a payment needs attention or support replies." />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((n) => (
              <li key={n.id} className={cn("group flex items-start gap-3 py-3", !n.read && "")}>
                <NoticeIcon type={n.type} />
                <button onClick={() => open(n)} className="min-w-0 flex-1 text-start">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className={cn("text-sm text-ink", !n.read && "font-semibold")}>{n.title}</span>
                    <span className="text-[11px] text-muted">{(NOTICE_STYLE[n.type] || NOTICE_STYLE.system).label} · {timeAgo(n.created_at)}</span>
                  </span>
                  {n.body && <span className="mt-0.5 block text-sm text-muted">{n.body}</span>}
                </button>
                {!n.read && <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-brand-600" aria-label="Unread" />}
                <button onClick={() => remove(n)} aria-label="Delete notification" className="rounded-lg p-1.5 text-muted opacity-0 hover:bg-surface-2 hover:text-ink focus:opacity-100 group-hover:opacity-100">
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <LoadMore list={list} />
      </section>
      <p className="text-center text-xs text-muted">Security, failed-payment and policy notices are always sent. Everything else can be changed in <Link href="/settings#notifications" className="underline">Settings</Link>.</p>
    </div>
  );
}
