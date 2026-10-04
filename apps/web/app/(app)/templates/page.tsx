"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Alert, Badge, Button, Card, CardHeader, Input, PageHeader, Select, Skeleton } from "@/components/ui";
import { TemplatePreview } from "@/components/template-preview";
import { UploadDropzone } from "@/components/upload";
import { useApi } from "@/lib/hooks";

export default function Templates() {
  const router = useRouter();
  const { data, error, mutate } = useApi<any>("/templates");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const filtered = (data?.items || []).filter((t: any) => `${t.name} ${t.description || ""} ${(t.tags || []).join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()) &&
    (filter === "all" || (filter === "default" ? t.is_default : filter === "builtin" ? t.builtin : filter === "uae" ? t.tags?.includes("UAE") : filter === "suggested" ? !!t.recommendation : !t.builtin)));
  const mine = filtered.filter((t: any) => !t.builtin);
  const builtin = filtered.filter((t: any) => t.builtin);
  const recommended = (data?.recommendations || []).map((r: any) => filtered.find((t: any) => t.id === r.template_id)).filter(Boolean);
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
          {t.description && <p className="mt-2 px-1 text-xs leading-relaxed text-muted">{t.description}</p>}
          {t.tags?.length > 0 && <div className="mt-2 flex flex-wrap gap-1 px-1">{t.tags.map((tag: string) => <Badge key={tag}>{tag}</Badge>)}</div>}
          {t.recommendation && <p className="mt-3 rounded-lg bg-brand-50 px-2 py-1.5 text-xs leading-relaxed text-brand-800"><span className="font-semibold">Suggested:</span> {t.recommendation.reason}</p>}
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
      <div className="flex flex-col gap-3 sm:flex-row"><Input aria-label="Search designs" placeholder="Search designs, subjects or curricula…" value={query} onChange={e => setQuery(e.target.value)} /><Select aria-label="Filter designs" className="sm:max-w-52" value={filter} onChange={e => setFilter(e.target.value)}><option value="all">All designs</option><option value="suggested">Suggested for you</option><option value="uae">UAE classroom styles</option><option value="mine">Uploaded and shared</option><option value="builtin">Built-in styles</option><option value="default">Default design</option></Select></div>
      {data && !filtered.length && (query || filter !== "all") && <p role="status" className="text-sm text-muted">No matching designs. Try another search or filter.</p>}
      {error ? <Alert tone="danger">Couldn’t load your designs. <Button variant="outline" size="sm" onClick={() => mutate()}>Try again</Button></Alert> : !data ? <Skeleton className="h-64" /> : (
        <>
          {recommended.length > 0 && <section aria-label="Suggested designs"><h2 className="font-semibold text-ink">Suggested for your teaching</h2><p className="mb-3 mt-1 text-sm text-muted">Based on your selected subjects, grades and curriculum{data.context?.school_name ? ` for ${data.context.school_name}` : ""}. Choose a suggestion or keep your preferred design. Upload a deck to use your school's branding.</p><Grid items={recommended} /></section>}
          {!["builtin", "uae", "suggested"].includes(filter) && (mine.length > 0 ? <section><h2 className="mb-3 font-semibold text-ink">Your templates</h2><Grid items={mine} /></section> : <section className="rounded-2xl border border-dashed border-line-strong p-6 text-center"><h2 className="font-semibold">Your templates</h2><p className="mt-2 text-sm text-muted">Your uploaded designs will appear here. Start with a built-in style or upload your own presentation above.</p></section>)}
          {builtin.length > 0 && filter !== "suggested" && <section><h2 className="mb-3 font-semibold text-ink">Built-in styles</h2><p className="mb-3 text-sm text-muted">Independent classroom designs, including UAE heritage, sustainability and subject themes.</p><Grid items={builtin} /></section>}
        </>
      )}
    </div>
  );
}
