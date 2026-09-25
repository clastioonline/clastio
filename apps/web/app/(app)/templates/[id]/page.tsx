"use client";

import { CircleCheck, Trash } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, Field, Input, PageHeader, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { LAYOUT_LABELS } from "@/lib/utils";

const COLOR_KEYS = [["primary", "Primary"], ["secondary", "Accent"], ["background", "Background"], ["text", "Body text"], ["title", "Titles"], ["card_bg", "Cards"]];

export default function TemplateDetail() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(`/templates/${id}`);
  const [colors, setColors] = useState<Record<string, string>>({});
  const [fonts, setFonts] = useState<Record<string, string>>({});
  const [typo, setTypo] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!data) return;
    setColors(data.colors || {});
    setFonts(data.fonts || {});
    setTypo({ title_pt: data.typography?.title_pt, body_pt: data.typography?.body_pt });
  }, [data]);
  if (!data) return <Skeleton className="h-96" />;

  const save = async () => {
    setBusy(true);
    try {
      await api(`/templates/${id}`, { method: "PATCH", body: { colors, fonts, typography: typo } });
      notify({ tone: "success", title: "Template updated", body: "Previews refreshed." });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const makeDefault = async () => {
    await api(`/templates/${id}/default`, { method: "POST" });
    notify({ tone: "success", title: "Default template set" });
    mutate();
  };
  const remove = async () => {
    if (!confirm("Delete this template?")) return;
    await api(`/templates/${id}`, { method: "DELETE" });
    router.push("/templates");
  };
  const analysis = data.analysis || {};
  const cs = data.content_style || {};

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={data.builtin ? "Built-in style" : data.mode === "native" ? "From your PowerPoint (exact master)" : "Reconstructed from PDF"}
        title={data.name}
        actions={
          <>
            {data.is_default ? <Badge tone="success"><CircleCheck className="h-3.5 w-3.5" /> Default</Badge> : <Button variant="outline" onClick={makeDefault}>Use as default</Button>}
            {!data.builtin && <Button variant="ghost" size="icon" onClick={remove} aria-label="Delete"><Trash className="h-4 w-4" /></Button>}
          </>
        } />
      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <Card className="p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {data.previews.map((p: string, i: number) => (
              <div key={i} className="aspect-[16/9] overflow-hidden rounded-xl border border-line bg-surface-2"><img src={p} alt={`Preview ${i + 1}`} className="h-full w-full object-cover" /></div>
            ))}
          </div>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Design system" subtitle={data.builtin ? "Built-in templates can't be edited — upload your own deck to customise." : "Detected from your slides. Adjust if something looks off."} />
            <div className="space-y-4 p-5">
              <div className="grid grid-cols-2 gap-3">
                {COLOR_KEYS.map(([k, label]) => (
                  <label key={k} className="flex items-center gap-2 text-sm">
                    <input type="color" value={colors[k] || "#000000"} disabled={data.builtin} onChange={(e) => setColors({ ...colors, [k]: e.target.value.toUpperCase() })}
                      className="h-8 w-8 cursor-pointer rounded-lg border border-line bg-transparent" />
                    <span><span className="block text-ink">{label}</span><span className="text-xs text-muted">{colors[k]}</span></span>
                  </label>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Heading font"><Input value={fonts.heading || ""} disabled={data.builtin} onChange={(e) => setFonts({ ...fonts, heading: e.target.value })} /></Field>
                <Field label="Body font"><Input value={fonts.body || ""} disabled={data.builtin} onChange={(e) => setFonts({ ...fonts, body: e.target.value })} /></Field>
                <Field label="Title size (pt)"><Input type="number" value={typo.title_pt || 36} disabled={data.builtin} onChange={(e) => setTypo({ ...typo, title_pt: Number(e.target.value) })} /></Field>
                <Field label="Body size (pt)"><Input type="number" value={typo.body_pt || 20} disabled={data.builtin} onChange={(e) => setTypo({ ...typo, body_pt: Number(e.target.value) })} /></Field>
              </div>
              {!data.builtin && <Button className="w-full" onClick={save} loading={busy}>Save & refresh previews</Button>}
            </div>
          </Card>
          {!data.builtin && (
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
