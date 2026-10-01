"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Badge, Button, Card, CardHeader, PageHeader, Skeleton } from "@/components/ui";
import { TemplatePreview } from "@/components/template-preview";
import { UploadDropzone } from "@/components/upload";
import { useApi } from "@/lib/hooks";

export default function Templates() {
  const router = useRouter();
  const { data, error, mutate } = useApi<any>("/templates");
  const mine = (data?.items || []).filter((t: any) => !t.builtin);
  const builtin = (data?.items || []).filter((t: any) => t.builtin);
  const Grid = ({ items }: { items: any[] }) => (
    <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
      {items.map((t) => (
        <Link key={t.id} href={`/templates/${t.id}`} className="focus-ring group block min-w-0 rounded-2xl border border-line bg-surface p-3 shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:border-brand-200">
          <TemplatePreview src={t.previews?.[0]} name={t.name} />
          <div className="mt-3 flex items-center justify-between gap-2 px-1">
            <div className="min-w-0">
              <div className="truncate font-medium text-ink group-hover:text-brand-700">{t.name}</div>
              <div className="mt-0.5 text-xs text-muted">{t.builtin ? "Built-in style" : t.can_edit === false ? "Shared with you" : t.mode === "native" ? "PowerPoint design" : "Reconstructed design"}</div>
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
      {error ? <Alert tone="danger">Couldn’t load your designs. <Button variant="outline" size="sm" onClick={() => mutate()}>Try again</Button></Alert> : !data ? <Skeleton className="h-64" /> : (
        <>
          {mine.length > 0 ? <section><h2 className="mb-3 font-semibold text-ink">Your templates</h2><Grid items={mine} /></section> : <section className="rounded-2xl border border-dashed border-line-strong p-6 text-center"><h2 className="font-semibold">Your templates</h2><p className="mt-2 text-sm text-muted">Your uploaded designs will appear here. Start with a built-in style or upload your own presentation above.</p></section>}
          <section><h2 className="mb-3 font-semibold text-ink">Built-in styles</h2><Grid items={builtin} /></section>
        </>
      )}
    </div>
  );
}
