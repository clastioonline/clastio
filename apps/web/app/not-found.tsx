import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
      <p className="text-sm font-semibold text-brand-600">404 · Page not found</p>
      <h1 className="mt-3 text-3xl font-bold text-ink">Let’s get you back to your lessons</h1>
      <p className="mt-4 text-muted">This link may be out of date, or the page may have moved.</p>
      <Link href="/dashboard" className="focus-ring mt-6 rounded-xl bg-brand-600 px-5 py-3 font-medium text-white">Open dashboard</Link>
      <Link href="/" className="focus-ring mt-4 rounded-lg px-3 py-2 text-brand-600 underline">Go home</Link>
    </main>
  );
}
