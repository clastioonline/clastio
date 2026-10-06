"use client";

import { CircleCheck, Trash } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useSWRConfig } from "swr";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, Field, Input, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { TemplatePreview } from "@/components/template-preview";
import { useApi, useJob } from "@/lib/hooks";
import { LAYOUT_LABELS } from "@/lib/utils";

const COLOR_KEYS = [["primary", "Primary"], ["secondary", "Accent"], ["background", "Background"], ["text", "Body text"], ["title", "Titles"], ["card_bg", "Cards"]];

export default function TemplateDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { notify } = useToast();
  const { mutate: refreshCache } = useSWRConfig();
  const { data, error, mutate } = useApi<any>(`/templates/${id}`);
  const [name, setName] = useState("");
  const [colors, setColors] = useState<Record<string, string>>({});
  const [fonts, setFonts] = useState<Record<string, string>>({});
  const [typo, setTypo] = useState<Record<string, number>>({});
  const [jobId, setJobId] = useState<string | null>(null);
  const job = useJob(jobId || (data?.job && ["queued", "running"].includes(data.job.status) ? data.job.id : null), async () => { setJobId(null); await mutate(); });
  const refreshing = !!jobId || ["queued", "running"].includes(job?.status || data?.job?.status);
  const editable = data?.can_edit ?? !data?.builtin;
  const [action, setAction] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!data) return;
    setName(data.name || "");
    setColors(data.colors || {});
    setFonts(data.fonts || {});
    setTypo({ title_pt: data.typography?.title_pt, body_pt: data.typography?.body_pt });
  }, [data]);
  if (error) return <div className="space-y-4"><Button href="/templates" variant="outline">Back to designs</Button><Alert tone="danger">This design could not be loaded. It may have been removed or you may not have access.</Alert><Button onClick={() => mutate()}>Try again</Button></div>;
  if (!data) return <Skeleton className="h-96" />;

  const save = async () => {
    setBusy(true);
    try {
      const result = await api<{ job_id: string }>(`/templates/${id}`, { method: "PATCH", body: { name, colors, fonts, typography: typo } });
      setJobId(result.job_id);
      notify({ tone: "success", title: "Design saved", body: "Previews are refreshing in the background. You can leave this page." });
      await mutate();
      await refreshCache("/templates");
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const makeDefault = async () => {
    setAction("default");
    try {
      await api(`/templates/${id}/default`, { method: "POST" });
      notify({ tone: "success", title: "Default template set" });
      await mutate();
      await refreshCache("/templates");
    } catch (e) { notify({ tone: "error", title: "Couldn’t set default", body: errorMessage(e) }); }
    finally { setAction(null); }
  };
  const remove = async () => {
    if (!confirm("Delete this template?")) return;
    setAction("delete");
    try {
      await api(`/templates/${id}`, { method: "DELETE" });
      await refreshCache("/templates");
      router.push("/templates");
    } catch (e) { notify({ tone: "error", title: "Couldn’t delete design", body: errorMessage(e) }); }
    finally { setAction(null); }
  };
  const analysis = data.analysis || {};
  const cs = data.content_style || {};

  return (
    <div className="min-w-0 space-y-6">
      <Button href="/templates" variant="ghost">← All designs</Button>
      <PageHeader eyebrow={data.builtin ? "Built-in style" : data.mode === "native" ? "From your PowerPoint (exact master)" : "Reconstructed from PDF"}
        title={data.name} subtitle={data.description}
        actions={
          <>
            <Button href={`/projects/new?template=${encodeURIComponent(id)}`}>Use for a lesson</Button>
            {data.is_default ? <Badge tone="success"><CircleCheck className="h-3.5 w-3.5" /> Default</Badge> : <Button variant="outline" onClick={makeDefault} loading={action === "default"} disabled={!!action}>Use as default</Button>}
            {editable && <Button variant="ghost" size="icon" onClick={remove} disabled={!!action || busy || refreshing} aria-label="Delete template"><Trash className="h-4 w-4" /></Button>}
          </>
        } />
      {data.font_warnings?.length > 0 && <Alert tone="warn" title="Some fonts may be substituted">{data.font_warnings.filter((warning: { font?: string }) => warning.font).map((warning: { font: string }) => warning.font).join(", ") || "Font availability could not be checked"}. Your previews may wrap text differently. Ask your school administrator to install the licensed fonts.</Alert>}
      {data.tags?.length > 0 && <div className="flex flex-wrap gap-1.5">{data.tags.map((tag: string) => <Badge key={tag}>{tag}</Badge>)}</div>}
      {refreshing && <Alert>Refreshing your previews. You can leave this page and follow progress in <a href="/activity" className="underline">Activity</a>.</Alert>}
      {data.design_inspection?.slides_inspected > 0 && <Card>
        <CardHeader title="Uploaded design inspection" subtitle={`${data.design_inspection.slides_inspected} slides structurally inspected · ${data.design_inspection.slides_rendered || 0} rendered · ${data.design_inspection.slides_ai_inspected || 0} inspected by AI.`} />
        <div className="space-y-3 p-5 text-sm">
          <p>Native masters, layouts and recurring decorations form your reusable design. New tables use the dominant uploaded table formatting; supported charts reuse formatting for their chart type.</p>
          <div className="flex flex-wrap gap-2">
            {data.design_inspection.table_style_reused && <Badge>Table formatting detected</Badge>}
            {data.design_inspection.chart_styles_reused.map((kind: string) => <Badge key={kind}>{kind} chart formatting detected</Badge>)}
          </div>
          <details>
            <summary className="cursor-pointer font-medium">Inspect each source slide</summary>
            <div className="mt-3 space-y-3">
              {data.design_inspection.source_previews?.map((page: any) => {
                const detail = data.design_inspection.page_details?.find((item: any) => item.number === page.number);
                return <div key={page.number} className="rounded-lg border border-line p-3 space-y-2">
                  <p className="font-medium">Original slide {page.number}</p>
                  <a href={page.url} target="_blank" rel="noreferrer"><img src={page.url} alt={`Complete original slide ${page.number}`} loading="lazy" className="w-full rounded" /></a>
                  {detail && <><p>{detail.design_summary}</p><p>{detail.content_structure}</p><p className="text-muted">{detail.engagement_guidance}</p></>}
                </div>;
              })}
              {data.design_inspection.slides.map((slide: any) => <div key={slide.slide} className="rounded-lg border border-line p-3">
                <p className="font-medium">Slide {slide.slide} · {slide.layout}</p>
                <p className="text-muted">{slide.tables} tables · {slide.charts} charts · {slide.pictures} pictures</p>
                {slide.fonts.length > 0 && <p>Explicit fonts: {slide.fonts.join(", ")}</p>}
              </div>)}
            </div>
          </details>
          <p className="text-muted">Image-based tables and charts remain images. Fonts unavailable on the rendering server may use a substitute. PDF designs are reconstructed rather than imported as native PowerPoint objects.</p>
        </div>
      </Card>}
      {data.job?.status === "failed" && !refreshing && <Alert tone="danger">Your design is saved, but previews could not refresh. Save again to retry.</Alert>}
      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Card className="min-w-0 self-start p-3 sm:p-4">
          <h2 className="mb-3 font-semibold">Generated design examples</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {(data.previews?.length ? data.previews : [undefined]).map((p: string | undefined, i: number) => (
              <TemplatePreview key={i} src={p} name={`Preview ${i + 1}`} />
            ))}
          </div>
        </Card>
        <div className="min-w-0 space-y-6">
          <Card>
            <CardHeader title="Design system" subtitle={!editable ? "This design is read-only. Upload your own deck to customise." : "Detected from your slides. Adjust if something looks off."} />
            <div className="space-y-4 p-5">
              <div className="space-y-4 mb-4">
                <Field label="Template name"><Input maxLength={200} value={name} disabled={!editable || busy || refreshing} onChange={(e) => setName(e.target.value)} /></Field>
              </div>
              <div className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
                {COLOR_KEYS.map(([k, label]) => (
                  <label key={k} className="flex items-center gap-2 text-sm">
                    <input type="color" value={colors[k] || "#000000"} disabled={!editable || busy || refreshing} onChange={(e) => setColors({ ...colors, [k]: e.target.value.toUpperCase() })}
                      className="h-10 w-10 shrink-0 cursor-pointer rounded-lg border border-line bg-transparent" />
                    <span><span className="block text-ink">{label}</span><span className="text-xs text-muted">{colors[k]}</span></span>
                  </label>
                ))}
              </div>
              <div className="grid grid-cols-1 gap-3 min-[380px]:grid-cols-2">
                <Field label="Heading font"><Input value={fonts.heading || ""} disabled={!editable || busy || refreshing} onChange={(e) => setFonts({ ...fonts, heading: e.target.value })} /></Field>
                <Field label="Body font"><Input value={fonts.body || ""} disabled={!editable || busy || refreshing} onChange={(e) => setFonts({ ...fonts, body: e.target.value })} /></Field>
                <Field label="Title size (pt)"><Input type="number" min={12} max={60} value={typo.title_pt || 36} disabled={!editable || busy || refreshing} onChange={(e) => setTypo({ ...typo, title_pt: Number(e.target.value) })} /></Field>
                <Field label="Body size (pt)"><Input type="number" min={12} max={60} value={typo.body_pt || 20} disabled={!editable || busy || refreshing} onChange={(e) => setTypo({ ...typo, body_pt: Number(e.target.value) })} /></Field>
              </div>
              {editable && <Button className="w-full" onClick={save} loading={busy} disabled={refreshing || !name.trim() || [typo.title_pt, typo.body_pt].some(v => v != null && (v < 12 || v > 60))}>Save & refresh previews</Button>}
            </div>
          </Card>
          {editable && (
            <Card>
              <CardHeader title="What we learned from your slides" />
              <div className="space-y-3 p-5 text-sm">
                <div className="flex flex-wrap gap-1.5">{(analysis.layouts_found || []).map((l: any) => <Badge key={l.key}>{LAYOUT_LABELS[l.key] || l.key} ×{l.count}</Badge>)}</div>
                {cs.avg_words_per_bullet && <div className="text-ink-2">About {cs.avg_words_per_bullet} words per bullet, {cs.bullets_per_slide?.join("–")} bullets per slide{cs.reading_grade ? `, reading level around grade ${Math.round(cs.reading_grade)}` : ""}.</div>}
                {cs.tone && <div className="text-ink-2">Tone: {cs.tone}</div>}
                <div className="text-muted">{analysis.stats?.decoration_count || 0} recurring design elements (logo, bands, footers) are reused on every slide.</div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
