"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthLayout, OAuthButtons, TermsNote } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
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
      await api("/auth/signup", { body: { ...form, accept_terms: true } });
      router.replace("/onboarding");
    } catch (err: any) {
      setError(err.status === 422 ? "Check your details: passwords need at least 8 characters." : err.message);
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Create your teaching assistant" subtitle={trial ? `Start your ${trial.days}-day free trial of ${trialPlan || "PPT Genie"}. No card needed.` : "Free to start. Set up in about 5 minutes."}
      footer={<>Already have an account? <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link></>}>
      <OAuthButtons />
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Your name"><Input required value={form.name} onChange={set("name")} placeholder="Sara Ahmed" autoComplete="name" /></Field>
        <Field label="Email"><Input type="email" required value={form.email} onChange={set("email")} placeholder="you@school.ae" autoComplete="email" /></Field>
        <Field label="Password" hint="At least 8 characters.">
          <Input type="password" required minLength={8} value={form.password} onChange={set("password")} autoComplete="new-password" />
        </Field>
        <Button type="submit" className="w-full" size="lg" loading={busy}>Create account</Button>
        <TermsNote />
      </form>
    </AuthLayout>
  );
}
