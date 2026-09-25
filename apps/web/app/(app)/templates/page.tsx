"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Badge, Card, CardHeader, PageHeader, Skeleton } from "@/components/ui";
import { UploadDropzone } from "@/components/upload";
import { useApi } from "@/lib/hooks";

export default function Templates() {
  const router = useRouter();
  const { data, mutate } = useApi<any>("/templates");
  const mine = (data?.items || []).filter((t: any) => !t.builtin);
  const builtin = (data?.items || []).filter((t: any) => t.builtin);
  const Grid = ({ items }: { items: any[] }) => (
    <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((t) => (
        <Link key={t.id} href={`/templates/${t.id}`} className="focus-ring group block rounded-2xl border border-line bg-surface p-3 shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:border-brand-200">
          <div className="grid grid-cols-3 gap-1.5">
            {(t.previews || []).slice(0, 3).map((p: string, i: number) => (
              <div key={i} className={i === 0 ? "col-span-3 aspect-[16/9] overflow-hidden rounded-lg bg-surface-2" : "aspect-[16/9] overflow-hidden rounded-md bg-surface-2"}>
                <img src={p} alt="" className="h-full w-full object-cover" loading="lazy" />
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between gap-2 px-1">
            <div className="min-w-0">
              <div className="truncate font-medium text-ink group-hover:text-brand-700">{t.name}</div>
              <div className="mt-1 flex items-center gap-1.5">
                {[t.colors?.primary, t.colors?.secondary, t.colors?.background, t.colors?.text].filter(Boolean).map((c: string, i: number) => (
                  <span key={i} className="h-4 w-4 rounded-full border border-line" style={{ background: c }} title={c} />
                ))}
                <span className="ms-1 truncate text-xs text-muted">{t.fonts?.heading} / {t.fonts?.body}</span>
              </div>
            </div>
            {t.is_default && <Badge tone="success">Default</Badge>}
          </div>
        </Link>
      ))}
    </div>
  );
  return (
    <div className="space-y-8">
      <PageHeader title="My designs" subtitle="Upload a deck you've taught with. We keep your slide master, colours, fonts, logo and layouts, and never modify the original." />
      <Card>
        <CardHeader title="Add your style" subtitle="PowerPoint files give an exact match. PDFs are reconstructed as closely as possible." />
        <div className="p-5"><UploadDropzone onReady={({ templateId }) => { mutate(); if (templateId) router.push(`/templates/${templateId}`); }} /></div>
      </Card>
      {!data ? <Skeleton className="h-64" /> : (
        <>
          {mine.length > 0 && <section><h2 className="mb-3 font-semibold text-ink">Your templates</h2><Grid items={mine} /></section>}
          <section><h2 className="mb-3 font-semibold text-ink">Built-in styles</h2><Grid items={builtin} /></section>
        </>
      )}
    </div>
  );
}
