"use client";

import { useEffect, useState } from "react";
import { Bell, BellOff } from "lucide-react";
import { useMobileApp } from "@/components/mobile-app";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Card, CardHeader, Skeleton, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type Device = { id: string; endpoint_hash: string; device_name: string; marketing_enabled: boolean; consent_at: string; active: boolean };
type PushConfig = { configured: boolean; public_key: string | null; items: Device[] };

function applicationKey(encoded: string): Uint8Array<ArrayBuffer> {
  const decoded = atob(encoded.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - encoded.length % 4) % 4));
  return Uint8Array.from(decoded, (char) => char.charCodeAt(0));
}

async function hashEndpoint(endpoint: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(endpoint));
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function PushNotificationsCard() {
  const { registration, ios, installed } = useMobileApp();
  const { data, error, mutate } = useApi<PushConfig>("/me/push");
  const { notify } = useToast();
  const [browserSubscription, setBrowserSubscription] = useState<PushSubscription | null>(null);
  const [currentHash, setCurrentHash] = useState<string | null>(null);
  const [supported, setSupported] = useState(false);
  const [permission, setPermission] = useState<NotificationPermission>("default");
  const [busy, setBusy] = useState(false);
  const [marketing, setMarketing] = useState(false);
  useEffect(() => {
    setSupported(window.isSecureContext && "PushManager" in window && "Notification" in window);
    if ("Notification" in window) setPermission(Notification.permission);
  }, []);
  useEffect(() => {
    if (!registration) return;
    let cancelled = false;
    registration.pushManager?.getSubscription().then(async (sub) => {
      const hash = sub ? await hashEndpoint(sub.endpoint) : null;
      if (!cancelled) { setBrowserSubscription(sub); setCurrentHash(hash); }
    }).catch(() => { /* Unsupported browser. */ });
    return () => { cancelled = true; };
  }, [registration]);
  const current = data?.items?.find((device) => device.endpoint_hash === currentHash);
  const enabled = Boolean(current?.active && browserSubscription && permission === "granted");
  const enable = async () => {
    if (!registration || !data?.public_key) return;
    setBusy(true);
    let sub: PushSubscription | null = null;
    try {
      // This is the first browser permission/subscription call after the click, with no preceding network await.
      sub = await registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: applicationKey(data.public_key) });
      await api("/me/push/subscriptions", { body: { ...sub.toJSON(), device_name: ios ? "iPhone / iPad" : "This browser", marketing_enabled: marketing } });
      setBrowserSubscription(sub);
      setCurrentHash(await hashEndpoint(sub.endpoint));
      setPermission(Notification.permission);
      await mutate();
      notify({ tone: "success", title: "Device notifications enabled", body: "Choose your notification categories above." });
    } catch (problem) {
      if (sub && !browserSubscription) await sub.unsubscribe().catch(() => {});
      if ("Notification" in window) setPermission(Notification.permission);
      notify({ tone: "error", title: "Couldn't enable notifications", body: errorMessage(problem) });
    } finally { setBusy(false); }
  };
  const remove = async (device: Device) => {
    setBusy(true);
    try {
      // Revoke delivery first. Browser unsubscribe failure cannot leave server notifications enabled.
      await api(`/me/push/subscriptions/${device.id}`, { method: "DELETE" });
      if (device.id === current?.id) {
        await browserSubscription?.unsubscribe();
        setBrowserSubscription(null);
        setCurrentHash(null);
      }
      await mutate();
      notify({ tone: "success", title: "Device notifications turned off" });
    } catch (problem) { notify({ tone: "error", title: "Couldn't remove this device", body: errorMessage(problem) }); }
    finally { setBusy(false); }
  };
  const changeMarketing = async (value: boolean) => {
    if (!current) { setMarketing(value); return; }
    try {
      await api(`/me/push/subscriptions/${current.id}`, { method: "PATCH", body: { marketing_enabled: value } });
      await mutate();
    } catch (problem) { notify({ tone: "error", title: "Couldn't save", body: errorMessage(problem) }); }
  };
  return <Card id="device-notifications">
    <CardHeader title="Device notifications" subtitle="Receive PPT-ready updates and reminders even when Clastio is closed." />
    <div className="space-y-4 p-5 text-sm">
      {error ? <div role="alert" className="text-muted">Couldn't load device settings. <Button variant="ghost" size="sm" onClick={() => mutate()}>Try again</Button></div>
        : !data ? <Skeleton className="h-24" /> : <>
          {!data.configured && <p className="text-muted">Device notifications are not available yet. Your in-app and email settings still work.</p>}
          {ios && !installed && <p className="text-muted">Add Clastio to your Home Screen and open the installed app before enabling notifications. iPhone and iPad need iOS / iPadOS 16.4 or later.</p>}
          {!supported && !(ios && !installed) && <p className="text-muted">This browser does not support device notifications. Try a current version of Chrome, Firefox or Safari.</p>}
          {permission === "denied" && <p className="text-muted">Notifications are blocked in your browser. Change the notification permission in this site's browser settings, then reload Clastio.</p>}
          {data.configured && supported && (!ios || installed) && <>
            <Toggle label="Product news on this device (optional)" description="Also enable Product news in the Push column above. Off by default." checked={current ? current.marketing_enabled : marketing} onChange={changeMarketing} />
            {enabled ? <Button variant="outline" onClick={() => remove(current!)} loading={busy}><BellOff className="h-4 w-4" /> Turn off on this device</Button>
              : <Button onClick={enable} loading={busy} disabled={!registration || permission === "denied"}><Bell className="h-4 w-4" /> Enable on this device</Button>}
          </>}
          <p className="text-xs text-muted">Only devices you opt in receive notifications. Turning off Push categories does not turn off required security emails. Signing out stops delivery for that device until you opt in again.</p>
          {data.items.length > 0 && <ul className="divide-y divide-line rounded-xl border border-line">
            {data.items.map((device) => <li key={device.id} className="flex items-center gap-3 p-3">
              <span className="min-w-0 flex-1 text-ink">{device.device_name}{device.id === current?.id ? " · this device" : ""}</span>
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => remove(device)}>Remove</Button>
            </li>)}
          </ul>}
        </>}
    </div>
  </Card>;
}
