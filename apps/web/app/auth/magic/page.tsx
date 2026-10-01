"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Alert, Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useSWRConfig } from "swr";

function Magic() {
  const params = useSearchParams();
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setError("This link is missing its token.");
      return;
    }
    api<{ redirect: string }>("/auth/magic", { body: { token } })
      .then(async (r) => {
        await mutate("/auth/me", await api("/auth/me"), { revalidate: false });
        router.replace(r.redirect || "/dashboard");
      })
      .catch((e) => setError(e.message));
  }, [params, router, mutate]);
  return (
    <div className="grid min-h-screen place-items-center p-6">
      {error ? (
        <div className="max-w-sm space-y-4 text-center">
          <Alert tone="danger">{error}</Alert>
          <Button href="/login">Sign in</Button>
        </div>
      ) : (
        <div className="flex items-center gap-3 text-muted"><Spinner /> Opening your lesson…</div>
      )}
    </div>
  );
}

export default function MagicPage() {
  return (
    <Suspense>
      <Magic />
    </Suspense>
  );
}
