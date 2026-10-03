"use client";

import { useEffect, useState } from "react";
import { AdminPage, ReasonDialog } from "@/components/admin-kit";
import { Panel } from "@/components/dash";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Field, Input, Skeleton, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

const LIMIT_FIELDS = [["daily_generations", "Generations / day"], ["max_concurrent_jobs", "Jobs at once"], ["max_upload_mb", "Upload MB"]] as const;

export default function AdminSettings() {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>("/admin/settings");
  const [s, setS] = useState<any>(null);
  const [confirmMaint, setConfirmMaint] = useState(false);
  useEffect(() => { if (data) setS(structuredClone(data)); }, [data]);
  if (!s) return <AdminPage title="Settings & flags" perm="settings.modify"><Skeleton className="h-96" /></AdminPage>;
  const save = async (key: string) => {
    try { await api(`/admin/settings/${key}`, { method: "PUT", body: s[key] }); notify({ tone: "success", title: "Saved", body: "Applies within a few seconds and is recorded in the audit log." }); mutate(); }
    catch (e) { notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) }); }
  };
  const sys = s.system;
  const setSys = (patch: any) => setS({ ...s, system: { ...sys, ...patch } });
  const maint = sys.maintenance || {};
  return (
    <AdminPage title="Settings & flags" perm="settings.modify" subtitle="Platform switches, maintenance mode, feature flags and limits. Every change is audited with before and after values.">
      {maint.enabled && <Alert tone="warn" title="Maintenance mode is ON">Teachers see a maintenance message; staff can still use the app.</Alert>}
      <div className="grid gap-5 xl:grid-cols-2">
        <Panel title="Platform" action={<Button size="sm" onClick={() => save("system")}>Save</Button>}>
          <div className="divide-y divide-line">
            <Toggle checked={!!maint.enabled} onChange={(v) => (v ? setConfirmMaint(true) : setSys({ maintenance: { ...maint, enabled: false } }))} label="Maintenance mode" description="Blocks the app for teachers (API answers 503). Sign-in, legal pages and webhooks keep working." />
            <Field label="Maintenance message" className="py-3"><Textarea value={maint.message || ""} maxLength={500} onChange={(e) => setSys({ maintenance: { ...maint, message: e.target.value } })} /></Field>
            <Toggle checked={sys.registration_enabled !== false} onChange={(v) => setSys({ registration_enabled: v })} label="New sign-ups" description="Turn off to pause registration." />
            <Toggle checked={sys.ai_generation_enabled !== false} onChange={(v) => setSys({ ai_generation_enabled: v })} label="AI generation" description="Kill switch for all generation (e.g. provider incident or runaway cost)." />
            <Toggle checked={!!sys.require_email_verification_for_generation} onChange={(v) => setSys({ require_email_verification_for_generation: v })} label="Require verified email to generate" />
            <Field label="Max upload size (MB, platform-wide)" className="py-3"><Input type="number" min={1} max={500} value={sys.max_upload_mb} onChange={(e) => setSys({ max_upload_mb: Number(e.target.value) })} /></Field>
          </div>
        </Panel>
        <Panel title="Feature flags" action={<Button size="sm" onClick={() => save("feature_flags")}>Save</Button>}>
          <div className="divide-y divide-line">
            {Object.entries(s.feature_flags).map(([k, v]) => <Toggle key={k} checked={!!v} onChange={(val) => setS({ ...s, feature_flags: { ...s.feature_flags, [k]: val } })} label={k.replace(/_/g, " ")} />)}
          </div>
        </Panel>
        <Panel title="Plan limits" action={<Button size="sm" onClick={() => save("plan_limits")}>Save</Button>}>
          <table className="w-full text-sm">
            <thead><tr><th className="py-2 text-start text-muted">Plan</th>{LIMIT_FIELDS.map(([, l]) => <th key={l} className="py-2 text-muted">{l}</th>)}</tr></thead>
            <tbody>{Object.entries(s.plan_limits).map(([plan, lim]: any) => (
              <tr key={plan}><td className="py-1.5 pe-2 font-medium">{plan === "*" ? "default" : plan}</td>
                {LIMIT_FIELDS.map(([k]) => <td key={k} className="px-1"><Input type="number" min={0} value={lim[k] ?? ""} aria-label={`${plan} ${k}`}
                  onChange={(e) => setS({ ...s, plan_limits: { ...s.plan_limits, [plan]: { ...lim, [k]: e.target.value === "" ? undefined : Number(e.target.value) } } })} /></td>)}</tr>
            ))}</tbody>
          </table>
          <p className="mt-2 text-xs text-muted">Monthly credits and storage are set per plan in Plans & trial.</p>
        </Panel>
        <Panel title="Referral rewards" action={<Button size="sm" onClick={() => save("referrals")}>Save</Button>}>
          <Toggle checked={!!s.referrals?.enabled} label="Teacher referral program" description="Both teachers receive a reward after the referred teacher's first paid subscription." onChange={(enabled) => setS({...s, referrals: {...s.referrals, enabled}})} />
          <Field label="Media credits for each teacher"><Input type="number" min={1} max={10000} value={s.referrals?.reward_media_credits ?? 25} onChange={(e) => setS({...s, referrals: {...s.referrals, reward_media_credits: Number(e.target.value)}})} /></Field>
        </Panel>
        <Panel title="Coupon codes">
          <p className="text-sm text-muted">Create discounts in your active payment provider's dashboard. Set expiry, redemption limits, eligible products, and discount duration there. Teachers can enter a code before checkout; the provider validates it and displays the final total.</p>
          <div className="mt-4 flex gap-3"><a className="text-sm underline" href="https://dashboard.stripe.com/coupons" target="_blank" rel="noreferrer">Stripe discounts</a><a className="text-sm underline" href="https://app.dodopayments.com" target="_blank" rel="noreferrer">Dodo dashboard</a></div>
        </Panel>
        <Panel title="Rate limits (per minute)" action={<Button size="sm" onClick={() => save("rate_limits")}>Save</Button>}>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(s.rate_limits).map(([k, v]: any) => <Field key={k} label={k.replace(/_/g, " ")}><Input type="number" min={1} value={v} onChange={(e) => setS({ ...s, rate_limits: { ...s.rate_limits, [k]: Number(e.target.value) } })} /></Field>)}
          </div>
        </Panel>
        <Panel title="Data retention (days)" action={<Button size="sm" onClick={() => save("system")}>Save</Button>}>
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(sys.retention_days || {}).map(([k, v]: any) => <Field key={k} label={k.replace(/_/g, " ")}><Input type="number" min={7} max={3650} value={v} onChange={(e) => setSys({ retention_days: { ...sys.retention_days, [k]: Number(e.target.value) } })} /></Field>)}
          </div>
          <p className="mt-2 text-xs text-muted">Audit logs and consent records are never deleted automatically.</p>
        </Panel>
      </div>
      <ReasonDialog open={confirmMaint} onClose={() => setConfirmMaint(false)} requireReason={false} danger confirmLabel="Turn on and save"
        title="Turn on maintenance mode?" description="Teachers will be blocked from the app until you turn it off."
        onConfirm={async () => {
          const next = { ...s, system: { ...sys, maintenance: { ...maint, enabled: true } } };
          setS(next);
          await api("/admin/settings/system", { method: "PUT", body: next.system });
          mutate();
        }} />
    </AdminPage>
  );
}
