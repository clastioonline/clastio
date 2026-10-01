"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-lg flex-col items-center justify-center px-6 text-center">
      <h1 className="text-2xl font-bold text-ink">We couldn’t load this page</h1>
      <p className="mt-3 text-muted">Please try again. If the problem continues, contact support from your account.</p>
      <div className="mt-6 flex items-center gap-4">
        <button onClick={reset} className="focus-ring rounded-xl bg-brand-600 px-5 py-3 font-medium text-white">Try again</button>
        <Link href="/" className="focus-ring rounded-lg px-3 py-2 text-brand-600 underline">Go home</Link>
      </div>
    </main>
  );
}
