"use client";

import { useEffect, useRef, useState } from "react";
import useSWR, { type SWRConfiguration } from "swr";
import { api, fetcher } from "./api";

export type User = {
  id: string;
  email: string;
  name: string;
  role: "teacher" | "admin";
  admin_role?: string | null;
  admin_role_label?: string | null;
  permissions: string[];
  status: string;
  email_verified: boolean;
  locale: string;
  timezone: string;
  onboarding_completed: boolean;
};

export type LegalDoc = { id: string; type: string; title: string; version: string; summary_of_changes?: string | null; requires_acceptance: boolean };

export function useMe() {
  const { data, error, isLoading, mutate } = useSWR<{ user: User; pending_legal?: LegalDoc[] }>("/auth/me", fetcher, {
    shouldRetryOnError: false,
    revalidateOnFocus: false,
  });
  return { user: data?.user, pendingLegal: data?.pending_legal || [], error, isLoading, mutate };
}

/** Staff permission check for showing controls. The server enforces every permission independently. */
export function useCan() {
  const { user } = useMe();
  const perms = new Set(user?.permissions || []);
  return (...needed: string[]) => needed.every((p) => perms.has(p));
}

export function useApi<T = any>(path: string | null, config?: SWRConfiguration) {
  return useSWR<T>(path, fetcher, { revalidateOnFocus: false, ...config });
}

export type Job = {
  id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  progress: number;
  stage: string | null;
  error: string | null;
  result: any;
};

/** Poll a background job until it finishes. */
export function useJob(jobId: string | null | undefined, onDone?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null);
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  useEffect(() => {
    setJob(null);
    if (!jobId) return;
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const j = await api<Job>(`/jobs/${jobId}`);
        if (stop) return;
        setJob(j);
        if (j.status === "succeeded" || j.status === "failed" || j.status === "cancelled") {
          await doneRef.current?.(j);
          return;
        }
      } catch {}
      if (!stop) timer = setTimeout(tick, 1200);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [jobId]);
  return job;
}

export function greeting(name?: string) {
  const h = new Date().getHours();
  const part = h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
  const first = (name || "").split(" ")[0];
  return first ? `${part}, ${first}` : part;
}
