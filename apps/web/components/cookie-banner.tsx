"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useSWRConfig } from "swr";

const KEY = "clastio:cookie-consent";

/* Clastio sets essential session and signed random installation cookies. Optional analytics/marketing cookies are off
   unless the visitor opts in here; the choice is stored on this device and, when signed in, recorded as consent. */
export function CookieBanner() {
  const { cache } = useSWRConfig();
  const [show, setShow] = useState(false);
  const [custom, setCustom] = useState(false);
  const [analytics, setAnalytics] = useState(false);
  useEffect(() => {
    try { setShow(!localStorage.getItem(KEY)); } catch { setShow(false); }
  }, []);
  const save = (choice: { analytics: boolean; marketing: boolean }) => {
    try { localStorage.setItem(KEY, JSON.stringify({ ...choice, at: new Date().toISOString() })); } catch { /* ignore */ }
    if (cache.get("/auth/me")?.data?.user) api("/me/cookie-consent", { body: choice }).catch(() => {});
    setShow(false);
  };
  if (!show) return null;
  return (
    <div role="dialog" aria-label="Cookie preferences" className="fixed inset-x-3 bottom-3 z-[65] mx-auto max-w-2xl rounded-2xl border border-line bg-surface p-4 text-sm shadow-[var(--shadow-pop)] sm:inset-x-6">
      <p className="text-ink-2">
        We use essential cookies to keep you signed in and reduce repeat trials and reward abuse. With your permission we'd also use analytics cookies to improve Clastio.
        See our <Link href="/legal/cookie" className="text-brand-600 underline">Cookie Policy</Link>.
      </p>
      {custom && (
        <label className="mt-3 flex items-center gap-2 text-ink-2">
          <input type="checkbox" className="h-4 w-4" checked={analytics} onChange={(e) => setAnalytics(e.target.checked)} /> Analytics cookies
        </label>
      )}
      <div className="mt-3 flex flex-wrap justify-end gap-2">
        {custom ? (
          <button onClick={() => save({ analytics, marketing: false })} className="rounded-full bg-brand-600 px-4 py-2 font-semibold text-white">Save choice</button>
        ) : (
          <>
            <button onClick={() => setCustom(true)} className="rounded-full px-4 py-2 font-medium text-ink-2 hover:bg-surface-2">Customise</button>
            <button onClick={() => save({ analytics: false, marketing: false })} className="rounded-full border border-line-strong px-4 py-2 font-medium text-ink">Essential only</button>
            <button onClick={() => save({ analytics: true, marketing: false })} className="rounded-full bg-brand-600 px-4 py-2 font-semibold text-white">Accept analytics</button>
          </>
        )}
      </div>
    </div>
  );
}
