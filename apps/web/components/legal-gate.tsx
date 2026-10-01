"use client";

import { ExternalLink } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "@/components/toast";
import { Alert, Button } from "@/components/ui";
import { api } from "@/lib/api";
import { useMe } from "@/lib/hooks";

/* When a new version of a policy that needs acceptance is published, signed-in users see this before
   continuing. Each acceptance is recorded with the exact version, time and method. */
export function LegalGate() {
  const { pendingLegal, mutate } = useMe();
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!pendingLegal.length) return null;
  const accept = async () => {
    setBusy(true);
    setError(null);
    try {
      await api("/me/legal/accept", { body: { document_types: pendingLegal.map((d) => d.type) } });
      await mutate();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="fixed inset-0 z-[70] grid place-items-center bg-ink/50 p-4 backdrop-blur-[2px]">
      <div role="dialog" aria-modal="true" aria-labelledby="legal-title" className="w-full max-w-lg rounded-2xl border border-line bg-surface p-6 shadow-[var(--shadow-pop)]">
        <h2 id="legal-title" className="text-lg font-semibold text-ink">We've updated our policies</h2>
        <p className="mt-1 text-sm text-muted">Please review the changes to keep using Clastio.</p>
        <ul className="mt-4 space-y-3">
          {pendingLegal.map((d) => (
            <li key={d.id} className="rounded-xl bg-surface-2 p-3 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-ink">{d.title} <span className="text-muted">v{d.version}</span></span>
                <a href={`/legal/${d.type}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-brand-600 hover:underline">Read <ExternalLink className="h-3.5 w-3.5" /></a>
              </div>
              {d.summary_of_changes && <p className="mt-1 text-muted">{d.summary_of_changes}</p>}
            </li>
          ))}
        </ul>
        <label className="mt-4 flex items-start gap-2 text-sm text-ink-2">
          <input type="checkbox" className="mt-0.5 h-4 w-4 accent-[var(--color-brand-600)]" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
          <span>I have read and agree to the updated {pendingLegal.map((d) => d.title).join(" and ")}.</span>
        </label>
        {error && <Alert tone="danger" className="mt-3">{error}</Alert>}
        <div className="mt-5 flex flex-wrap justify-end gap-2">
          <Button variant="ghost" onClick={async () => { await api("/auth/logout", { method: "POST" }); window.location.href = "/"; }}>Sign out</Button>
          <Button disabled={!agreed} loading={busy} onClick={accept}>Accept and continue</Button>
        </div>
      </div>
    </div>
  );
}
