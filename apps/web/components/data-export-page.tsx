"use client";

import { useState } from "react";
import { SystemStateLayout } from "@/components/system-state-layout";
import { Alert, Button, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useApi, type User } from "@/lib/hooks";
import { supportEmailFor } from "@/lib/public-support";

export function DataExportPage() {
  const account = useApi<{ user: User }>("/auth/me", { shouldRetryOnError: false, revalidateOnMount: true, revalidateOnFocus: false });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [downloaded, setDownloaded] = useState(false);
  const user = account.error ? undefined : account.data?.user;
  if (account.isLoading || account.isValidating && !account.error) return <SystemStateLayout title="Checking account access" description="Please wait while we check who is signed in."><Spinner /></SystemStateLayout>;
  if (account.error || !user) {
    const signedOut = account.error instanceof ApiError && account.error.status === 401;
    return <SystemStateLayout title={signedOut ? "Sign in to request your data" : "We couldn’t check your account"}
      description={signedOut ? "Sign in to the account whose summary you want to download. You can also contact support about a broader data request." : "Account access could not be confirmed. Retry the check or contact support before requesting an export."}
      actions={<><Button href="/login?next=%2Fdata-export-request">Sign in</Button>{!signedOut && <Button variant="outline" onClick={() => void account.mutate()}>Check again</Button>}<Button variant="outline" href="/contact">Contact support</Button></>} />;
  }
  const download = async () => {
    if (busy) return;
    setBusy(true); setError(""); setDownloaded(false);
    try {
      const data = await api<Record<string, unknown>>("/me/export");
      if (!data || typeof data !== "object" || Array.isArray(data) || !data.user) throw new Error("The account summary could not be confirmed. Please retry or contact support.");
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url; link.download = "clastio-account-summary.json";
      document.body.appendChild(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      setDownloaded(true);
    } catch (failure) { setError((failure as Error).message); }
    finally { setBusy(false); }
  };
  return <SystemStateLayout title="Download your account summary" description="The summary includes profile details, preferences, classes and lists of courses, lessons, documents and uploads. It also includes your recorded AI-call count."
    actions={<><Button loading={busy} onClick={download}>Download account summary</Button><Button variant="outline" href="/support">Request wider data access</Button><Button variant="outline" href="/settings">Account settings</Button></>}>
    {error && <Alert tone="danger">{error}</Alert>}
    {downloaded && <Alert tone="success">Your browser received the account summary. Check its downloads list to save the JSON file.</Alert>}
    <p className="text-sm text-muted">Uploaded file contents, generated presentations and other full workspace records are not included in this summary. Download teaching files from their workspace pages. For a wider request, open an account support ticket or <a className="underline" href={supportEmailFor("Data access request")}>email Clastio support</a>.</p>
    <p className="mt-4 text-sm text-muted">Read the <a className="underline" href="/legal/privacy">published Privacy Policy</a> and <a className="underline" href="/data-privacy">data request guidance</a> before closing account access.</p>
  </SystemStateLayout>;
}
