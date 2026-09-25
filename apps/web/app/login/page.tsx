"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { AuthLayout, OAuthButtons } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ user: { onboarding_completed: boolean; role: string } }>("/auth/login", { body: { email, password } });
      const next = params.get("next");
      router.replace(!res.user.onboarding_completed ? "/onboarding" : next && next.startsWith("/") ? next : res.user.role === "admin" ? "/admin" : "/dashboard");
    } catch (err: any) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <AuthLayout title="Welcome back" subtitle="Sign in to your teaching assistant."
      footer={<>New here? <Link href="/signup" className="font-medium text-brand-600 hover:underline">Create a free account</Link></>}>
      <OAuthButtons />
      <form onSubmit={submit} className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        <Field label="Email">
          <Input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@school.ae" />
        </Field>
        <Field label={<span className="flex items-center justify-between">Password <Link href="/forgot-password" className="text-xs font-medium text-brand-600 hover:underline">Forgot password?</Link></span>}>
          <Input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <Button type="submit" className="w-full" size="lg" loading={busy}>Sign in</Button>
      </form>
    </AuthLayout>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
