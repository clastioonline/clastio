"use client";

import { useEffect, useState } from "react";
import { Alert, Button, Card, CardHeader, Field, Input, Stat, Textarea, Toggle } from "@/components/ui";
import { errorMessage, useToast } from "@/components/toast";
import { api, ApiError } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const labels: Record<string, string> = {
  daily_usd: "Platform daily limit (USD)", monthly_usd: "Platform monthly limit (USD)",
  user_monthly_usd: "Per user monthly limit (USD)", job_usd: "Per job limit (USD)", call_usd: "Per call limit (USD)",
  max_calls_per_job: "Maximum calls per job", max_input_bytes: "Maximum input bytes", max_output_tokens: "Maximum output tokens",
};

export function AiBudgetControls() {
  const { data, error, mutate } = useApi<any>("/admin/ai-budget");
  const { notify } = useToast();
  const [policy, setPolicy] = useState<any>(null);
  const [cards, setCards] = useState("{}");
  const [saveError, setSaveError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState("");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  useEffect(() => {
    if (data) { setPolicy(data.policy); setCards(JSON.stringify(data.rate_cards, null, 2)); }
  }, [data]);
  async function save() {
    setBusy(true);
    setSaveError("");
    try {
      const parsed = JSON.parse(cards);
      await api("/admin/settings/ai_rate_cards", { method: "PUT", body: parsed });
      await api("/admin/settings/ai_budget", { method: "PUT", body: policy });
      notify({ tone: "success", title: "AI spending controls saved" });
      mutate();
    } catch (e) {
      const details = e instanceof ApiError && Array.isArray(e.details)
        ? e.details.map((issue: any) => `${(issue.loc || []).join(".")}: ${issue.msg || "Invalid value"}`).join("; ") : "";
      const message = [errorMessage(e), details].filter(Boolean).join(" ");
      setSaveError(message);
      notify({ tone: "error", title: "Couldn't save controls", body: message });
    }
    finally { setBusy(false); }
  }
  async function reconcile() {
    setBusy(true);
    try {
      await api(`/admin/ai-budget/${selected}/reconcile`, { body: { amount_usd: Number(amount), reference } });
      setSelected(""); setAmount(""); setReference(""); mutate();
      notify({ tone: "success", title: "Charge reconciled", body: "The adjustment is recorded in the audit log." });
    } catch (e) { notify({ tone: "error", title: "Couldn't reconcile charge", body: errorMessage(e) }); }
    finally { setBusy(false); }
  }
  if (error) return <Alert tone="danger">Spending controls could not be loaded. <button onClick={() => mutate()}>Retry</button></Alert>;
  if (!data || !policy) return <p className="text-muted">Loading spending controls…</p>;
  return <Card>
    <CardHeader title="AI spending controls" subtitle="Funds are reserved before paid calls. Teacher credits are managed separately." />
    <div className="space-y-5 p-5 min-w-0">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Settled this month" value={`$${data.spent_usd.toFixed(4)}`} />
        <Stat label="Held for calls" value={`$${data.held_usd.toFixed(4)}`} />
        <Stat label="Available budget" value={`$${data.remaining_usd.toFixed(2)}`} />
        <Stat label="Monthly forecast" value={`$${data.forecast_usd.toFixed(2)}`} hint="Based on settled spend; excludes holds" />
      </div>
      <p className="text-sm text-muted">Input: {data.tokens.input_tokens.toLocaleString()} · Output: {data.tokens.output_tokens.toLocaleString()} · Cache reads: {data.tokens.cached_tokens.toLocaleString()} · Cache writes: {data.tokens.cache_write_tokens.toLocaleString()} · Reasoning (included in output): {data.tokens.reasoning_tokens.toLocaleString()} · Settled failed calls: ${data.failed_cost_usd.toFixed(4)}</p>
      {data.alert !== "normal" && <Alert tone="warn">{data.alert === "limit" ? "Monthly spending allowance reached." : "At least 80% of the monthly allowance is spent or held."}</Alert>}
      <Toggle checked={policy.live_enabled} onChange={(v) => setPolicy({ ...policy, live_enabled: v })} label="Allow paid AI calls" description="Requires approved prices and server API keys. Offline demo mode stays offline." />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Object.entries(labels).map(([key, label]) => <Field key={key} label={label}>
          <Input type="number" min={0} step={key.endsWith("usd") ? "0.01" : "1"} value={policy[key]} onChange={(e) => setPolicy({ ...policy, [key]: Number(e.target.value) })} />
        </Field>)}
      </div>
      <Field label="Approved model price cards (JSON)">
        <Textarea rows={8} className="font-mono text-xs" value={cards} onChange={(e) => setCards(e.target.value)} />
      </Field>
      <p className="text-xs text-muted">Key each card by provider:model. Required fields: input, output, cached and cache_write (USD per million tokens), ceiling_usd (maximum cost of one allowed request), and source (pricing reference). Use verified rates covering cache writes and long contexts. Unknown models are blocked. Media and missing usage keep their full hold until reconciliation.</p>
      {saveError && <Alert tone="danger" title="Spending controls were not fully saved"><p role="alert" className="break-words">{saveError}</p></Alert>}
      <Button loading={busy} onClick={save}>Save spending controls</Button>
      <p className="text-xs text-muted">This ledger covers calls made since these controls were installed. Limits reset at UTC midnight or month start; unresolved holds carry forward. Compare charges with provider invoices before releasing holds.</p>
      {data.unresolved.length > 0 && <div className="space-y-3">
        <h3 className="font-semibold">Calls awaiting settlement</h3>
        <div className="max-h-64 space-y-2 overflow-y-auto">
          {data.unresolved.map((call: any) => <div key={call.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-line p-3 text-sm">
            <span className="min-w-0 break-all">{call.provider} · {call.model} · {call.status} · ${call.reserved_usd.toFixed(4)}</span>
            <Button variant="ghost" onClick={() => setSelected(call.id)}>Review charge</Button>
          </div>)}
        </div>
        {selected && <div className="space-y-3 rounded-lg border border-line p-3">
          <p className="break-all text-xs">Call {selected}. Enter the confirmed provider charge. Active jobs cannot be reconciled; unfinished calls must be at least 24 hours old.</p>
          <Field label="Confirmed charge (USD)"><Input type="number" min={0} step="0.000001" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
          <Field label="Invoice or provider request reference"><Input value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
          <Button loading={busy} disabled={amount === "" || reference.trim().length < 10} onClick={reconcile}>Record confirmed charge</Button>
        </div>}
      </div>}
    </div>
  </Card>;
}
