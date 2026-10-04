"use client";
import { useState } from "react";
import { api, formatDate } from "@/lib/api";
import { useApi, useCan } from "@/lib/hooks";
import { LoadError } from "@/components/load-error";
import { Button, Field, Input, Select } from "@/components/ui";

export function LicensePanel({ admin = false }: { admin?: boolean }) {
  const [key, setKey] = useState("");
  const [plan, setPlan] = useState("teacher");
  const [months, setMonths] = useState(1);
  const [busy, setBusy] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const can = useCan();
  const canManage = admin && can("billing.modify");
  const { data, error, mutate } = useApi<{ items: { id: string; key_suffix: string; plan_code: string; months: number; expires_at: string; redeemed_at: string | null; revoked: boolean }[] }>(admin ? "/admin/licenses" : null);
  const submit = async () => {
    setBusy(true); setMessage("");
    try {
      if (admin) {
        const result = await api<{ key: string }>("/admin/licenses", { body: { plan, months, valid_days: 90 } });
        setKey(result.key); setMessage("Copy this key now. It is shown only once and can be redeemed within 90 days.");
        await mutate();
      } else {
        await api("/billing/licenses/redeem", { body: { key } });
        window.location.reload();
      }
    } catch (e) { setMessage((e as Error).message); }
    finally { setBusy(false); }
  };
  return <section id="license" className="scroll-mt-6 space-y-4 rounded-3xl bg-surface p-6 ring-1 ring-line">
    <h2 className="text-xl font-semibold">{admin ? "Create plan licenses" : "Redeem a license key"}</h2>
    <p className="text-sm text-muted">{admin ? "Issue a single-use key for school or promotional access." : "Have a key from your school or Clastio? Redeem it here for plan access without checkout."}</p>
    {canManage && <div className="flex flex-wrap gap-3"><Field label="Plan"><Select value={plan} onChange={e => setPlan(e.target.value)}>{["teacher", "pro", "assistant"].map(p => <option key={p}>{p}</option>)}</Select></Field><Field label="Months of access"><Input type="number" min={1} max={36} value={months} onChange={e => setMonths(Number(e.target.value))} /></Field></div>}
    {(!admin || canManage) && <>
      <Field label="License key"><Input value={key} readOnly={admin} maxLength={100} spellCheck={false} onChange={e => setKey(e.target.value)} autoComplete="off" /></Field>
      <Button loading={busy} disabled={admin ? !Number.isInteger(months) || months < 1 || months > 36 : !key.trim()} onClick={submit}>{admin ? "Create license" : "Redeem license"}</Button>
      {admin && key && <Button variant="outline" onClick={async () => { try { await navigator.clipboard.writeText(key); setMessage("License key copied. Keep it safe; it grants plan access."); } catch { setMessage("Select the license key and copy it manually."); } }}>Copy key</Button>}
    </>}
    {message && <p role="status" className="text-sm">{message}</p>}
    {admin && error && <LoadError label="licenses" retry={mutate} />}
    {admin && !data && !error && <p role="status" className="text-sm text-muted">Loading licenses…</p>}
    {admin && data?.items.length === 0 && <p className="text-sm text-muted">No licenses created yet.</p>}
    {admin && data?.items.map(item => {
      const expired = new Date(item.expires_at).getTime() <= Date.now();
      return <div key={item.id} className="flex flex-wrap items-center gap-3 border-t border-line pt-3 text-sm"><span>…{item.key_suffix} · {item.plan_code} · {item.months} months · {item.redeemed_at ? "Redeemed" : item.revoked ? "Revoked" : expired ? "Expired" : "Available"} · redeem by {formatDate(item.expires_at)}</span>{canManage && !item.redeemed_at && !item.revoked && !expired && <Button variant="outline" loading={revoking === item.id} disabled={revoking !== null} onClick={async () => { setRevoking(item.id); try { await api(`/admin/licenses/${item.id}`, { method: "DELETE" }); await mutate(); } catch(e) {setMessage((e as Error).message);} finally { setRevoking(null); } }}>Revoke</Button>}</div>;
    })}
  </section>;
}
