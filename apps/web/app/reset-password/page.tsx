"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthLayout } from "@/components/auth-card";
import { Alert, Button, Field, Input } from "@/components/ui";
import { api } from "@/lib/api";

export default function ResetPassword() {
  const [token, setToken] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setToken(new URLSearchParams(window.location.search).get("token")), []);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) { setError("The two passwords don't match."); return; }
    setBusy(true);
    setError(null);
    try {
      await api("/auth/reset-password", { body: { token, password } });
      setDone(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthLayout title="Choose a new password" subtitle="You'll be signed out on every other device."
      footer={<Link href="/login" className="font-medium text-brand-600 hover:underline">Back to sign in</Link>}>
      {done ? (
        <div className="space-y-4"><Alert tone="success" title="Password changed">Sign in with your new password.</Alert><Button href="/login" className="w-full">Sign in</Button></div>
      ) : !token ? <Alert tone="danger">This link is incomplete. Request a new one from “Forgot password”.</Alert> : (
        <form onSubmit={submit} className="space-y-4">
          {error && <Alert tone="danger">{error}</Alert>}
          <Field label="New password" hint="At least 8 characters; avoid common passwords.">
            <Input type="password" required minLength={8} autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Confirm password"><Input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
          <Button type="submit" className="w-full" size="lg" loading={busy}>Save new password</Button>
        </form>
      )}
    </AuthLayout>
  );
}
