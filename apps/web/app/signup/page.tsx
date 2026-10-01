"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AuthLayout, Captcha, OAuthButtons } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useSWRConfig } from "swr";
import { useApi } from "@/lib/hooks";

export default function SignupPage() {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [captcha, setCaptcha] = useState<string | null>(null);
  const onCaptcha = useCallback((t: string | null) => setCaptcha(t), []);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { data: plans } = useApi<any>("/billing/plans");
  const trial = plans?.trial?.enabled ? plans.trial : null;
  const trialPlan = trial ? plans.items.find((p: any) => p.code === trial.plan)?.name : null;
  useEffect(() => {
    // The landing page's email box passes the address along.
    const email = new URLSearchParams(window.location.search).get("email");
    if (email) setForm((f) => ({ ...f, email }));
  }, []);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const params = new URLSearchParams(window.location.search);
      const utm: Record<string, string> = {};
      for (const k of ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"]) {
        const v = params.get(k);
        if (v) utm[k] = v;
      }
      if (document.referrer) utm.referrer = document.referrer.slice(0, 120);
      await api("/auth/signup", { body: { ...form, accept_terms: acceptTerms, marketing_email: marketing, utm,
        referral_code: params.get("ref") || undefined, captcha_token: captcha || undefined } });
      await mutate("/auth/me", await api("/auth/me"), { revalidate: false });
      router.replace("/onboarding");
    } catch (err: any) {
      setError(err.code === "validation_error" ? "Check your details: passwords need at least 8 characters." : err.message);
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Create your teaching assistant" subtitle={trial ? `Start your ${trial.days}-day free trial of ${trialPlan || "Clastio"}. No card needed.` : "Free to start. Set up in about 5 minutes."}
      footer={<>Already have an account? <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link></>}>
      <OAuthButtons />
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Your name"><Input required value={form.name} onChange={set("name")} placeholder="Sara Ahmed" autoComplete="name" /></Field>
        <Field label="Email"><Input type="email" required value={form.email} onChange={set("email")} placeholder="you@school.ae" autoComplete="email" /></Field>
        <Field label="Password" hint="At least 8 characters.">
          <Input type="password" required minLength={8} value={form.password} onChange={set("password")} autoComplete="new-password" />
        </Field>
        <label className="flex items-start gap-2 text-sm text-ink-2">
          <input type="checkbox" required className="mt-0.5 h-4 w-4 accent-[var(--color-brand-600)]" checked={acceptTerms} onChange={(e) => setAcceptTerms(e.target.checked)} />
          <span>I agree to the <Link href="/legal/terms" target="_blank" className="text-brand-600 underline">Terms & Conditions</Link> and <Link href="/legal/acceptable_use" target="_blank" className="text-brand-600 underline">Acceptable Use Policy</Link>, and I have read the <Link href="/legal/privacy" target="_blank" className="text-brand-600 underline">Privacy Policy</Link>.</span>
        </label>
        <label className="flex items-start gap-2 text-sm text-muted">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--color-brand-600)]" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
          <span>Send me occasional tips and product news by email (optional — change any time in Settings).</span>
        </label>
        <Captcha onToken={onCaptcha} />
        <Button type="submit" className="w-full" size="lg" loading={busy} disabled={!acceptTerms}>Create account</Button>
        <p className="text-xs text-muted">We never need your students' personal data.</p>
      </form>
    </AuthLayout>
  );
}
