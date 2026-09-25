"use client";

import {
  Bot,
  CalendarDays,
  ChartColumn,
  CreditCard,
  FolderKanban,
  GraduationCap,
  House,
  Languages,
  LayoutGrid,
  LogOut,
  Menu,
  MessageCircle,
  Brain,
  ImagePlay,
  NotebookPen,
  Palette,
  Settings,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Logo } from "@/components/brand";
import { Badge, Progress, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", key: "nav.today", label: "Today", icon: House },
  { href: "/assistant", key: "nav.assistant", label: "Assistant", icon: Bot },
  { href: "/projects", key: "nav.projects", label: "Projects", icon: FolderKanban },
  { href: "/lessons", key: "nav.lessons", label: "Lessons & documents", icon: NotebookPen },
  { href: "/calendar", key: "nav.calendar", label: "Calendar & timetable", icon: CalendarDays },
  { href: "/curriculum", key: "nav.curriculum", label: "Classes & curriculum", icon: GraduationCap },
  { href: "/templates", key: "nav.templates", label: "Design templates", icon: Palette },
  { href: "/media", key: "nav.media", label: "Media studio", icon: ImagePlay },
  { href: "/teacher-memory", key: "nav.memory", label: "Teacher memory", icon: Brain },
  { href: "/whatsapp", key: "nav.whatsapp", label: "WhatsApp", icon: MessageCircle },
];
const NAV_BOTTOM = [
  { href: "/billing", key: "nav.billing", label: "Plan & billing", icon: CreditCard },
  { href: "/settings", key: "nav.settings", label: "Settings", icon: Settings },
];

function NavLink({ href, label, icon: Icon, active, onClick }: { href: string; label: string; icon: any; active: boolean; onClick?: () => void }) {
  return (
    <Link href={href} onClick={onClick} data-active={active}
      className={cn("ui-nav focus-ring group flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
        active ? "bg-brand-600 text-white shadow-sm" : "text-ink-2 hover:bg-surface-2 hover:text-ink")}>
      <Icon className={cn("h-[18px] w-[18px] shrink-0", active ? "text-white" : "text-muted group-hover:text-brand-600")} />
      <span className="truncate">{label}</span>
    </Link>
  );
}

function UsageMeter() {
  const { data } = useApi<any>("/me/usage", { refreshInterval: 30_000 });
  if (!data) return null;
  const c = data.usage.credits;
  const pct = c.limit && c.limit > 0 ? (c.used / c.limit) * 100 : 0;
  return (
    <Link href="/billing" className="focus-ring block rounded-xl border border-line bg-surface-2/60 p-3 hover:border-brand-200">
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-ink">{data.plan.name}</span>
        {data.plan.code === "free" ? <Badge tone="accent">Upgrade</Badge> : <Sparkles className="h-3.5 w-3.5 text-accent-500" />}
      </div>
      {c.limit > 0 && (
        <>
          <Progress value={pct} className="mt-2 h-1.5" tone={pct > 85 ? "accent" : "brand"} />
          <div className="mt-1.5 text-[11px] text-muted">{c.used} / {c.limit} credits this month</div>
        </>
      )}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { user, error, isLoading } = useMe();
  const pathname = usePathname();
  const router = useRouter();
  const { t, locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);
  const { data: health } = useApi<any>("/health");

  useEffect(() => {
    if (error) router.replace(`/login?next=${encodeURIComponent(pathname)}`);
  }, [error, pathname, router]);
  useEffect(() => {
    if (user && !user.onboarding_completed && pathname !== "/onboarding") router.replace("/onboarding");
  }, [user, pathname, router]);
  useEffect(() => setOpen(false), [pathname]);

  if (isLoading || !user) {
    return (
      <div className="grid min-h-screen place-items-center">
        <Spinner className="h-7 w-7" />
      </div>
    );
  }

  const isActive = (href: string) => pathname === href || (href !== "/dashboard" && pathname.startsWith(href + "/"));
  const logout = async () => {
    await api("/auth/logout", { method: "POST" });
    window.location.href = "/login";
  };

  const sidebar = (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <Logo href="/dashboard" />
        <button className="rounded-lg p-2 text-muted hover:bg-surface-2 lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
          <X className="h-5 w-5" />
        </button>
      </div>
      <nav className="-mx-4 flex flex-1 flex-col gap-1 overflow-y-auto px-4" aria-label="Main">
        {NAV.map((n) => <NavLink key={n.href} href={n.href} label={t(n.key, n.label)} icon={n.icon} active={isActive(n.href)} />)}
        <div className="my-2 border-t border-line" />
        {NAV_BOTTOM.map((n) => <NavLink key={n.href} href={n.href} label={t(n.key, n.label)} icon={n.icon} active={isActive(n.href)} />)}
        {user.role === "admin" && (
          <>
            <NavLink href="/admin" label={t("nav.admin", "Admin")} icon={LayoutGrid} active={pathname === "/admin"} />
            <NavLink href="/admin/ai-costs" label="AI costs" icon={ChartColumn} active={pathname === "/admin/ai-costs"} />
            <NavLink href="/admin/media" label="Payments & media" icon={Wallet} active={pathname === "/admin/media"} />
          </>
        )}
      </nav>
      <UsageMeter />
      <div className="flex items-center gap-2 border-t border-line pt-3">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
          {(user.name || user.email).slice(0, 1).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-ink">{user.name || "Teacher"}</div>
          <div className="truncate text-xs text-muted">{user.email}</div>
        </div>
        <button onClick={() => setLocale(locale === "ar" ? "en" : "ar")} className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-ink"
          title={locale === "ar" ? "English" : "العربية"} aria-label="Switch language">
          <Languages className="h-4 w-4" />
        </button>
        <button onClick={logout} className="rounded-lg p-2 text-muted hover:bg-surface-2 hover:text-ink" title={t("nav.signout", "Sign out")} aria-label="Sign out">
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:ps-72">
      <aside className="fixed inset-y-0 start-0 z-40 hidden w-72 border-e border-line bg-surface lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-ink/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 start-0 w-[84%] max-w-xs bg-surface shadow-xl">{sidebar}</aside>
        </div>
      )}
      <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-surface/85 px-4 backdrop-blur lg:hidden">
        <button className="rounded-lg p-2 text-ink hover:bg-surface-2" onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu className="h-5 w-5" />
        </button>
        <Logo href="/dashboard" />
      </header>
      {health && health.ai_mode === "offline" && (
        <div className="border-b border-accent-100 bg-accent-50 px-4 py-2 text-center text-xs text-accent-600">
          Demo mode: no AI provider key is configured, so lessons use built-in sample content. Add an Anthropic, OpenAI or Gemini key for real content.
        </div>
      )}
      <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-10 lg:py-8">{children}</main>
    </div>
  );
}
