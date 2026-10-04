"use client";

import { useState } from "react";
import { AdminActivity } from "@/components/admin-activity";
import { ActivityList, ActivityOverview, useActivity } from "@/components/activity-center";
import { Button, PageHeader, Tabs } from "@/components/ui";
import { useMe } from "@/lib/hooks";

export default function ActivityPage() {
  const [filter, setFilter] = useState("all");
  const { count, refresh } = useActivity();
  const { user } = useMe();
  if (user?.role === "admin") return <AdminActivity />;
  return <div className="mx-auto max-w-4xl space-y-6">
    <PageHeader title="Activity" subtitle="Start something, then get on with your day. Your latest 100 tasks live here, with active work shown first." actions={<Button variant="outline" onClick={refresh}>Refresh</Button>} />
    <ActivityOverview />
    <Tabs value={filter} onChange={setFilter} tabs={[{ value: "all", label: "All work" }, { value: "working", label: `In progress (${count})` }, { value: "succeeded", label: "Ready" }, { value: "failed", label: "Needs attention" }]} />
    <ActivityList filter={filter} />
  </div>;
}
