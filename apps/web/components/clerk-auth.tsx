"use client";
import { SignIn, SignUp } from "@clerk/nextjs";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { clerkCallbackPath, safeSignInReturnPath } from "@/lib/navigation";
export function ClerkAuth({ signup = false }: { signup?: boolean }) {
  return <Suspense fallback={<main className="p-6">Loading sign in…</main>}><ClerkAuthContent signup={signup} /></Suspense>;
}
function ClerkAuthContent({ signup }: { signup: boolean }) {
  const params = useSearchParams();
  const next = safeSignInReturnPath(params.get("next"));
  const callback = clerkCallbackPath(next);
  const query = `next=${encodeURIComponent(next)}`;
  return <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
    {signup ? <SignUp routing="hash" forceRedirectUrl={callback} signInForceRedirectUrl={callback} signInUrl={`/login?${query}`} /> : <SignIn routing="hash" forceRedirectUrl={callback} signUpForceRedirectUrl={callback} signUpUrl={`/signup?${query}`} />}
    <Link href={`/login?legacy=1&${query}`} className="text-sm underline">Sign in to an existing Clastio account</Link>
  </main>;
}
