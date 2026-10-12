"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useSWRConfig } from "swr";
import { SystemStateLayout } from "@/components/system-state-layout";
import { PricingTable } from "@/components/pricing-table";
import { NotificationPrefsCard } from "@/components/account-settings";
import { Alert, Button, Field, Input, Spinner } from "@/components/ui";
import { api, ApiError, formatDate } from "@/lib/api";
import { useApi, type User } from "@/lib/hooks";
import { adminLandingPath, safeInternalPath } from "@/lib/navigation";
import { availableUsageResource, billingStateView, confirmedPaidAccess, safePaymentDestination, type AccountSystemKind, type BillingState, type BillingSystemKind } from "@/lib/account-state";
import { quotaAvailable } from "@/lib/usage";

function useCheckedAccount() {
  return useApi<{ user: User }>("/auth/me", { shouldRetryOnError: false, revalidateOnMount: true, revalidateOnFocus: false });
}

function accountHome(user: User, next?: string | null) {
  return user.role === "admin" ? adminLandingPath(user.permissions) : !user.onboarding_completed ? "/onboarding" : safeInternalPath(next);
}

function AccountUnavailable({ error, retry, next }: { error: unknown; retry: () => void; next: string }) {
  const unauthorized = error instanceof ApiError && error.status === 401;
  const restricted = error instanceof ApiError && error.status === 403;
  return <SystemStateLayout title={unauthorized ? "Sign in to continue" : restricted ? "Account access is unavailable" : "We couldn’t check your account"}
    description={unauthorized ? "There is no active sign-in on this device. Sign in to check the account and continue." : restricted ? "The account service has restricted access. Contact support to review the account; this page does not identify the reason for the restriction." : "Your account status is temporarily unavailable. Retry the check before making account or billing changes."}
    tone={restricted ? "warn" : "neutral"} actions={<><Button href={`/login?next=${encodeURIComponent(next)}`}>Sign in</Button>{!unauthorized && !restricted && <Button variant="outline" onClick={retry}>Check again</Button>}<Button href="/contact" variant="outline">Contact support</Button></>} />;
}

export function AccountSystemPage({ kind }: { kind: AccountSystemKind }) {
  const params = useSearchParams();
  const account = useCheckedAccount();
  const user = account.error ? undefined : account.data?.user;
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const next = safeInternalPath(params.get("next"));
  if (account.isLoading || account.isValidating && !account.error) return <SystemStateLayout title="Checking your account" description="Please wait while we check the current sign-in and account status."><Spinner /></SystemStateLayout>;
  if (kind === "account-deleted" && !user && account.error instanceof ApiError && account.error.status === 401) {
    return <SystemStateLayout title="Account closure status" description="You are not signed in, so this page cannot confirm an account deletion. A successful deletion request shows its confirmation and scheduled date when submitted. Contact support to ask about a previous request." actions={<><Button href="/contact">Contact support</Button><Button variant="outline" href="/login">Sign in</Button></>} />;
  }
  if (kind === "link-expired") {
    const purpose = params.get("purpose");
    return <SystemStateLayout title="Get a fresh account link" description="Use a fresh verification or password-reset email if a previous link could not be accepted. Link validity is checked when the account service processes it." actions={<><Button href={purpose === "reset" ? "/forgot-password" : user ? "/verification-failed" : "/login"}>{purpose === "reset" ? "Request a reset email" : user ? "Check email verification" : "Sign in"}</Button><Button variant="outline" href="/forgot-password">Password reset</Button><Button variant="outline" href="/contact">Contact support</Button></>} />;
  }
  if (account.error || !user) return <AccountUnavailable error={account.error} retry={() => void account.mutate()} next={kind === "session-expired" ? next : `/${kind}`} />;
  if (kind === "verification-success" || kind === "verification-failed") {
    const resend = async () => {
      setBusy(true); setError(""); setMessage("");
      try {
        const result = await api<{ already_verified?: boolean }>("/auth/resend-verification", { method: "POST" });
        setMessage(result.already_verified ? "The account service confirms your email is already verified." : "A verification email was requested. Check your inbox and spam folder.");
        await account.mutate();
      } catch (failure) { setError((failure as Error).message); }
      finally { setBusy(false); }
    };
    return <SystemStateLayout title={user.email_verified ? "Your email is verified" : "Verify your email"} tone={user.email_verified ? "success" : "neutral"}
      description={user.email_verified ? "The account service confirms this account’s email address is verified. You can continue to the app." : `The account service shows that ${user.email} still needs verification. Request a fresh message and use the link it contains.`}
      actions={<>{!user.email_verified && <Button loading={busy} onClick={resend}>Resend verification email</Button>}<Button href={accountHome(user)} variant={user.email_verified ? "primary" : "outline"}>Continue to the app</Button><Button href="/contact" variant="outline">Contact support</Button></>}>
      {message && <Alert tone="success">{message}</Alert>}{error && <Alert tone="danger">{error}</Alert>}
    </SystemStateLayout>;
  }
  return <SystemStateLayout title={user.status === "active" ? "Your account is active" : "Review account access"}
    description={user.status === "active" ? "The account service confirms active access. Continue to your app, or open account settings to review security and privacy choices." : "The account service reports that access is restricted. Contact support to review the available recovery options."}
    tone={user.status === "active" ? "success" : "warn"} actions={<><Button href={accountHome(user, next)}>Continue to the app</Button><Button variant="outline" href="/settings">Account settings</Button><Button variant="outline" href="/contact">Contact support</Button></>} />;
}

export function DeleteAccountPage() {
  const account = useCheckedAccount();
  const { mutate } = useSWRConfig();
  const user = account.error ? undefined : account.data?.user;
  const [email, setEmail] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [receipt, setReceipt] = useState<{ status: string; purge_on?: string } | null>(null);
  if (receipt) return <SystemStateLayout title="Deletion request accepted" tone="success" description="The account service accepted your request and scheduled account deletion. This confirmation records the request; it does not mean that final deletion has already completed." actions={<><Button href="/contact">Contact support about this request</Button><Button variant="outline" href="/">Go home</Button></>}>
    {receipt.purge_on && <p className="text-sm">Scheduled date from the account service: <strong>{formatDate(receipt.purge_on, { day: "numeric", month: "long", year: "numeric" })}</strong>.</p>}
    <p className="mt-3 text-sm text-muted">Your access is closed now. Contact support within the account’s grace period if you want to ask about withdrawing the request. Payment and other records may be retained where required.</p>
  </SystemStateLayout>;
  if (account.isLoading || account.isValidating && !account.error) return <SystemStateLayout title="Checking account access" description="Please wait while we check who is signed in."><Spinner /></SystemStateLayout>;
  if (account.error || !user) return <AccountUnavailable error={account.error} retry={() => void account.mutate()} next="/delete-account" />;
  if (user.role === "admin") return <SystemStateLayout title="Staff accounts are managed by an administrator" description="Self-service deletion is available for teacher accounts. Contact the administrator responsible for your staff access." actions={<><Button href={accountHome(user)}>Return to the admin console</Button><Button variant="outline" href="/contact">Contact support</Button></>} />;
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy || !acknowledged || email.trim().toLowerCase() !== user.email.toLowerCase()) return;
    setBusy(true); setError("");
    try {
      const result = await api<{ status: string; purge_on?: string }>("/me/delete", { body: { confirm_email: email.trim() }, idempotent: true });
      if (result.status !== "pending_deletion") throw new Error("The deletion request could not be confirmed. Contact support before submitting again.");
      setReceipt(result);
      await mutate("/auth/me", undefined, { revalidate: false });
      navigator.serviceWorker?.controller?.postMessage({ type: "CLASTIO_SIGNED_OUT" });
      const clerk = (window as unknown as { Clerk?: { signOut: () => Promise<void> } }).Clerk;
      await clerk?.signOut().catch(() => {});
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  };
  return <SystemStateLayout title="Request account deletion" description="Review the request before confirming. Submitting closes account access immediately and schedules deletion after the configured grace period. Contact support with questions about retained records or a previous request." actions={<><Button href="/settings" variant="outline">Keep my account</Button><Button href="/contact" variant="outline">Contact support</Button></>}>
    <p className="mb-5 text-sm text-muted">Settings provides an account-summary export. Download any presentation or document files you want to keep before closing access.</p>
    <form onSubmit={submit} className="space-y-4">
      <Field label="Confirm your account email" hint={`Type ${user.email} to confirm this account.`}><Input aria-label="Confirm your account email" type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></Field>
      <label className="flex items-start gap-3 text-sm"><input type="checkbox" required checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} className="mt-1" /><span>I understand this closes access now and requests scheduled deletion.</span></label>
      {error && <Alert tone="danger">{error}</Alert>}
      <Button type="submit" variant="danger" loading={busy} disabled={!acknowledged || email.trim().toLowerCase() !== user.email.toLowerCase()}>Submit deletion request</Button>
    </form>
  </SystemStateLayout>;
}

export function BillingSystemPage({ kind }: { kind: BillingSystemKind }) {
  const params = useSearchParams();
  const account = useCheckedAccount();
  const user = account.error ? undefined : account.data?.user;
  const [waiting, setWaiting] = useState(kind === "payment-success");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [cancelConfirmed, setCancelConfirmed] = useState(false);
  const [billingChecked, setBillingChecked] = useState(false);
  const billing = useApi<BillingState>(user && user.role !== "admin" ? "/billing/subscription" : null, { shouldRetryOnError: false, revalidateOnMount: true, refreshInterval: current => waiting ? 2000 : current?.pending_checkout ? 5000 : 0 });
  useEffect(() => {
    if (billing.data && !billing.isValidating && !billing.error) {
      setBillingChecked(true);
      if (confirmedPaidAccess(billing.data)) setWaiting(false);
    }
  }, [billing.data, billing.isValidating, billing.error]);
  useEffect(() => {
    if (!waiting) return;
    const timer = setTimeout(() => setWaiting(false), 45000);
    return () => clearTimeout(timer);
  }, [waiting]);
  if (account.isLoading || account.isValidating && !account.error) return <SystemStateLayout title="Checking billing access" description="Please wait while we check your sign-in."><Spinner /></SystemStateLayout>;
  if (account.error || !user) return <AccountUnavailable error={account.error} retry={() => void account.mutate()} next={`/${kind}`} />;
  if (user.role === "admin") return <SystemStateLayout title="Staff billing access" description="Teacher subscriptions and self-service checkout are separate from staff administration. Open the admin console or contact support about account access." actions={<><Button href={accountHome(user)}>Open admin console</Button><Button variant="outline" href="/contact">Contact support</Button></>} />;
  if (billing.error) return <SystemStateLayout title="We couldn’t check billing" description="Your current payment and plan status is unavailable. Retry before making another payment or changing your subscription." reference={billing.error instanceof ApiError ? billing.error.requestId : undefined} actions={<><Button onClick={() => void billing.mutate()}>Check billing again</Button><Button variant="outline" href="/contact">Contact support</Button></>} />;
  const data = billing.data;
  if (!data || !billingChecked) return <SystemStateLayout title="Checking current billing" description="Please wait while we load the plan and payment status."><Spinner /></SystemStateLayout>;
  const resource = availableUsageResource(params.get("resource"));
  const view = billingStateView(kind, data, resource);
  const sub = data.subscription;
  const pending = data.pending_checkout;
  const online = Boolean(sub && ["stripe", "dodo"].includes(sub.provider || ""));
  const pendingUrl = pending?.url && typeof window !== "undefined" ? safePaymentDestination(pending.url, window.location.origin) : null;
  const quota = data.usage?.[resource];
  const openPortal = async () => {
    setBusy(true); setError("");
    try {
      const result = await api<{ url: string }>("/billing/portal", { method: "POST" });
      const destination = safePaymentDestination(result.url, window.location.origin);
      if (!destination) throw new Error("The billing portal destination could not be confirmed. Contact support.");
      window.location.assign(destination);
    } catch (failure) { setError((failure as Error).message); setBusy(false); }
  };
  const cancel = async (event: React.FormEvent) => {
    event.preventDefault(); if (!cancelConfirmed || busy) return;
    setBusy(true); setError("");
    try { await api("/billing/cancel", { method: "POST", idempotent: true }); await billing.mutate(); setCancelConfirmed(false); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  };
  return <SystemStateLayout {...view} actions={<>
    {pendingUrl && <Button href={pendingUrl}>Resume checkout</Button>}
    {online && <Button loading={busy} onClick={openPortal} variant={pendingUrl ? "outline" : "primary"}>Open secure billing portal</Button>}
    <Button href="/billing" variant="outline">Open Plan & billing</Button><Button onClick={() => void billing.mutate()} variant="outline">Refresh status</Button><Button href="/contact" variant="outline">Contact support</Button>
  </>}>
    <dl className="grid gap-4 rounded-xl bg-surface-2 p-4 text-sm sm:grid-cols-2"><div><dt className="text-muted">Current plan</dt><dd className="mt-1 font-semibold">{data.plan.name}</dd></div><div><dt className="text-muted">Subscription status</dt><dd className="mt-1 font-semibold">{sub?.status?.replaceAll("_", " ") || "No current paid subscription"}</dd></div>
      {sub?.current_period_end && <div><dt className="text-muted">Current billing period ends</dt><dd className="mt-1 font-semibold">{formatDate(sub.current_period_end, { day: "numeric", month: "long", year: "numeric" })}</dd></div>}
      {pending && <div><dt className="text-muted">Checkout status</dt><dd className="mt-1 font-semibold">{pending.status}</dd></div>}
      {data.trial?.active && data.trial.ends_at && <div><dt className="text-muted">Trial ends</dt><dd className="mt-1 font-semibold">{formatDate(data.trial.ends_at, { day: "numeric", month: "long", year: "numeric" })}</dd></div>}
    </dl>
    {(kind === "usage-limit" || kind === "upgrade-required") && quota && <p className="mt-4 text-sm">{resource.replaceAll("_", " ")}: {quotaAvailable(quota) === null ? "unlimited available" : `${quotaAvailable(quota)} available`}{(quota.reserved || 0) > 0 ? ` · ${quota.reserved} reserved for queued work` : ""}. <a href="/activity" className="font-semibold text-brand-700 underline">Review Activity</a></p>}
    {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
    {kind === "subscription-cancelled" && online && !sub?.cancel_at_period_end && !["canceled", "cancelled"].includes(sub?.status || "") && <form onSubmit={cancel} className="mt-6 space-y-4 rounded-xl border border-line p-4"><label className="flex items-start gap-3 text-sm"><input type="checkbox" checked={cancelConfirmed} onChange={event => setCancelConfirmed(event.target.checked)} className="mt-1" /><span>I want to cancel renewal at the end of the current billing period.</span></label><Button type="submit" variant="danger" loading={busy} disabled={!cancelConfirmed}>Request cancellation</Button></form>}
    {kind === "checkout" && !pending && !online && !(sub?.provider === "manual" && data.plan.code !== "free") && <div className="mt-8"><h2 className="mb-5 text-xl font-semibold">Current plans</h2><PricingTable mode="app" currentPlan={data.plan.code} onTrial={Boolean(data.trial?.active)} /></div>}
    <p className="mt-5 text-xs text-muted">Payment confirmation and account access are provided by the billing service. Review Plan & billing for payment history and any available invoice.</p>
  </SystemStateLayout>;
}

export function ConsentSystemPage({ kind }: { kind: "email-unsubscribe" | "notification-preferences" }) {
  const account = useCheckedAccount();
  const user = account.error ? undefined : account.data?.user;
  const emailPage = kind === "email-unsubscribe";
  const preferences = useApi<{ marketing: { marketing_email: boolean }; items?: unknown[] }>(user ? emailPage ? "/me/consents" : "/me/notification-preferences" : null, { shouldRetryOnError: false, revalidateOnMount: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (account.isLoading || account.isValidating && !account.error) return <SystemStateLayout title="Checking account preferences" description="Please wait while we check your sign-in."><Spinner /></SystemStateLayout>;
  if (account.error || !user) return <AccountUnavailable error={account.error} retry={() => void account.mutate()} next={`/${kind}`} />;
  if (preferences.error) return <SystemStateLayout title="Preferences are unavailable" description="Retry before changing email or notification choices." actions={<><Button onClick={() => void preferences.mutate()}>Check again</Button><Button variant="outline" href="/settings">Open Settings</Button></>} />;
  if (!preferences.data || preferences.isValidating) return <SystemStateLayout title="Loading preferences" description="Please wait while we load your account’s current choices."><Spinner /></SystemStateLayout>;
  if (!emailPage) return <SystemStateLayout title="Notification preferences" description="Choose the channels available for your account. Mandatory account notifications remain enabled." actions={<Button variant="outline" href="/settings#notifications">Open account settings</Button>}><NotificationPrefsCard /></SystemStateLayout>;
  const enabled = preferences.data.marketing.marketing_email;
  const unsubscribe = async () => {
    setBusy(true); setError("");
    try { const next = await api<{ marketing: { marketing_email: boolean } }>("/me/consents", { method: "PUT", body: { marketing_email: false } }); await preferences.mutate(next, false); }
    catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  };
  return <SystemStateLayout title={enabled ? "Manage email marketing" : "Email marketing is off"} tone={enabled ? "neutral" : "success"} description={enabled ? "Your account currently allows optional tips and product news by email. Choose the button below to turn those messages off." : "The account service confirms that optional email marketing is off. Account, security and billing messages may still be sent."}
    actions={<>{enabled && <Button loading={busy} onClick={unsubscribe}>Unsubscribe from marketing email</Button>}<Button href="/settings" variant="outline">Open privacy settings</Button></>}>
    {error && <Alert tone="danger">{error}</Alert>}
  </SystemStateLayout>;
}
