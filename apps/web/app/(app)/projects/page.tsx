"use client";

import { Plus, Presentation, Search } from "lucide-react";
import { useState } from "react";
import { ProjectCard } from "@/components/common";
import { Button, EmptyState, Input, PageHeader, Skeleton } from "@/components/ui";
import { LoadError } from "@/components/load-error";
import { useApi } from "@/lib/hooks";

export default function Projects() {
  const [q, setQ] = useState("");
  const { data, error, mutate } = useApi<any>(`/projects${q ? `?q=${encodeURIComponent(q)}` : ""}`, { refreshInterval: 5000 });
  return (
    <div>
      <PageHeader title="Lessons & PPTs" subtitle="Every unit you've planned, with its lessons, slides and documents."
        actions={<Button href="/projects/new"><Plus className="h-4 w-4" /> New course</Button>} />
      <div className="relative mb-5 max-w-sm">
        <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <Input className="ps-9" placeholder="Search topics…" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {error ? <LoadError retry={mutate} label="your projects" /> : !data ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-60" />)}</div>
      ) : data.items.length ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">{data.items.map((p: any) => <ProjectCard key={p.id} p={p} />)}</div>
      ) : (
        <EmptyState icon={<Presentation className="h-6 w-6" />} title={q ? "No matching projects" : "No projects yet"}
          description="Plan a topic as a sequence of connected lessons, each with its own slides, notes and activities."
          action={<Button href="/projects/new"><Plus className="h-4 w-4" /> Create your first course</Button>} />
      )}
    </div>
  );
}
