"use client";

import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { Logo } from "@/components/brand";
import { useApi } from "@/lib/hooks";

export function AuthLayout({ title, subtitle, children, footer }: { title: string; subtitle: ReactNode; children: ReactNode; footer: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="flex flex-col justify-center px-6 py-10 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Logo />
          <h1 className="mt-10 text-2xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-1.5 text-sm text-muted">{subtitle}</p>
          <div className="mt-8">{children}</div>
          <div className="mt-6 text-sm text-muted">{footer}</div>
        </div>
      </div>
      <div className="ui-hero relative hidden overflow-hidden bg-brand-600 lg:block">
        <div className="absolute -end-20 -top-20 h-96 w-96 rounded-full bg-brand-500/40 blur-3xl" />
        <div className="absolute -bottom-24 -start-10 h-80 w-80 rounded-full bg-accent-500/30 blur-3xl" />
        <div className="relative flex h-full flex-col justify-end p-12 text-white">
          <p className="max-w-md text-2xl font-medium leading-snug">
            Upload last year's slides once. Every lesson after that comes out in your own template, with your fonts, colours and logo.
          </p>
          <ul className="mt-6 space-y-2 text-sm text-white/80">
            <li>• Connected lesson sequences, not repeated slides</li>
            <li>• Worksheets, quizzes and homework with answer keys</li>
            <li>• Your daily plan on WhatsApp</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export function OAuthButtons() {
  const { data } = useApi<{ providers: string[] }>("/auth/oauth/providers");
  const providers = data?.providers || [];
  if (!providers.length) return null;
  return (
    <div className="space-y-2">
      {providers.map((p) => (
        <a key={p} href={`/api/v1/auth/oauth/${p}/start`}
          className="flex h-10 w-full items-center justify-center gap-2 rounded-xl border border-line-strong bg-surface text-sm font-medium text-ink hover:bg-surface-2">
          Continue with {p === "google" ? "Google" : "Microsoft"}
        </a>
      ))}
      <div className="my-4 flex items-center gap-3 text-xs text-muted"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
    </div>
  );
}

export function TermsNote() {
  return (
    <p className="mt-4 text-xs text-muted">
      By continuing you agree to the <Link href="/legal/terms" className="underline">Terms</Link> and <Link href="/legal/acceptable_use" className="underline">Acceptable Use Policy</Link> and acknowledge the <Link href="/legal/privacy" className="underline">Privacy Policy</Link>.
      We never need your students' personal data.
    </p>
  );
}


/* Cloudflare Turnstile, shown only when the server has a site key configured. */
export function Captcha({ onToken }: { onToken: (t: string | null) => void }) {
  const { data } = useApi<any>("/public/config");
  const key = data?.turnstile_site_key;
  useEffect(() => {
    if (!key) return;
    (window as any).pptgCaptcha = (t: string) => onToken(t);
    (window as any).pptgCaptchaExpired = () => onToken(null);
    if (!document.getElementById("cf-turnstile")) {
      const sc = document.createElement("script");
      sc.id = "cf-turnstile";
      sc.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
      sc.async = true;
      document.head.appendChild(sc);
    }
  }, [key, onToken]);
  if (!key) return null;
  return <div className="cf-turnstile" data-sitekey={key} data-callback="pptgCaptcha" data-expired-callback="pptgCaptchaExpired" />;
}
