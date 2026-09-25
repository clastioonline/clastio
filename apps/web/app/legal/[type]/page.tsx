"use client";

import Link from "next/link";
import { use, useState } from "react";
import { LandingFooter, LandingNav } from "@/components/marketing";
import { Markdown } from "@/components/markdown";
import { Skeleton } from "@/components/ui";
import { formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

const DOCS = [
  ["terms", "Terms"], ["privacy", "Privacy"], ["acceptable_use", "Acceptable use"], ["cookie", "Cookies"], ["refund", "Refunds"],
];

export default function LegalPage({ params }: { params: Promise<{ type: string }> }) {
  const { type } = use(params);
  const [version, setVersion] = useState<string | null>(null);
  const { data, error } = useApi<any>(`/legal/${type}${version ? `?version=${encodeURIComponent(version)}` : ""}`);
  return (
    <div className="landing min-h-screen bg-[var(--l-bg)] text-[var(--l-ink)]">
      <LandingNav />
      <main className="mx-auto grid max-w-5xl gap-8 px-4 py-12 sm:px-6 md:grid-cols-[12rem_1fr]">
        <nav aria-label="Legal documents" className="space-y-1 text-sm">
          {DOCS.map(([t, label]) => (
            <Link key={t} href={`/legal/${t}`} className={cn("block rounded-lg px-3 py-2", t === type ? "bg-[var(--l-card)] font-semibold" : "text-[var(--l-muted)] hover:text-[var(--l-ink)]")}>{label}</Link>
          ))}
          <Link href="/status" className="block rounded-lg px-3 py-2 text-[var(--l-muted)] hover:text-[var(--l-ink)]">System status</Link>
        </nav>
        <article className="min-w-0 rounded-3xl bg-[var(--l-card)] p-6 sm:p-10">
          {error ? <p>This document isn't available.</p> : !data ? <Skeleton className="h-96" /> : (
            <>
              <h1 className="text-3xl font-bold tracking-tight">{data.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-[var(--l-muted)]">
                <span>Version {data.version}{data.effective_from ? ` · effective ${formatDate(data.effective_from, { day: "numeric", month: "long", year: "numeric" })}` : ""}</span>
                {data.versions?.length > 1 && (
                  <label className="flex items-center gap-2">Earlier versions
                    <select className="rounded-lg border border-[var(--l-line)] bg-transparent px-2 py-1" value={version || data.version}
                      onChange={(e) => setVersion(e.target.value === data.versions[0].version ? null : e.target.value)}>
                      {data.versions.map((v: any) => <option key={v.id} value={v.version}>v{v.version}</option>)}
                    </select>
                  </label>
                )}
              </div>
              {data.summary_of_changes && <p className="mt-4 rounded-xl bg-[var(--l-bg)] p-3 text-sm"><b>What changed:</b> {data.summary_of_changes}</p>}
              <div className="legal-doc mt-6 leading-relaxed"><Markdown text={data.content} /></div>
            </>
          )}
        </article>
      </main>
      <LandingFooter />
    </div>
  );
}
