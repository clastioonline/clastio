"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthLayout } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ message: string }>("/auth/forgot-password", { body: { email } });
      setSent(r.message);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Reset your password" subtitle="We'll email you a link to choose a new one."
      footer={<Link href="/login" className="font-medium text-brand-600 hover:underline">Back to sign in</Link>}>
      {sent ? <Alert tone="success" title="Check your email">{sent} The link works once and expires in 30 minutes.</Alert> : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="Email"><Input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          <Button type="submit" className="w-full" size="lg" loading={busy}>Send reset link</Button>
        </form>
      )}
    </AuthLayout>
  );
}
