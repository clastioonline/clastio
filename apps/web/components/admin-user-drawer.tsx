"use client";

import { useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Badge, Button, Field, Input, Modal, Select, Skeleton } from "@/components/ui";
import { api, formatDate, timeAgo } from "@/lib/api";
import { useApi } from "@/lib/hooks";

export function UserDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { notify } = useToast();
  const { data, mutate } = useApi<any>(id ? `/admin/users/${id}` : null);
  const [plan, setPlan] = useState("assistant");
  const [months, setMonths] = useState(1);
  const act = async (body: any) => {
    try {
      await api(`/admin/users/${id}`, { method: "PATCH", body });
      notify({ tone: "success", title: "Updated" });
      mutate();
    } catch (e) {
      notify({ tone: "error", title: "Failed", body: errorMessage(e) });
    }
  };
  return (
    <Modal open={!!id} onClose={onClose} title={data?.user?.email || "User"} size="lg">
      {!data ? <Skeleton className="h-40" /> : (
        <div className="space-y-5 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={data.user.status === "active" ? "success" : "danger"}>{data.user.status}</Badge>
            <Badge>{data.user.role}</Badge>
            <Badge tone="brand">{data.usage.plan.name}</Badge>
            <span className="text-muted">joined {formatDate(data.user.created_at)} · AI cost ${data.usage.ai_cost_usd}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {Object.entries(data.usage.usage).map(([k, v]: any) => (
              <div key={k} className="rounded-xl bg-surface-2 p-3"><div className="text-xs text-muted">{k.replace("_", " ")}</div><div className="font-semibold tabular-nums">{v.used} / {v.limit === -1 ? "∞" : v.limit ?? "—"}</div></div>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Grant plan (schools, support)"><Select value={plan} onChange={(e) => setPlan(e.target.value)}>{["teacher", "pro", "assistant"].map((p) => <option key={p}>{p}</option>)}</Select></Field>
            <Field label="Months"><Input type="number" min={1} max={36} value={months} onChange={(e) => setMonths(Number(e.target.value))} /></Field>
            <Button onClick={() => act({ plan, months })}>Grant</Button>
            <Button variant="outline" onClick={() => act({ extend_trial_days: 7 })}>Extend trial 7 days</Button>
            <Button variant="outline" onClick={() => act({ credits_grant: 200 })}>+200 credits</Button>
            {data.user.status === "active" ? <Button variant="danger" onClick={() => act({ status: "suspended" })}>Suspend</Button> : <Button variant="outline" onClick={() => act({ status: "active" })}>Reactivate</Button>}
          </div>
          <div>
            <div className="mb-2 font-medium text-ink">Projects</div>
            <ul className="space-y-1">{data.projects.map((p: any) => <li key={p.id} className="flex justify-between"><span>{p.topic} · Grade {p.grade}</span><Badge>{p.status}</Badge></li>)}</ul>
          </div>
          <div>
            <div className="mb-2 font-medium text-ink">Recent jobs</div>
            <ul className="space-y-1">{data.jobs.map((j: any) => <li key={j.id} className="flex justify-between gap-2"><span className="truncate">{j.type} · {timeAgo(j.created_at)}</span><Badge tone={j.status === "failed" ? "danger" : "neutral"}>{j.status}</Badge></li>)}</ul>
          </div>
        </div>
      )}
    </Modal>
  );
}

