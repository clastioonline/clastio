"use client";

import { useEffect, useState } from "react";
import { AiBudgetControls } from "@/components/ai-budget-controls";
import { BarList, compact } from "@/components/charts";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, CardHeader, Field, Input, PageHeader, Skeleton, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";

const TIERS = [
  ["planning", "Course planning (strong reasoning)"], ["content", "Lesson & slide writing"], ["fast", "Routing, quick rewrites"],
  ["qc", "Quality checks"], ["vision", "Vision (PDF analysis)"], ["embedding", "Embeddings"], ["image", "Image generation"],
];

export default function AiCosts() {
  const { user } = useMe();
  const { notify } = useToast();
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const { data } = useApi<any>(user?.role === "admin" ? `/admin/ai-costs?days=${days}` : null);
  const { data: settings, mutate } = useApi<any>(user?.role === "admin" ? "/admin/settings" : null);
  const { data: health } = useApi<any>("/health");
  const [routing, setRouting] = useState<Record<string, string>>({});
  const [costs, setCosts] = useState<Record<string, number>>({});
  useEffect(() => {
    if (settings) {
      setRouting(settings.model_routing || {});
      setCosts(settings.credit_costs || {});
    }
  }, [settings]);

  if (user && user.role !== "admin") return <p className="text-muted">Admins only.</p>;
  if (!data || !settings) return <Skeleton className="h-96" />;
  const total = data.by_model.reduce((a: number, m: any) => a + m.cost_usd, 0);
  const calls = data.by_model.reduce((a: number, m: any) => a + m.calls, 0);
  const cached = data.by_model.reduce((a: number, m: any) => a + m.cached_tokens, 0);
  const input = data.by_model.reduce((a: number, m: any) => a + m.input_tokens, 0);

  const save = async (key: string, value: any) => {
    try {
      await api(`/admin/settings/${key}`, { method: "PUT", body: value });
      notify({ tone: "success", title: "Saved", body: key === "model_routing" ? "New requests use the updated routing immediately." : undefined });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="AI costs & model routing" subtitle="Cheaper models for routine work, stronger ones only for planning. Every call is metered." />
      <AiBudgetControls />
      <Tabs value={days} onChange={setDays} tabs={[{ value: "7", label: "7 days" }, { value: "30", label: "30 days" }, { value: "90", label: "90 days" }]} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Total AI cost" value={`$${total.toFixed(2)}`} />
        <Stat label="Calls" value={compact(calls)} />
        <Stat label="Prompt-cache hit rate" value={`${input + cached ? Math.round((cached / (input + cached)) * 100) : 0}%`} hint="Share of input tokens served from cache" />
        <Stat label="Live providers" value={health?.ai_providers?.length || 0} hint={health?.ai_mode === "offline" ? "Offline demo mode" : health?.ai_providers?.join(", ")} />
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card><CardHeader title="Cost by task (USD)" /><div className="p-5"><BarList items={data.by_task.map((t: any) => ({ name: t.task, value: t.cost_usd, hint: `${t.calls} calls` }))} format={(v) => `$${v.toFixed(v < 1 ? 3 : 2)}`} empty="No AI calls in this period" /></div></Card>
        <Card><CardHeader title="Cost by model (USD)" /><div className="p-5"><BarList items={data.by_model.map((m: any) => ({ name: `${m.provider} · ${m.model}`, value: m.cost_usd, hint: `${m.calls} calls, ${m.failures} failed` }))} format={(v) => `$${v.toFixed(v < 1 ? 3 : 2)}`} empty="No AI calls in this period" /></div></Card>
      </div>
      <Card>
        <CardHeader title="Calls by model" />
        <div className="overflow-x-auto p-2">
          <table className="w-full text-sm">
            <thead className="text-xs uppercase text-muted"><tr>{["Model", "Calls", "Input", "Output", "Cached", "Avg latency", "Failures", "Cost"].map((h) => <th key={h} className="px-3 py-2 text-start">{h}</th>)}</tr></thead>
            <tbody className="divide-y divide-line tabular-nums">
              {data.by_model.map((m: any) => (
                <tr key={m.provider + m.model}><td className="px-3 py-2 font-medium text-ink">{m.provider} · {m.model}</td><td className="px-3 py-2">{compact(m.calls)}</td><td className="px-3 py-2">{compact(m.input_tokens)}</td>
                  <td className="px-3 py-2">{compact(m.output_tokens)}</td><td className="px-3 py-2">{compact(m.cached_tokens)}</td><td className="px-3 py-2">{m.avg_latency_ms} ms</td><td className="px-3 py-2">{m.failures}</td><td className="px-3 py-2">${m.cost_usd.toFixed(4)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Model routing" subtitle="provider:model per task tier. Leave blank to use the server default (Anthropic Claude first, then OpenAI, then Gemini)." />
          <div className="space-y-3 p-5">
            {TIERS.map(([k, label]) => (
              <Field key={k} label={label}><Input value={routing[k] || ""} placeholder={k === "planning" ? "anthropic:claude-opus-5" : k === "embedding" ? "openai:text-embedding-3-small" : "default"} onChange={(e) => setRouting({ ...routing, [k]: e.target.value })} /></Field>
            ))}
            <Button onClick={() => save("model_routing", Object.fromEntries(Object.entries(routing).filter(([, v]) => v)))}>Save routing</Button>
          </div>
        </Card>
        <Card>
          <CardHeader title="Credit costs" subtitle="What each artefact costs against plan limits" />
          <div className="grid grid-cols-2 gap-3 p-5">
            {Object.entries(costs).map(([k, v]) => (
              <Field key={k} label={k.replace(/_/g, " ")}><Input type="number" min={0} value={v} onChange={(e) => setCosts({ ...costs, [k]: Number(e.target.value) })} /></Field>
            ))}
            <div className="col-span-2"><Button onClick={() => save("credit_costs", costs)}>Save credit costs</Button></div>
          </div>
          <div className="px-5 pb-5"><Alert tone="neutral">Plan limits (credits per month, classes, WhatsApp messages…) are edited per plan via the admin API or the plans table.</Alert></div>
        </Card>
      </div>
    </div>
  );
}
