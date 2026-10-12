"use client";
import { useAuth } from "@clerk/nextjs";
import { Suspense, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { postSignInPath, safeSignInReturnPath } from "@/lib/navigation";
import { Alert, Button } from "@/components/ui";

export default function ClerkCallback() {
  return process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY ? <Suspense fallback={<main className="p-6">Completing sign in…</main>}><EnabledCallback /></Suspense> : <main className="p-6">Clerk sign-in is not configured. <Link href="/login">Sign in</Link></main>;
}
function EnabledCallback() {
  const { isLoaded, isSignedIn, getToken, signOut } = useAuth();
  const params = useSearchParams();
  const next = safeSignInReturnPath(params.get("next"));
  const login = `/login?next=${encodeURIComponent(next)}`;
  const started = useRef(false);
  const [error, setError] = useState("");
  const [needsTerms, setNeedsTerms] = useState(false);
  const [busy, setBusy] = useState(false);
  const finish = async (acceptTerms = false) => {
    setBusy(true);
    setError("");
    try {
      const token = await getToken();
      let referral_code: string | undefined;
      try { referral_code = sessionStorage.getItem("clastio:referral") || undefined; } catch { /* optional */ }
      const result = await api<{user: {onboarding_completed: boolean; role: string; permissions: string[]}}>("/auth/clerk", {body: {token, accept_terms: acceptTerms, referral_code}});
      window.location.replace(postSignInPath(result.user, next));
    } catch (err: any) {
      if (err.code === "terms_required") setNeedsTerms(true);
      else setError(err.message);
      setBusy(false);
    }
  };
  useEffect(() => {
    if (!isLoaded || started.current) return;
    started.current = true;
    if (!isSignedIn) window.location.replace(login);
    else void finish();
  }, [isLoaded, isSignedIn]); // Establish the app session once after Clerk authenticates.
  return <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 px-6">
    <h1 className="text-xl font-semibold">Complete your Clastio sign-in</h1>
    {error && <><Alert tone="danger">{error}</Alert><Button onClick={() => finish()} loading={busy}>Try again</Button><Link href={`/login?legacy=1&next=${encodeURIComponent(next)}`} className="underline">Connect an existing account</Link></>}
    {needsTerms && <><p>By creating your account, you agree to the <Link href="/legal/terms" className="underline">Terms</Link> and <Link href="/legal/acceptable_use" className="underline">Acceptable Use Policy</Link> and acknowledge the <Link href="/legal/privacy" className="underline">Privacy Policy</Link>.</p><Button onClick={() => finish(true)} loading={busy}>Agree and create account</Button></>}
    {!error && !needsTerms && <p>Signing you in…</p>}
    <Button variant="ghost" onClick={() => signOut({redirectUrl: login})}>Use a different account</Button>
  </main>;
}
