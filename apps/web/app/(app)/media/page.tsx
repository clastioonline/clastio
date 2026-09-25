"use client";

import { Clapperboard, Download, ImageIcon, Info, Sparkles, Trash, WandSparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Badge, Button, Card, CardHeader, Chips, EmptyState, Field, PageHeader, Select, Skeleton, Spinner, Tabs, Textarea } from "@/components/ui";
import { api, formatDate } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";

type Item = {
  id: string; kind: "image" | "video"; prompt: string; style: string | null; aspect: string; seconds: number | null;
  status: "queued" | "running" | "ready" | "failed"; credits: number; mime_type: string | null; url: string | null;
  error: string | null; demo: boolean; model: string | null; created_at: string;
};

const pending = (d: any) => (d?.items || []).some((i: Item) => i.status === "queued" || i.status === "running");

function MediaPreview({ item }: { item: Item }) {
  const ratio = item.aspect === "9:16" ? "aspect-[9/16]" : item.aspect === "1:1" ? "aspect-square" : "aspect-video";
  return (
    <div className={cn("relative overflow-hidden rounded-xl bg-surface-2", ratio)}>
      {item.status === "ready" && item.url ? (
        item.mime_type?.startsWith("video/") ? (
          <video src={item.url} controls playsInline className="h-full w-full object-cover" />
        ) : (
          <img src={item.url} alt={item.prompt} className="h-full w-full object-cover" loading="lazy" />
        )
      ) : item.status === "failed" ? (
        <div className="grid h-full place-items-center p-4 text-center text-sm text-danger-700">{item.error || "Generation failed"}</div>
      ) : (
        <div className="grid h-full place-items-center text-sm text-muted">
          <div className="flex flex-col items-center gap-2"><Spinner />{item.kind === "video" ? "Generating video… this can take a few minutes" : "Generating image…"}</div>
        </div>
      )}
      <div className="absolute start-2 top-2 flex gap-1">
        <Badge tone="brand" className="bg-surface/90 backdrop-blur">AI-generated</Badge>
        {item.demo && <Badge tone="accent" className="bg-surface/90 backdrop-blur">Demo</Badge>}
      </div>
    </div>
  );
}

function Studio() {
  const params = useSearchParams();
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/media", { refreshInterval: (d) => (pending(d) ? 3000 : 0) });
  const [kind, setKind] = useState<"image" | "video">("image");
  const [prompt, setPrompt] = useState("");
  const [style, setStyle] = useState("photorealistic");
  const [aspect, setAspect] = useState("16:9");
  const [seconds, setSeconds] = useState(4);
  const [busy, setBusy] = useState<string | null>(null);

  if (!data) return <Skeleton className="h-96" />;
  const cost = kind === "image" ? data.pricing.image : data.pricing.video_per_second * seconds;
  const short = data.balance < cost;

  const generate = async () => {
    setBusy("generate");
    try {
      await api("/media", { body: { kind, prompt, style, aspect, seconds: kind === "video" ? seconds : null } });
      setPrompt("");
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't start", body: errorMessage(e) });
    } finally {
      setBusy(null);
    }
  };
  const buy = async (code: string) => {
    setBusy(code);
    try {
      const r = await api<{ url: string }>(`/media/packs/${code}/checkout`, { method: "POST" });
      window.location.href = r.url;
    } catch (e) {
      notify({ tone: "error", title: "Checkout unavailable", body: errorMessage(e) });
      setBusy(null);
    }
  };
  const remove = async (id: string) => {
    await api(`/media/${id}`, { method: "DELETE" });
    mutate();
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Media studio" eyebrow="Add-on"
        subtitle="Create images and short videos for your lessons. Everything you make is labelled as AI-generated."
        actions={<div className="flex items-center gap-2 rounded-xl border border-line bg-surface px-3 py-2 text-sm">
          <Sparkles className="h-4 w-4 text-accent-500" /><span className="font-semibold tabular-nums text-ink">{data.balance}</span><span className="text-muted">media credits</span>
        </div>} />
      {params.get("status") === "success" && <Alert tone="success" title="Payment received">Your credits appear here as soon as the payment is confirmed (usually within a minute).</Alert>}
      {!data.enabled && <Alert tone="warn" title="The media studio is switched off">An administrator has paused image and video generation.</Alert>}

      <div className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
        <Card>
          <CardHeader icon={<WandSparkles className="h-5 w-5" />} title="Create"
            action={<Tabs value={kind} onChange={(v) => { setKind(v); if (v === "video" && aspect === "1:1") setAspect("16:9"); }}
              tabs={[{ value: "image", label: <span className="flex items-center gap-1.5"><ImageIcon className="h-4 w-4" />Image</span> },
                { value: "video", label: <span className="flex items-center gap-1.5"><Clapperboard className="h-4 w-4" />Video</span> }]} />} />
          <div className="space-y-4 p-5">
            <Field label="Describe it">
              <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} maxLength={1000} className="min-h-[96px]"
                placeholder={kind === "image" ? "e.g. Students measuring plant growth in a sunny school greenhouse" : "e.g. Time-lapse of a bean seed sprouting in soil"} />
            </Field>
            <Field label="Style"><Chips options={data.styles.map((s: string) => ({ value: s, label: s[0].toUpperCase() + s.slice(1) }))} value={style} onChange={setStyle} /></Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Shape">
                <Select value={aspect} onChange={(e) => setAspect(e.target.value)}>
                  <option value="16:9">Landscape 16:9 (slides)</option>
                  <option value="9:16">Portrait 9:16</option>
                  {kind === "image" && <option value="1:1">Square 1:1</option>}
                </Select>
              </Field>
              {kind === "video" && (
                <Field label="Length">
                  <Select value={seconds} onChange={(e) => setSeconds(Number(e.target.value))}>
                    {data.video_seconds.map((s: number) => <option key={s} value={s}>{s} seconds</option>)}
                  </Select>
                </Field>
              )}
            </div>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
              <div className="text-sm text-muted">Costs <span className="font-semibold text-ink">{cost} credits</span>{short && <span className="text-danger-700"> · you have {data.balance}</span>}</div>
              <Button onClick={generate} loading={busy === "generate"} disabled={!data.enabled || prompt.trim().length < 3 || short}>
                <WandSparkles className="h-4 w-4" /> Generate {kind}
              </Button>
            </div>
            <p className="flex gap-2 text-xs text-muted"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />Files keep the provider's AI provenance data and are named as AI-generated. Avoid real people's names or likenesses; requests that break the provider's policies are declined and refunded.</p>
          </div>
        </Card>

        <Card>
          <CardHeader icon={<Sparkles className="h-5 w-5" />} title="Media credits" subtitle={`Image ${data.pricing.image} credits · video ${data.pricing.video_per_second} credits per second`} />
          <div className="grid gap-3 p-5 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
            {data.packs.map((p: any, i: number) => (
              <div key={p.code} className={cn("flex flex-col rounded-2xl border p-4", i === 1 ? "border-brand-300 bg-brand-50" : "border-line")}>
                <div className="text-sm font-medium text-ink-2">{p.name}</div>
                <div className="mt-1 text-2xl font-semibold tabular-nums text-ink">{p.credits}<span className="ms-1 text-sm font-normal text-muted">credits</span></div>
                <div className="mt-0.5 text-sm text-muted">AED {p.price_aed}</div>
                <Button className="mt-3" size="sm" variant={i === 1 ? "primary" : "outline"} loading={busy === p.code}
                  disabled={!data.online_payments} onClick={() => buy(p.code)}>Buy</Button>
              </div>
            ))}
          </div>
          {!data.online_payments && <p className="px-5 pb-5 text-xs text-muted">Online payment isn't set up yet. Ask your administrator to add credits.</p>}
        </Card>
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold text-ink">Your media</h2>
        {data.items.length ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((m: Item) => (
              <Card key={m.id} className="p-3">
                <MediaPreview item={m} />
                <div className="mt-3 flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-sm text-ink">{m.prompt}</p>
                    <p className="mt-1 text-xs text-muted">{m.kind === "video" ? `${m.seconds}s video` : "Image"} · {m.style || "no style"} · {m.credits} credits · {formatDate(m.created_at)}</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    {m.url && <Button size="icon" variant="ghost" href={m.url} aria-label="Download"><Download className="h-4 w-4" /></Button>}
                    {(m.status === "ready" || m.status === "failed") && <Button size="icon" variant="ghost" aria-label="Delete" onClick={() => remove(m.id)}><Trash className="h-4 w-4" /></Button>}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState icon={<ImageIcon className="h-6 w-6" />} title="Nothing yet" description="Your generated images and videos appear here." />
        )}
      </div>
    </div>
  );
}

export default function MediaPage() {
  return <Suspense><Studio /></Suspense>;
}
