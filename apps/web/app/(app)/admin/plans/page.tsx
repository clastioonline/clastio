"use client";
import { LicensePanel } from "@/components/license-panel";

import { Gift } from "lucide-react";
import { useEffect, useState } from "react";
import { DashHeader, Panel, PillButton } from "@/components/dash";
import { LoadError } from "@/components/load-error";
import { errorMessage, useToast } from "@/components/toast";
import { Field, Input, Select, Skeleton, Textarea } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useCan } from "@/lib/hooks";

/* Limits admins most often tune. -1 means unlimited. */
const LIMITS: { key: string; label: string }[] = [
  { key: "credits", label: "Credits/mo" },
  { key: "max_lectures", label: "Lessons/unit" },
  { key: "classes", label: "Classes" },
  { key: "style_profiles", label: "Designs" },
  { key: "ai_images", label: "AI images/mo" },
  { key: "whatsapp_messages", label: "WhatsApp/mo" },
  { key: "storage_mb", label: "Storage MB" },
  { key: "media_credits_monthly", label: "Media cr./mo" },
];

function PlanEditor({ plan, onSaved, readOnly = false }: { plan: any; onSaved: () => void; readOnly?: boolean }) {
  const { notify } = useToast();
  const [p, setP] = useState(plan);
  const [busy, setBusy] = useState(false);
  useEffect(() => setP(plan), [plan]);
  const save = async () => {
    setBusy(true);
    try {
      await api(`/admin/plans/${p.code}`, { method: "PUT", body: {
        name: p.name, price_monthly_aed: Number(p.price_monthly_aed), price_annual_aed: Number(p.price_annual_aed),
        limits: p.limits, features: p.features, active: p.active } });
      notify({ tone: "success", title: `${p.name} saved`, body: "New prices and limits apply immediately. Update the matching product price in your payment dashboard too." });
      onSaved();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const free = p.code === "free";
  return (
    <Panel title={<span className="flex flex-wrap items-baseline gap-2">{p.name}<span className="text-sm font-normal text-muted">{p.code}</span></span>}
      action={!free && !readOnly && (
        <label className="flex shrink-0 items-center gap-2 text-sm text-ink-2">
          <input type="checkbox" className="h-4 w-4 accent-[var(--color-brand-600)]" checked={p.active !== false} onChange={(e) => setP({ ...p, active: e.target.checked })} />On sale
        </label>
      )}>
      <fieldset className="space-y-4" disabled={readOnly}>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Name"><Input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} /></Field>
          <Field label="AED / month"><Input type="number" min={0} disabled={free} value={p.price_monthly_aed} onChange={(e) => setP({ ...p, price_monthly_aed: e.target.value })} /></Field>
          <Field label="AED / year"><Input type="number" min={0} disabled={free} value={p.price_annual_aed} onChange={(e) => setP({ ...p, price_annual_aed: e.target.value })} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {LIMITS.map((l) => (
            <Field key={l.key} label={l.label}>
              <Input type="number" min={-1} value={p.limits[l.key] ?? 0}
                onChange={(e) => setP({ ...p, limits: { ...p.limits, [l.key]: Number(e.target.value) } })} />
            </Field>
          ))}
        </div>
        <Field label="Features shown on pricing" hint="One per line">
          <Textarea className="min-h-[132px]" value={(p.features || []).join("\n")} onChange={(e) => setP({ ...p, features: e.target.value.split("\n").map((x) => x.trim()).filter(Boolean) })} />
        </Field>
        {!readOnly && <div className="flex justify-end"><PillButton onClick={save} disabled={busy}>{busy ? "Saving…" : "Save plan"}</PillButton></div>}
      </fieldset>
    </Panel>
  );
}

export default function AdminPlans() {
  const { notify } = useToast();
  const can = useCan();
  const canManageTrial = can("settings.modify");
  const { data, error, mutate } = useApi<any>("/admin/plans");
  const { data: settings, error: settingsError, mutate: mutateSettings } = useApi<any>(canManageTrial ? "/admin/settings" : null);
  const [trial, setTrial] = useState<any>(null);
  useEffect(() => { if (settings) setTrial(settings.trial); }, [settings]);

  const saveTrial = async () => {
    try {
      await api("/admin/settings/trial", { method: "PUT", body: { ...trial, days: Number(trial.days) } });
      notify({ tone: "success", title: "Trial saved", body: "Duration applies to new trials; allowance limits also apply to active trials." });
      mutateSettings();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };

  if (error) return <LoadError label="plans" retry={mutate} />;
  if (!data) return <Skeleton className="h-96 rounded-3xl" />;
  return (
    <div className="space-y-5">
      <DashHeader title="Plans & trial" subtitle="What teachers can buy, what each plan includes, and the free trial teachers can choose. -1 means unlimited." />
      <LicensePanel admin />
      {canManageTrial && settingsError && <LoadError label="trial settings" retry={mutateSettings} />}
      {canManageTrial && !settingsError && !trial && <Skeleton className="h-40 rounded-3xl" />}
      {canManageTrial && trial && <section className="ui-hero rounded-3xl bg-brand-800 p-6 text-white">
        <div className="flex flex-wrap items-end gap-4">
          <div className="me-auto">
            <h2 className="flex items-center gap-2 text-xl font-semibold"><Gift className="h-5 w-5" />Free trial for new teachers</h2>
            <p className="mt-1 max-w-xl text-sm text-white/80">No card needed. When it ends the teacher moves to the Free plan and is invited to upgrade inside the app.</p>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4" checked={!!trial.enabled} onChange={(e) => setTrial({ ...trial, enabled: e.target.checked })} />Trial on</label>
          <label className="text-sm">Plan
            <Select className="mt-1 w-44 text-ink" value={trial.plan} onChange={(e) => setTrial({ ...trial, plan: e.target.value })}>
              {data.items.filter((p: any) => p.code !== "free").map((p: any) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </Select>
          </label>
          <label className="text-sm">Days
            <Input className="mt-1 w-24 text-ink" type="number" min={0} max={90} value={trial.days} onChange={(e) => setTrial({ ...trial, days: e.target.value })} />
          </label>
          {[["credits", "Trial credits"], ["ai_images", "AI images"], ["whatsapp_messages", "WhatsApp messages"]].map(([key, label]) => <label key={key} className="text-sm">{label}<Input className="mt-1 w-24 text-ink" type="number" min={0} max={100000} value={trial[key] ?? 0} onChange={(e) => setTrial({...trial, [key]: Number(e.target.value)})} /></label>)}
          <button onClick={saveTrial} className="h-10 rounded-full bg-white px-5 text-sm font-semibold text-brand-800 hover:bg-white/90">Save trial</button>
        </div>
      </section>}
      <div className="grid gap-5 xl:grid-cols-2">
        {data.items.map((p: any) => <PlanEditor key={p.code} plan={p} onSaved={mutate} readOnly={!can("billing.modify")} />)}
      </div>
    </div>
  );
}
