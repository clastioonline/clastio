"use client";

import {
  Bell,
  Bot,
  Brain,
  CalendarDays,
  ChartColumn,
  CircleHelp,
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
import { Logo } from "@/components/brand";
import { Spinner } from "@/components/ui";
import { UpgradeDialog } from "@/components/upgrade-dialog";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
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
  { href: "/tutorials", key: "nav.tutorials", label: "Tutorials & help", icon: CircleHelp },
  { href: "/billing", key: "nav.billing", label: "Plan & billing", icon: CreditCard },
  { href: "/settings", key: "nav.settings", label: "Settings", icon: Settings },
];
const ADMIN: Item[] = [
  { href: "/admin", key: "nav.admin", label: "Overview", icon: ShieldCheck },
  { href: "/admin/users", key: "nav.adminUsers", label: "Teachers", icon: Users },
  { href: "/admin/plans", key: "nav.plans", label: "Plans & trial", icon: CreditCard },
  { href: "/admin/media", key: "nav.payments", label: "Payments & media", icon: Wallet },
  { href: "/admin/ai-costs", key: "nav.aiCosts", label: "AI costs", icon: ChartColumn },
];
/* Pages an admin may open outside /admin. Everything else is the teacher product. */
const ADMIN_ALLOWED = ["/settings"];

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
  if (t?.active && t.days_left <= 3) {
    return (
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-accent-50 px-4 py-3 text-sm text-ink-2">
        <span>Your {data.plan.name} trial ends in <b>{t.days_left} day{t.days_left === 1 ? "" : "s"}</b>. Choose a plan to keep everything you've set up working.</span>
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

function Notifications({ admin }: { admin: boolean }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { data } = useApi<any>(admin ? null : "/me/dashboard", { refreshInterval: 60_000 });
  const { data: failed } = useApi<any>(admin ? "/admin/jobs?status=failed" : null, { refreshInterval: 60_000 });
  useEffect(() => {
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const items: { text: string; href: string }[] = [];
  if (failed?.items?.length) items.push({ text: `${failed.items.length} failed job(s) need a look`, href: "/admin#failed" });
  if (data?.next_class) {
    const n = data.next_class;
    items.push({ text: `${n.is_today ? "Today" : "Next"} ${n.start}: ${n.class.name} ${n.class.subject}${n.lesson ? ` — ${n.lesson.title}` : ""}`, href: n.lesson ? `/lessons/${n.lesson.id}` : "/calendar" });
  }
  if (data?.kpis?.building) items.push({ text: `${data.kpis.building} lesson(s) being built`, href: "/projects" });
  if (data?.kpis?.pending) items.push({ text: `${data.kpis.pending} lesson(s) waiting to be built`, href: "/projects" });
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)} aria-label="Notifications" aria-expanded={open}
        className="focus-ring relative grid h-11 w-11 place-items-center rounded-full bg-surface text-ink-2 hover:text-ink">
        <Bell className="h-5 w-5" />
        {items.length > 0 && <span className="absolute end-2.5 top-2.5 h-2 w-2 rounded-full bg-accent-500" />}
      </button>
      {open && (
        <div className="absolute end-0 top-13 z-50 mt-2 w-80 rounded-2xl border border-line bg-surface p-2 shadow-[var(--shadow-pop)]">
          {items.length ? items.map((i) => (
            <Link key={i.text} href={i.href} onClick={() => setOpen(false)} className="block rounded-xl px-3 py-2.5 text-sm text-ink-2 hover:bg-surface-2">{i.text}</Link>
          )) : <div className="px-3 py-4 text-sm text-muted">You're all caught up.</div>}
        </div>
      )}
    </div>
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
      <form className="relative hidden max-w-md flex-1 sm:block" role="search"
        onSubmit={(e) => { e.preventDefault(); router.push(`${admin ? "/admin/users" : "/lessons"}${q ? `?q=${encodeURIComponent(q)}` : ""}`); }}>
        <Search className="pointer-events-none absolute start-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted" />
        <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder={admin ? "Search teachers by name or email" : "Search lessons and documents"} aria-label={admin ? "Search teachers" : "Search lessons and documents"}
          className="h-12 w-full rounded-full bg-surface ps-12 pe-16 text-sm text-ink outline-none placeholder:text-muted focus:ring-2 focus:ring-brand-200" />
        <kbd className="absolute end-3 top-1/2 -translate-y-1/2 rounded-md bg-surface-2 px-2 py-1 text-xs text-muted">⌘ K</kbd>
      </form>
      <div className="lg:hidden"><Logo href="/dashboard" /></div>
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
        <Notifications admin={admin} />
        <Link href="/settings" className="focus-ring flex items-center gap-3 rounded-full py-1 pe-2 ps-1 hover:bg-surface">
          <span className="grid h-11 w-11 place-items-center rounded-full bg-gradient-to-br from-brand-400 to-brand-700 text-base font-semibold text-white">
            {(user.name || user.email).slice(0, 1).toUpperCase()}
          </span>
          <span className="hidden min-w-0 md:block">
            <span className="block max-w-[11rem] truncate text-sm font-semibold text-ink">{user.name || (admin ? "Admin" : "Teacher")}</span>
            <span className="block max-w-[11rem] truncate text-xs text-muted">{user.email}</span>
          </span>
        </Link>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, error, isLoading } = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { data: health } = useApi<any>("/health");

  useEffect(() => {
    if (error) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [error, pathname, router]);
  const admin = user?.role === "admin";
  useEffect(() => {
    if (!user) return;
    if (admin) {
      // Admins run the platform; the teacher product is not theirs to use or pay for.
      if (!pathname.startsWith("/admin") && !ADMIN_ALLOWED.includes(pathname)) router.replace("/admin");
    } else if (pathname.startsWith("/admin")) {
      router.replace("/dashboard");
    } else if (!user.onboarding_completed && pathname !== "/onboarding") {
      router.replace("/onboarding");
    }
  }, [user, admin, pathname, router]);
  useEffect(() => setOpen(false), [pathname]);

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
        <Logo href={user.role === "admin" ? "/admin" : "/dashboard"} />
        <button className="rounded-full p-2 text-muted hover:bg-surface lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu"><X className="h-5 w-5" /></button>
      </div>
      <nav className="-mx-4 flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto px-4" aria-label="Main">
        {admin ? (
          <Section title="Admin">{ADMIN.map((i) => <NavLink key={i.href} item={i} label={i.label} active={isActive(i.href)} />)}</Section>
        ) : (
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
        <div className="rounded-2xl bg-surface p-4 text-sm text-muted">Signed in as a platform admin. Teachers manage their own plans; you manage prices, trials and payments here.</div>
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
            {!admin && <PlanBanner />}
            {admin && health && health.ai_mode === "offline" && (
              <div className="mb-6 rounded-2xl border border-accent-100 bg-accent-50 px-4 py-2.5 text-sm text-accent-600">
                Demo mode: no AI key is configured on the server, so teachers get built-in sample content. Add an Anthropic, OpenAI or Gemini key to .env.
              </div>
            )}
            {children}
          </main>
          {!admin && <UpgradeDialog />}
        </div>
      </div>
    </div>
  );
}
