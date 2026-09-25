"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { AuthLayout } from "@/components/auth-card";
import { Alert, Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

function Verify() {
  const [state, setState] = useState<"working" | "done" | "error">("working");
  const [msg, setMsg] = useState("");
  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) { setState("error"); setMsg("This link is incomplete."); return; }
    api("/auth/verify-email", { body: { token } }).then(() => setState("done")).catch((e) => { setState("error"); setMsg(e.message); });
  }, []);
  return (
    <AuthLayout title="Confirm your email" subtitle="One moment…" footer={<Link href="/login" className="text-brand-600 hover:underline">Go to sign in</Link>}>
      {state === "working" && <Spinner />}
      {state === "done" && <div className="space-y-4"><Alert tone="success" title="Email confirmed">Thanks! Your account is fully set up.</Alert><Button href="/dashboard" className="w-full">Continue</Button></div>}
      {state === "error" && <Alert tone="danger" title="We couldn't confirm your email">{msg || "The link may have expired."} Sign in and use “Resend link” to get a new one.</Alert>}
    </AuthLayout>
  );
}
export default function Page() { return <Suspense><Verify /></Suspense>; }
