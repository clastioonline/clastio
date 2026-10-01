"use client";

import { ArrowRight, CheckCheck, CircleAlert, CircleCheck, Clock3, Layers, LoaderCircle, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import useSWR, { useSWRConfig } from "swr";
import { api, timeAgo } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { useToast } from "@/components/toast";
import { Button, Modal, Progress, Skeleton } from "@/components/ui";

export type Activity = {
  id: string; type: string; label: string; title: string; href: string;
  status: string; progress: number; stage: string | null; error: string | null;
  created_at: string; completed_at: string | null;
};
type Feed = { items: Activity[]; active_count: number };
const active = (item: Activity) => item.status === "queued" || item.status === "running";
const Context = createContext<{
  items: Activity[]; count: number; loading: boolean; error: unknown; open: () => void; refresh: () => void;
}>({ items: [], count: 0, loading: false, error: null, open: () => {}, refresh: () => {} });
export const useActivity = () => useContext(Context);

export function ActivityProvider({ children }: { children: ReactNode }) {
  const { user } = useMe();
  const { notify } = useToast();
  const { mutate: refreshCache } = useSWRConfig();
  const [opened, setOpened] = useState(false);
  const { data, error, isLoading, mutate } = useSWR<Feed>(user ? ["activity", user.id] : null, () => api("/activity"), {
    refreshInterval: (feed) => feed?.active_count ? 3000 : 15000,
    revalidateOnFocus: true, shouldRetryOnError: true,
  });
  const previous = useRef<{ user?: string; statuses: Map<string, string> }>({ statuses: new Map() });
  useEffect(() => {
    if (previous.current.user !== user?.id) {
      previous.current = { user: user?.id, statuses: new Map() };
      setOpened(false);
    }
    if (!user || !data) return;
    let changed = false;
    for (const item of data.items) {
      const old = previous.current.statuses.get(item.id);
      if ((old === "queued" || old === "running") && !active(item)) {
        changed = true;
        notify({ tone: item.status === "succeeded" ? "success" : "error",
          title: item.status === "succeeded" ? `${item.title} is ready` : `${item.title} needs attention`,
          body: "Open Activity to see the result." });
      }
    }
    previous.current.statuses = new Map(data.items.map((item) => [item.id, item.status]));
    if (changed) {
      void refreshCache((key) => typeof key === "string" && /^\/(lessons|documents|projects|templates|media|assistant|me\/notifications)/.test(key));
    }
  }, [data, user?.id, notify, refreshCache]);
  useEffect(() => {
    const refresh = () => { if (user) void mutate(); };
    window.addEventListener("clastio:work-started", refresh);
    return () => window.removeEventListener("clastio:work-started", refresh);
  }, [mutate, user?.id]);
  const open = useCallback(() => setOpened(true), []);
  return <Context.Provider value={{ items: user ? data?.items || [] : [], count: data?.active_count || 0,
    loading: isLoading, error, open, refresh: () => { void mutate(); } }}>
    {children}
    {user && <Modal open={opened} onClose={() => setOpened(false)} title="Your activity" size="lg"
      footer={<><Button variant="ghost" onClick={() => setOpened(false)}>Keep exploring</Button><Link href="/activity" onClick={() => setOpened(false)} className="focus-ring rounded-xl bg-brand-600 px-4 py-2 text-sm font-medium text-white">View all activity</Link></>}>
      <p className="mb-5 text-sm text-muted">Your work keeps going when you leave this page—even if you close the browser.</p>
      <ActivityList limit={8} onNavigate={() => setOpened(false)} />
    </Modal>}
  </Context.Provider>;
}

export function ActivityButton() {
  const { count, open } = useActivity();
  return <button onClick={open} aria-label={`Open activity${count ? `, ${count} in progress` : ""}`}
    className="focus-ring relative flex h-11 shrink-0 items-center gap-2 rounded-full bg-surface px-3 text-ink-2 hover:text-brand-700">
    {count ? <LoaderCircle className="h-5 w-5 animate-spin motion-reduce:animate-none" /> : <Layers className="h-5 w-5" />}
    <span className="hidden text-sm font-medium xl:block">Activity</span>
    {!!count && <span className="rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{count}</span>}
  </button>;
}

export function ActivityList({ filter = "all", limit = 100, onNavigate }: { filter?: string; limit?: number; onNavigate?: () => void }) {
  const { items, loading, error, refresh } = useActivity();
  if (loading) return <div className="space-y-3"><Skeleton className="h-24" /><Skeleton className="h-24" /></div>;
  if (error) return <div role="alert" className="rounded-2xl border border-line p-5 text-sm"><p>We couldn’t refresh your activity. Your submitted tasks continue on the server.</p><Button className="mt-3" variant="outline" onClick={refresh}><RefreshCw className="h-4 w-4" />Try again</Button></div>;
  const shown = items.filter((item) => filter === "all" || (filter === "working" ? active(item) : item.status === filter)).slice(0, limit);
  if (!shown.length) return <div className="rounded-2xl border border-dashed border-line-strong p-8 text-center">
    <CheckCheck className="mx-auto h-8 w-8 text-brand-600" /><h3 className="mt-3 font-semibold text-ink">{filter === "working" ? "Nothing waiting on you" : "A little room for your next idea"}</h3>
    <p className="mt-2 text-sm text-muted">Create lessons, prepare a worksheet, or ask your assistant. We’ll keep track of the work here.</p>
    <Link href="/projects/new" onClick={onNavigate} className="focus-ring mt-4 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-brand-700">Create lessons <ArrowRight className="h-4 w-4" /></Link>
  </div>;
  return <div className="space-y-3">{shown.map((item) => {
    const working = active(item), success = item.status === "succeeded", failed = item.status === "failed";
    const Icon = working ? item.status === "queued" ? Clock3 : LoaderCircle : success ? CircleCheck : CircleAlert;
    return <article key={item.id} className="rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-start gap-3">
        <span className={cn("grid h-10 w-10 shrink-0 place-items-center rounded-xl", working ? "bg-brand-50 text-brand-700" : success ? "bg-success-50 text-success-700" : "bg-warn-50 text-warn-700")}>
          <Icon className={cn("h-5 w-5", item.status === "running" && "animate-spin motion-reduce:animate-none")} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-muted">{item.label} · {timeAgo(item.created_at)}</p>
          <h3 className="mt-1 break-words font-semibold text-ink">{item.title}</h3>
          <p className="mt-1 text-sm text-muted">{working ? item.stage || "Waiting for a worker" : success ? "Ready when you are" : failed ? item.error : "Cancelled"}</p>
        </div>
      </div>
      {working && <div className="mt-4"><div className="mb-1.5 flex justify-between text-xs text-muted"><span>{item.status === "queued" ? "In the queue" : "In progress"}</span><span>{Math.min(100, Math.max(0, item.progress))}%</span></div><Progress value={item.progress} /></div>}
      <div className="mt-3 flex justify-end"><Link href={item.href} onClick={onNavigate} className="focus-ring inline-flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium text-brand-700">{success ? "Open result" : "View details"}<ArrowRight className="h-4 w-4" /></Link></div>
    </article>;
  })}</div>;
}

export function ActivityOverview() {
  const { count, items, error, open } = useActivity();
  const ready = items.filter((item) => item.status === "succeeded").length;
  return <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 to-brand-900 p-5 text-white sm:p-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-start gap-3"><Sparkles className="mt-1 h-6 w-6 shrink-0 text-accent-300" /><div>
        <p className="text-xs font-semibold uppercase tracking-widest text-white/70">Your teaching workspace</p>
        <h2 className="mt-1 text-xl font-semibold">{error ? "Your work has a home here" : count ? `${count} task${count === 1 ? " is" : "s are"} moving forward` : ready ? "Your next lesson starts a step ahead" : "A great lesson starts with an idea"}</h2>
        <p className="mt-2 max-w-xl text-sm text-white/80">{count ? "Keep planning or take a break. Your results will be waiting in Activity." : "Plan a unit, create a quiz, or explore an idea with your assistant."}</p>
      </div></div>
      <button onClick={open} className="focus-ring flex shrink-0 items-center gap-2 rounded-full bg-white px-5 py-3 text-sm font-semibold text-brand-800">{count ? "Follow progress" : "Open activity"}<ArrowRight className="h-4 w-4" /></button>
    </div>
    <div className="mt-5 flex flex-wrap gap-2 border-t border-white/20 pt-4">
      {[['/projects/new', 'Build a lesson'], ['/lessons?tab=documents', 'Create a worksheet'], ['/assistant', 'Explore an idea']].map(([href, label]) => <Link key={href} href={href} className="focus-ring rounded-full bg-white/10 px-3 py-2 text-xs font-medium transition hover:bg-white/20">{label} ↗</Link>)}
    </div>
  </section>;
}
