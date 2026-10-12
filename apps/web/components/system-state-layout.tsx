import type { ReactNode } from "react";
import { safeSystemHref, SYSTEM_STATE_CSS, type SystemAction, type SystemTone } from "@/lib/system-pages";

export type SystemStateLayoutProps = {
  title: string;
  description: string;
  code?: string;
  tone?: SystemTone;
  children?: ReactNode;
  actions?: ReactNode;
  primaryAction?: SystemAction;
  secondaryAction?: SystemAction;
  hints?: string[];
  reference?: string;
};

export function SystemStateLayout({ title, description, code, tone = "neutral", children, actions,
  primaryAction, secondaryAction, hints, reference }: SystemStateLayoutProps) {
  return <main className="sys-page">
    <style>{SYSTEM_STATE_CSS}</style>
    <div className="sys-wrap">
      <header className="sys-header">
        <a className="sys-brand" href="/" aria-label="Clastio home"><img src="/brand/favicon.png" width={44} height={44} alt="" />Clastio</a>
        <nav className="sys-nav" aria-label="Help navigation"><a href="/help">Help</a><a href="/contact">Contact</a><a href="/status">Status</a></nav>
      </header>
      <section className="sys-card" aria-labelledby="sys-title">
        <span className="sys-badge" data-tone={tone}>{code ? `${code} · Clastio` : "Clastio"}</span>
        <h1 id="sys-title">{title}</h1>
        <p className="sys-description">{description}</p>
        {(actions || primaryAction || secondaryAction) && <div className="sys-actions">
          {actions}
          {primaryAction && <a className="sys-action sys-primary" href={safeSystemHref(primaryAction.href)}>{primaryAction.label}</a>}
          {secondaryAction && <a className="sys-action" href={safeSystemHref(secondaryAction.href)}>{secondaryAction.label}</a>}
        </div>}
        {children && <div className="sys-content">{children}</div>}
        {!!hints?.length && <aside className="sys-hints"><h2>What you can do</h2><ul>{hints.map(hint => <li key={hint}>{hint}</li>)}</ul></aside>}
        {reference && <p className="sys-reference">Reference: <code>{reference}</code></p>}
      </section>
      <footer className="sys-footer"><span>Your teaching, in your own design.</span>
        <nav className="sys-footer-links" aria-label="Useful links"><a href="/solutions">Teaching guides</a><a href="/legal/privacy">Privacy</a><a href="/">Home</a></nav>
      </footer>
    </div>
  </main>;
}
