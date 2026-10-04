"use client";

import {
  Activity,
  Bell,
  Bot,
  Brain,
  CalendarDays,
  ChartColumn,
  CircleHelp,
  FileText,
  Gauge,
  KeyRound,
  LifeBuoy,
  Megaphone,
  ScrollText,
  ServerCog,
  SlidersHorizontal,
  CreditCard,
  FolderKanban,
  GraduationCap,
  ImagePlay,
  Languages,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageCircle,
  NotebookPen,
  Palette,
  Search,
  Settings,
  ShieldCheck,
  Users,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AppWalkthrough } from "@/components/app-walkthrough";
import { ActivityButton } from "@/components/activity-center";
import { Logo } from "@/components/brand";
import { LoadError } from "@/components/load-error";
import { LegalGate } from "@/components/legal-gate";
import { AnnouncementBanners, MaintenanceBanner, NotificationBell, VerifyEmailBanner } from "@/components/notification-center";
import { Spinner } from "@/components/ui";
import { UpgradeDialog } from "@/components/upgrade-dialog";
import { api, ApiError } from "@/lib/api";
import { useApi, useCan, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { adminLandingPath } from "@/lib/navigation";
import { quotaAvailable } from "@/lib/usage";
import { cn } from "@/lib/utils";

type Item = { href: string; key: string; label: string; icon: any; badge?: string | number | null };

const MENU: Item[] = [
  { href: "/dashboard", key: "nav.today", label: "Dashboard", icon: LayoutDashboard },
  { href: "/projects", key: "nav.projects", label: "Lessons & PPTs", icon: FolderKanban },
  { href: "/assistant", key: "nav.assistant", label: "Assistant", icon: Bot },
  { href: "/lessons", key: "nav.lessons", label: "Library", icon: NotebookPen },
  { href: "/calendar", key: "nav.calendar", label: "Calendar", icon: CalendarDays },
  { href: "/curriculum", key: "nav.curriculum", label: "Classes", icon: GraduationCap },
  { href: "/templates", key: "nav.templates", label: "My designs", icon: Palette },
  { href: "/media", key: "nav.media", label: "Media studio", icon: ImagePlay },
  { href: "/teacher-memory", key: "nav.memory", label: "Teacher memory", icon: Brain },
  { href: "/whatsapp", key: "nav.whatsapp", label: "WhatsApp", icon: MessageCircle },
];
const GENERAL: Item[] = [
  { href: "/activity", key: "nav.activity", label: "Activity", icon: Activity },
  { href: "/notifications", key: "nav.notifications", label: "Notifications", icon: Bell },
  { href: "/support", key: "nav.support", label: "Help & support", icon: LifeBuoy },
  { href: "/tutorials", key: "nav.tutorials", label: "Tutorials & help", icon: CircleHelp },
  { href: "/billing", key: "nav.billing", label: "Plan & billing", icon: CreditCard },
  { href: "/settings", key: "nav.settings", label: "Settings", icon: Settings },
];
type AdminItem = Item & { perm?: string };
/* The admin console, grouped as operators think about it. Each item shows only for roles with its permission;
   the API enforces the same permission on every request. */
const ADMIN_GROUPS: { title: string; items: AdminItem[] }[] = [
  { title: "Overview", items: [
    { href: "/admin", key: "", label: "Dashboard", icon: ShieldCheck, perm: "analytics.view" },
  ] },
  { title: "Users", items: [
    { href: "/admin/users", key: "", label: "Teachers", icon: Users, perm: "users.view" },
    { href: "/admin/staff", key: "", label: "Staff & roles", icon: KeyRound, perm: "users.view" },
  ] },
  { title: "Billing", items: [
    { href: "/admin/billing", key: "", label: "Subscriptions & payments", icon: Wallet, perm: "billing.view" },
    { href: "/admin/plans", key: "", label: "Plans & trial", icon: CreditCard, perm: "billing.view" },
    { href: "/admin/media", key: "", label: "Media packs", icon: ImagePlay, perm: "billing.view" },
  ] },
  { title: "Usage", items: [
    { href: "/admin/api-usage", key: "", label: "API usage", icon: Gauge, perm: "api_usage.view" },
    { href: "/admin/ai-costs", key: "", label: "AI costs", icon: ChartColumn, perm: "api_usage.view" },
  ] },
  { title: "Support", items: [
    { href: "/admin/support", key: "", label: "Tickets & requests", icon: LifeBuoy, perm: "support.manage" },
    { href: "/admin/announcements", key: "", label: "Announcements", icon: Megaphone, perm: "announcements.manage" },
  ] },
  { title: "Security", items: [
    { href: "/admin/security", key: "", label: "Security events", icon: Activity, perm: "security.view" },
    { href: "/admin/audit", key: "", label: "Audit log", icon: ScrollText, perm: "audit.view" },
  ] },
  { title: "System", items: [
    { href: "/admin/system", key: "", label: "Health & logs", icon: ServerCog, perm: "system.logs.view" },
    { href: "/admin/settings", key: "", label: "Settings & flags", icon: SlidersHorizontal, perm: "settings.modify" },
    { href: "/admin/legal", key: "", label: "Legal documents", icon: FileText, perm: "legal.manage" },
  ] },
];
/* Pages an admin may open outside /admin. Everything else is the teacher product. */
const ADMIN_ALLOWED = ["/settings", "/notifications", "/activity"];

function NavLink({ item, active, label }: { item: Item; active: boolean; label: string }) {
  const Icon = item.icon;
  return (
    <Link href={item.href} aria-current={active ? "page" : undefined}
      className={cn("focus-ring group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[15px] transition-colors",
        active
          ? "font-semibold text-ink before:absolute before:-start-4 before:top-1.5 before:bottom-1.5 before:w-1.5 before:rounded-e-full before:bg-brand-600"
          : "text-muted hover:bg-surface hover:text-ink")}>
      <Icon className={cn("h-5 w-5 shrink-0", active ? "text-brand-600" : "text-muted group-hover:text-brand-600")} />
      <span className="truncate">{label}</span>
      {item.badge ? <span className="ms-auto rounded-md bg-brand-700 px-1.5 py-0.5 text-[11px] font-semibold text-white dark:text-ink">{item.badge}</span> : null}
    </Link>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-2 px-3 text-xs font-medium uppercase tracking-wider text-muted">{title}</div>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

/* The dark card at the bottom of the sidebar: plan, trial and credits, with the next step. */
function PlanCard() {
  const { data } = useApi<any>("/me/usage", { refreshInterval: 30_000 });
  if (!data) return null;
  const c = data.usage.credits;
  const available = quotaAvailable(c);
  const pct = c.limit && c.limit > 0 ? Math.min(100, (c.used / c.limit) * 100) : 0;
  const trial = data.trial?.active ? data.trial : null;
  return (
    <div className="ui-hero relative overflow-hidden rounded-2xl bg-brand-800 p-4 text-white">
      <div className="text-xs text-white/70">{trial ? "Free trial" : "Your plan"}</div>
      <div className="mt-0.5 font-semibold">{data.plan.name}{trial && <span className="font-normal text-white/80"> · {trial.days_left} day{trial.days_left === 1 ? "" : "s"} left</span>}</div>
      {c.limit > 0 && (
        <>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/20"><div className="h-full rounded-full bg-accent-400" style={{ width: `${Math.max(3, pct)}%` }} /></div>
          <div className="mt-1.5 text-[11px] text-white/70">{c.used} / {c.limit} credits this month</div>
        </>
      )}
      <div className="mt-2 text-xs text-white/90">{available === null ? "Unlimited credits" : `${available} credits available`}{c.reserved > 0 && <span className="block text-white/70">{c.reserved} reserved for queued work</span>}</div>
      <Link href="/billing" className="mt-3 block rounded-full bg-white/95 py-2 text-center text-sm font-semibold text-brand-800 hover:bg-white">
        {trial ? "Choose a plan" : data.plan.code === "free" ? "Upgrade" : "Manage plan"}
      </Link>
    </div>
  );
}

/* Trial and plan messages at the top of every teacher page. */
function PlanBanner() {
  const { data } = useApi<any>("/me/usage", { refreshInterval: 60_000 });
  const pathname = usePathname();
  if (!data || pathname === "/billing") return null;
  const t = data.trial;
  const available = quotaAvailable(data.usage.credits);
  if (t?.active) {
    return (
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-accent-50 px-4 py-3 text-sm text-ink-2">
        <span>Your {data.plan.name} trial ends in <b>{t.days_left} day{t.days_left === 1 ? "" : "s"}</b>. <b>{available === null ? "Unlimited credits" : `${available} credits left`}</b> in your trial. No card on file; nothing is charged.</span>
        <Link href="/billing" className="rounded-full bg-brand-800 px-4 py-2 font-semibold text-white hover:brightness-110">Choose a plan</Link>
      </div>
    );
  }
  if (t?.ended) {
    return (
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-brand-50 px-4 py-3 text-sm text-ink-2">
        <span>Your free trial has ended and you're on the Free plan. Your lessons and designs are safe. Upgrade to keep building full units.</span>
        <Link href="/billing" className="rounded-full bg-brand-800 px-4 py-2 font-semibold text-white hover:brightness-110">See plans</Link>
      </div>
    );
  }
  return null;
}

/* Admin global search: people, payments, tickets, jobs and request ids from one box. */
function AdminSearch() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLFormElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const term = q.trim();
  const { data } = useApi<any>(term.length >= 2 ? `/admin/search?q=${encodeURIComponent(term)}` : null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); inputRef.current?.focus(); }
    };
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", close);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("mousedown", close); };
  }, []);
  const go = (href: string) => { setOpen(false); setQ(""); router.push(href); };
  const results = data ? [
    ...data.users.map((u: any) => ({ key: u.id, label: u.email, hint: `${u.name || "user"} · ${u.status}`, href: `/admin/users/${u.id}` })),
    ...data.tickets.map((t: any) => ({ key: t.id, label: `#${t.number} ${t.subject}`, hint: `ticket · ${t.status}`, href: `/admin/support/${t.id}` })),
    ...data.payments.map((p: any) => ({ key: p.id, label: `${p.currency} ${p.amount} · ${p.provider_ref}`, hint: `payment · ${p.status}`, href: `/admin/billing?ref=${encodeURIComponent(p.provider_ref)}` })),
    ...data.jobs.map((j: any) => ({ key: j.id, label: `${j.type} job`, hint: j.status, href: `/admin/system?job=${j.id}` })),
    ...(data.request ? [{ key: data.request, label: data.request, hint: "request trace", href: `/admin/system?trace=${data.request}` }] : []),
  ] : [];
  return (
    <form ref={ref} className="relative hidden max-w-md flex-1 sm:block" role="search"
      onSubmit={(e) => { e.preventDefault(); if (results[0]) go(results[0].href); else if (term.startsWith("req_")) go(`/admin/system?trace=${term}`); else go(`/admin/users?q=${encodeURIComponent(term)}`); }}>
      <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
      <input ref={inputRef} value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
        placeholder="Search email, name, payment, ticket #, req_…" aria-label="Search the admin console"
        className="h-12 w-full rounded-full bg-surface ps-12 pe-16 text-sm text-ink outline-none placeholder:text-muted focus:ring-2 focus:ring-brand-200" />
      <kbd className="absolute end-3 top-1/2 -translate-y-1/2 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">⌘ K</kbd>
      {open && term.length >= 2 && (
        <div className="absolute inset-x-0 top-14 z-50 rounded-2xl border border-line bg-surface p-2 shadow-[var(--shadow-pop)]">
          {results.length ? results.slice(0, 10).map((r) => (
            <button type="button" key={r.key} onClick={() => go(r.href)} className="block w-full rounded-xl px-3 py-2 text-start hover:bg-surface-2">
              <span className="block truncate text-sm text-ink">{r.label}</span><span className="block text-xs text-muted">{r.hint}</span>
            </button>
          )) : <div className="px-3 py-3 text-sm text-muted">{data ? "No matches." : "Searching…"}</div>}
        </div>
      )}
    </form>
  );
}

function TopBar({ user, onMenu }: { user: any; onMenu: () => void }) {
  const admin = user.role === "admin";
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const { locale, setLocale } = useI18n();
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <header className="flex items-center gap-3 rounded-3xl bg-panel p-3 sm:px-4">
      <button className="grid h-11 w-11 place-items-center rounded-full bg-surface text-ink lg:hidden" onClick={onMenu} aria-label="Open menu">
        <Menu className="h-5 w-5" />
      </button>
      {admin ? <AdminSearch /> : (
        <form className="relative hidden max-w-md flex-1 sm:block" role="search"
          onSubmit={(e) => { e.preventDefault(); router.push(`/lessons${q ? `?q=${encodeURIComponent(q)}` : ""}`); }}>
          <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
          <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search lessons and documents" aria-label="Search lessons and documents"
            className="h-12 w-full rounded-full bg-surface ps-12 pe-16 text-sm text-ink outline-none placeholder:text-muted focus:ring-2 focus:ring-brand-200" />
          <kbd className="absolute end-3 top-1/2 -translate-y-1/2 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">⌘ K</kbd>
        </form>
      )}
      <div className="shrink-0 lg:hidden"><Logo href={admin ? adminLandingPath(user.permissions) : "/dashboard"} className="[&>span]:hidden sm:[&>span]:inline" /></div>
      <div className="ms-auto flex items-center gap-2">
        <button onClick={() => setLocale(locale === "ar" ? "en" : "ar")} aria-label="Switch language" title={locale === "ar" ? "English" : "العربية"}
          className="focus-ring hidden h-11 w-11 place-items-center rounded-full bg-surface text-ink-2 hover:text-ink sm:grid">
          <Languages className="h-5 w-5" />
        </button>
        {!admin && (
          <Link href="/whatsapp" aria-label="WhatsApp" className="focus-ring hidden h-11 w-11 place-items-center rounded-full bg-surface text-ink-2 hover:text-ink sm:grid">
            <MessageCircle className="h-5 w-5" />
          </Link>
        )}
        <AppWalkthrough user={user} />
        <ActivityButton />
        <NotificationBell />
        <Link href="/settings" className="focus-ring flex items-center gap-3 rounded-full py-1 pe-2 ps-1 hover:bg-surface">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-base font-semibold text-white">
            {(user.name || user.email).slice(0, 1).toUpperCase()}
          </span>
          <span className="hidden min-w-0 md:block">
            <span className="block max-w-[11rem] truncate text-sm font-semibold text-ink">{user.name || (admin ? "Admin" : "Teacher")}</span>
            <span className="block max-w-[11rem] truncate text-xs text-muted">{admin ? user.admin_role_label || "Staff" : user.email}</span>
          </span>
        </Link>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, error, isLoading, mutate } = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const can = useCan();
  const { data: sysHealth } = useApi<any>(user?.role === "admin" && can("system.logs.view") ? "/admin/system/health" : null, { refreshInterval: 120_000 });

  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [error, pathname, router]);
  const admin = user?.role === "admin";
  useEffect(() => {
    if (!user) return;
    if (admin) {
      // Admins run the platform; the teacher product is not theirs to use or pay for.
      if ((!pathname.startsWith("/admin") && !ADMIN_ALLOWED.includes(pathname)) || (pathname === "/admin" && !user.permissions.includes("analytics.view"))) {
        const first = ADMIN_GROUPS.flatMap((g) => g.items).find((i) => !i.perm || user.permissions?.includes(i.perm));
        router.replace(first?.href || "/settings");
      }
    } else if (pathname.startsWith("/admin")) {
      router.replace("/dashboard");
    } else if (!user.onboarding_completed && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [user, admin, pathname, router]);
  useEffect(() => setOpen(false), [pathname]);

  if (error && !(error instanceof ApiError && error.status === 401)) {
    return <main className="mx-auto max-w-3xl p-6"><LoadError label="your account" retry={mutate} /></main>;
  }
  if (isLoading || !user) {
    return <div className="grid min-h-screen place-items-center"><Spinner className="h-7 w-7" /></div>;
  }

  const isActive = (href: string) => pathname === href || (!["/dashboard", "/admin"].includes(href) && pathname.startsWith(href + "/"));
  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    window.location.href = "/login";
  };

  const sidebar = (
    <div className="flex h-full flex-col gap-5 overflow-hidden p-4">
      <div className="flex items-center justify-between px-2 pt-2">
        <Logo href={user.role === "admin" ? adminLandingPath(user.permissions) : "/dashboard"} />
        <button className="rounded-full p-2 text-muted hover:bg-surface lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
      </div>
      <nav className="-mx-4 flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4" aria-label="Main">
        {admin ? ADMIN_GROUPS.map((g) => {
          const items = g.items.filter((i) => !i.perm || can(i.perm));
          return items.length ? <Section key={g.title} title={g.title}>{items.map((i) => <NavLink key={i.href} item={i} label={i.label} active={isActive(i.href)} />)}</Section> : null;
        }) : (
          <Section title="Menu">{MENU.map((i) => <NavLink key={i.href} item={i} label={t(i.key, i.label)} active={isActive(i.href)} />)}</Section>
        )}
        <Section title="General">
          {(admin ? GENERAL.filter((i) => ADMIN_ALLOWED.includes(i.href)) : GENERAL).map((i) => <NavLink key={i.href} item={i} label={t(i.key, i.label)} active={isActive(i.href)} />)}
          <button onClick={logout} className="focus-ring group flex items-center gap-3 rounded-xl px-3 py-2 text-start text-[15px] text-muted hover:bg-surface hover:text-ink">
            <LogOut className="h-5 w-5 group-hover:text-brand-600" />{t("nav.signout", "Logout")}
          </button>
        </Section>
      </nav>
      {admin ? (
        <div className="rounded-2xl bg-surface p-4 text-sm text-muted">Signed in as <b className="text-ink">{user.admin_role_label || "staff"}</b>. What you see here depends on your role; every change is recorded in the audit log.</div>
      ) : <div className="[@media(max-height:860px)]:hidden"><PlanCard /></div>}
    </div>
  );

  return (
    <div className="min-h-screen bg-canvas p-2 sm:p-3 lg:p-4">
      <div className="lg:flex lg:gap-4">
        <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-[17rem] shrink-0 rounded-3xl bg-panel lg:block">{sidebar}</aside>
        {open && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
            <aside className="absolute inset-y-0 start-0 w-[84%] max-w-xs bg-panel shadow-xl">{sidebar}</aside>
          </div>
        )}
        <div className="min-w-0 flex-1 space-y-3 lg:space-y-4">
          <TopBar user={user} onMenu={() => setOpen(true)} />
          <main className="min-h-[calc(100vh-8.5rem)] rounded-3xl bg-panel px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
            <MaintenanceBanner />
            <AnnouncementBanners />
            {!user.email_verified && <VerifyEmailBanner email={user.email} />}
            {!admin && <PlanBanner />}
            {admin && sysHealth?.ready?.checks?.ai?.mode === "offline" && (
              <div className="mb-6 rounded-2xl border border-accent-100 bg-accent-50 px-4 py-2.5 text-sm text-accent-600">
                Demo mode: no AI key is configured on the server, so teachers get built-in sample content. Add an Anthropic, OpenAI or Gemini key to .env.
              </div>
            )}
            {children}
          </main>
          {!admin && <UpgradeDialog />}
          <LegalGate />
        </div>
      </div>
    </div>
  );
}
