"use client";

import { Laptop, LogOut, Smartphone } from "lucide-react";
import { useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Card, CardHeader, Field, Input, Skeleton, Toggle } from "@/components/ui";
import { api, timeAgo } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export function SecurityCard() {
  const { notify } = useToast();
  const { data, mutate } = useApi<{ items: any[] }>("/auth/sessions");
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [busy, setBusy] = useState(false);
  const change = async () => {
    setBusy(true);
    try {
      await api("/auth/change-password", { body: pw });
      notify({ tone: "success", title: "Password changed", body: "Your other devices were signed out." });
      setPw({ current_password: "", new_password: "" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't change password", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const revoke = async (id: string) => {
    await api(`/auth/sessions/${id}`, { method: "DELETE" }).catch((e) => notify({ tone: "error", title: errorMessage(e) }));
    mutate();
  };
  const logoutAll = async () => {
    if (!confirm("Sign out of Clastio on every device, including this one?")) return;
    await api("/auth/logout-all", { method: "POST" });
    window.location.href = "/login";
  };
  const active = (data?.items || []).filter((s) => !s.revoked_at);
  return (
    <Card id="security">
      <CardHeader title="Sign-in & security" subtitle="Change your password and see where you're signed in." />
      <div className="space-y-5 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Current password"><Input type="password" autoComplete="current-password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} /></Field>
          <Field label="New password" hint="At least 8 characters"><Input type="password" autoComplete="new-password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        </div>
        <Button variant="outline" onClick={change} loading={busy} disabled={!pw.current_password || pw.new_password.length < 8}>Change password</Button>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-ink">Active sessions</span>
            <Button variant="ghost" size="sm" onClick={logoutAll}><LogOut className="h-4 w-4" /> Sign out everywhere</Button>
          </div>
          {!data ? <Skeleton className="h-24" /> : (
            <ul className="divide-y divide-line rounded-xl border border-line">
              {active.map((s) => {
                const Icon = s.device_type === "mobile" ? Smartphone : Laptop;
                return (
                  <li key={s.id} className="flex items-center gap-3 px-3 py-2.5 text-sm">
                    <Icon className="h-5 w-5 shrink-0 text-muted" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-ink">{s.browser || "Browser"} on {s.os || "unknown"} {s.current && <Badge tone="success" className="ms-1">This device</Badge>}</span>
                      <span className="block text-xs text-muted">{s.ip || "unknown IP"} · active {timeAgo(s.last_active_at)} · signed in {timeAgo(s.created_at)}</span>
                    </span>
                    {!s.current && <Button variant="ghost" size="sm" onClick={() => revoke(s.id)}>Sign out</Button>}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}

export function NotificationPrefsCard() {
  const { notify } = useToast();
  const { data, mutate } = useApi<{ items: any[] }>("/me/notification-preferences");
  const set = async (category: string, channel: "in_app" | "email", value: boolean) => {
    try {
      const next = await api("/me/notification-preferences", { method: "PUT", body: { categories: { [category]: { [channel]: value } } } });
      mutate(next, false);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };
  return (
    <Card id="notifications">
      <CardHeader title="Notifications" subtitle="Choose what reaches you in the app and by email." />
      <div className="p-5">
        {!data ? <Skeleton className="h-40" /> : (
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted"><tr><th className="py-2 text-start font-medium">Type</th><th className="py-2 font-medium">In app</th><th className="py-2 font-medium">Email</th></tr></thead>
            <tbody className="divide-y divide-line">
              {data.items.map((p) => (
                <tr key={p.category}>
                  <td className="py-2.5 pe-3 text-ink">{p.label}{p.mandatory && <span className="block text-xs text-muted">Always on</span>}</td>
                  {(["in_app", "email"] as const).map((ch) => (
                    <td key={ch} className="py-2.5 text-center">
                      <input type="checkbox" aria-label={`${p.label}: ${ch === "email" ? "email" : "in app"}`} className="h-4 w-4 accent-[var(--color-brand-600)]"
                        checked={p[ch]} disabled={p.mandatory} onChange={(e) => set(p.category, ch, e.target.checked)} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </Card>
  );
}

export function ConsentsCard() {
  const { data, mutate } = useApi<any>("/me/consents");
  const { notify } = useToast();
  const set = async (key: string, value: boolean) => {
    try {
      mutate(await api("/me/consents", { method: "PUT", body: { [key]: value } }), false);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    }
  };
  const c = data?.consents || {};
  return (
    <Card>
      <CardHeader title="Privacy & consent" subtitle="Marketing is always optional and separate from our Terms." />
      <div className="divide-y divide-line px-5">
        {!data ? <Skeleton className="my-4 h-24" /> : (
          <>
            <Toggle checked={data.marketing.marketing_email} onChange={(v) => set("marketing_email", v)} label="Tips and product news by email" />
            <Toggle checked={data.marketing.marketing_whatsapp} onChange={(v) => set("marketing_whatsapp", v)} label="Product news on WhatsApp" />
            <div className="py-3 text-xs text-muted">
              {["terms", "privacy", "acceptable_use"].map((k) => c[k] && (
                <div key={k}>Accepted {k.replace("_", " ")} v{c[k].version} on {new Date(c[k].at).toLocaleDateString()}</div>
              ))}
              <button className="mt-2 text-brand-600 underline" onClick={() => { try { localStorage.removeItem("clastio:cookie-consent"); } catch { /* ignore */ } window.location.reload(); }}>
                Change cookie choices
              </button>
            </div>
          </>
        )}
      </div>
    </Card>
  );
}
