"use client";
import { SignIn, SignUp } from "@clerk/nextjs";
import Link from "next/link";
export function ClerkAuth({ signup = false }: { signup?: boolean }) {
  return <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
    {signup ? <SignUp routing="hash" /> : <SignIn routing="hash" />}
    <Link href="/login?legacy=1" className="text-sm underline">Sign in to an existing Clastio account</Link>
  </main>;
}
