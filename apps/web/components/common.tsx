"use client";

import { FolderKanban, LoaderCircle } from "lucide-react";
import Link from "next/link";
import { Badge, Progress } from "@/components/ui";
import type { Job } from "@/lib/hooks";
import { STATUS_TONE, cn } from "@/lib/utils";

export function StatusBadge({ status }: { status: string }) {
  const label: Record<string, string> = {
    generated: "Ready", ready: "Ready", generating: "Preparing", planned: "Planned", planning: "Planning",
    reflected: "Taught", taught: "Taught", failed: "Failed", partial: "Partly ready", processing: "Working", queued: "Queued",
  };
  return (
    <Badge tone={STATUS_TONE[status] || "neutral"}>
      {(status === "generating" || status === "planning" || status === "processing") && <LoaderCircle className="h-3 w-3 animate-spin" />}
      {label[status] || status}
    </Badge>
  );
}

export function ClassChip({ name, color }: { name: string; color?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-xs font-semibold text-white" style={{ background: color || "#4f46e5" }}>
      {name}
    </span>
  );
}

export function SlideThumb({ src, alt, className }: { src?: string | null; alt: string; className?: string }) {
  return (
    <div className={cn("aspect-[16/9] self-start overflow-hidden rounded-lg border border-line bg-surface-2", className)}>
      {src ? <img src={src} alt={alt} className="h-full w-full object-cover" loading="lazy" /> : (
        <div className="grid h-full place-items-center text-muted"><FolderKanban className="h-6 w-6" /></div>
      )}
    </div>
  );
}

export function ProjectCard({ p }: { p: any }) {
  const pct = p.lessons_total ? Math.round((p.lessons_ready / p.lessons_total) * 100) : 0;
  return (
    <Link href={`/projects/${p.id}`} className="focus-ring group block rounded-2xl border border-line bg-surface p-3 shadow-[var(--shadow-card)] transition hover:-translate-y-0.5 hover:border-brand-200">
      <SlideThumb src={p.cover} alt={p.title} />
      <div className="mt-3 px-1">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-1 font-medium text-ink group-hover:text-brand-700">{p.course.topic}</h3>
          <StatusBadge status={p.status} />
        </div>
        <div className="mt-1 text-xs text-muted">Grade {p.course.grade} · {p.course.subject} · {p.lessons_total} lessons × {p.course.slides_per_lecture} slides</div>
        {p.lessons_total > 0 && <Progress value={pct} className="mt-3 h-1.5" tone={pct === 100 ? "success" : "brand"} />}
      </div>
    </Link>
  );
}

export function JobLine({ job }: { job: Job | null }) {
  if (!job) return null;
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-muted">
        <span>{job.stage || "Working"}</span>
        <span className="tabular-nums">{job.progress}%</span>
      </div>
      <Progress value={job.progress} />
    </div>
  );
}
