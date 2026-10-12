"use client";

import { FileText, Printer } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { ChapterSources } from "@/components/chapter-sources";
import { Alert, Badge, Button, Card, EmptyState, Field, Input, Progress, Select } from "@/components/ui";
import { useApi, type Job } from "@/lib/hooks";
import { normalizeTeacherCourseSelection, teacherCourseOptions, teacherEducationStage, teacherEducationStages, type TeacherCourseClass } from "@/lib/teacher-course-options";

export const EDUCATION_STAGES = [
  { value: "early_years", label: "Early Years" },
  { value: "primary", label: "Primary" },
  { value: "secondary", label: "Secondary" },
  { value: "university", label: "University" },
] as const;

export type EducatorContext = {
  topic: string; subject: string; grade: string; education_stage: string;
  curriculum: string; language: string; framework: string;
  source_file_ids: string[]; source_page_ranges: Record<string, [number, number]>;
};

export const INITIAL_EDUCATOR_CONTEXT: EducatorContext = {
  topic: "", subject: "Science", grade: "6", education_stage: "primary",
  curriculum: "UAE MoE", language: "en", framework: "not_specified",
  source_file_ids: [], source_page_ranges: {},
};

type EducatorProfile = {
  subjects?: string[]; grades?: string[]; curriculum?: string; teaching_languages?: string[];
  regulatory_authority?: string; education_stages?: string[];
};

export function useEducatorTeachingScope() {
  const { data: profile, error: profileError, mutate: refreshProfile } = useApi<EducatorProfile>("/me/profile");
  const { data: classes, error: classesError, mutate: refreshClasses } = useApi<{ items: TeacherCourseClass[] }>("/classes");
  const options = useMemo(() => teacherCourseOptions(profile || {}, classes?.items || []), [profile, classes]);
  const stages = useMemo(() => teacherEducationStages(profile || {}, options.grades), [profile, options.grades]);
  const ready = Boolean(profile && classes && !profileError && !classesError);
  return { profile, options, stages, ready, error: profileError || classesError, refresh: () => { refreshProfile(); refreshClasses(); } };
}

/** Saved preferences fill the form once; they never replace an in-progress brief. */
export function useEducatorContext(initial: EducatorContext = INITIAL_EDUCATOR_CONTEXT): [EducatorContext, Dispatch<SetStateAction<EducatorContext>>, ReturnType<typeof useEducatorTeachingScope>] {
  const [value, setValue] = useState<EducatorContext>({ ...initial });
  const teaching = useEducatorTeachingScope();
  const { profile } = teaching;
  const initialized = useRef(false);
  const edited = useRef(false);
  useEffect(() => {
    if (!profile || initialized.current) return;
    initialized.current = true;
    if (edited.current) return;
    setValue(previous => {
      const savedGrade = profile.grades?.[0]?.trim() || "";
      const grade = savedGrade || previous.grade;
      const schoolYear = Number(savedGrade.replace(/^(?:grade|year)\s*/i, ""));
      const inferredStage = /university|undergraduate|postgraduate|college/i.test(savedGrade) ? "university"
        : /nursery|reception|kindergarten|early years|^kg\s*[12]?$|^fs\s*[12]$/i.test(savedGrade) ? "early_years"
        : schoolYear >= 1 && schoolYear <= 6 ? "primary" : schoolYear >= 7 && schoolYear <= 13 ? "secondary" : previous.education_stage;
      const stage = profile.education_stages?.find(item => EDUCATION_STAGES.some(stage => stage.value === item)) || inferredStage;
      const framework = ["khda", "adek", "moe", "other", "not_specified"].includes(profile.regulatory_authority || "") ? profile.regulatory_authority! : "not_specified";
      return { ...previous, subject: profile.subjects?.[0] || previous.subject, grade,
        curriculum: profile.curriculum || previous.curriculum, language: profile.teaching_languages?.find(item => ["en", "ar"].includes(item)) || previous.language,
        education_stage: stage, framework: stage === "university" && ["khda", "adek", "moe"].includes(framework) ? "not_specified" : framework };
    });
  }, [profile]);
  useEffect(() => {
    if (!teaching.ready) return;
    setValue(previous => {
      const selection = normalizeTeacherCourseSelection({ ...previous, class_section_id: "" }, teaching.options);
      const inferredStage = teacherEducationStage(selection.grade);
      const stage = teaching.stages.includes(previous.education_stage) ? previous.education_stage
        : inferredStage && teaching.stages.includes(inferredStage) ? inferredStage : teaching.stages[0] || "";
      const framework = stage === "university" && ["khda", "adek", "moe"].includes(previous.framework) ? "not_specified" : previous.framework;
      if (previous.subject === selection.subject && previous.grade === selection.grade && previous.education_stage === stage && previous.framework === framework) return previous;
      return { ...previous, subject: selection.subject, grade: selection.grade, education_stage: stage, framework };
    });
  }, [teaching.ready, teaching.options, teaching.stages]);
  const update = useCallback<Dispatch<SetStateAction<EducatorContext>>>(next => { edited.current = true; setValue(next); }, []);
  return [value, update, teaching];
}

/** Shared deep links make completed work reachable from Activity and browser history. */
export function useEducatorSelection(): [string | null, (id: string | null) => void] {
  const params = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const selected = params.get("id");
  return [selected, id => {
    const next = new URLSearchParams(params.toString());
    if (id) next.set("id", id); else next.delete("id");
    router.push(`${pathname}${next.size ? `?${next}` : ""}`, { scroll: false });
  }];
}

export function EducatorContextFields({ value, onChange, topicLabel = "Topic", showFramework = true }: {
  value: EducatorContext; onChange: (next: EducatorContext) => void; topicLabel?: string; showFramework?: boolean;
}) {
  const teaching = useEducatorTeachingScope();
  const update = (key: keyof EducatorContext, next: string) => onChange({ ...value, [key]: next });
  return <div className="grid min-w-0 gap-4 sm:grid-cols-2">
    <Field label={topicLabel} className="sm:col-span-2"><Input required maxLength={300} value={value.topic} onChange={event => update("topic", event.target.value)} placeholder="Ecosystems and UAE mangroves" /></Field>
    <div className="sm:col-span-2">{teaching.error ? <Alert tone="danger">Could not load your teaching profile. <Button size="sm" variant="outline" onClick={teaching.refresh}>Try again</Button></Alert>
      : <p className="text-sm text-muted">{!teaching.ready ? "Loading your teaching subjects and grades…" : teaching.options.subjects.length && teaching.options.grades.length ? "Choose from the subjects and grades in your teaching profile." : "Add your teaching subjects and grades before generating resources."} <Link href="/settings" className="font-semibold text-brand-700 underline">Update teaching profile</Link></p>}</div>
    <Field label="Subject"><Select aria-label="Subject" required value={teaching.options.subjects.includes(value.subject) ? value.subject : ""} disabled={!teaching.ready || !teaching.options.subjects.length} onChange={event => update("subject", event.target.value)}><option value="" disabled>Select your subject</option>{teaching.options.subjects.map(subject => <option key={subject}>{subject}</option>)}</Select></Field>
    <Field label="Education stage"><Select aria-label="Education stage" required value={teaching.stages.includes(value.education_stage) ? value.education_stage : ""} disabled={!teaching.ready || !teaching.stages.length} onChange={event => onChange({ ...value, education_stage: event.target.value, framework: event.target.value === "university" ? "not_specified" : value.framework })}><option value="" disabled>Select education stage</option>{EDUCATION_STAGES.filter(stage => teaching.stages.includes(stage.value)).map(stage => <option key={stage.value} value={stage.value}>{stage.label}</option>)}</Select></Field>
    <Field label={value.education_stage === "university" ? "Course level / year" : "Grade / year"}><Select aria-label="Grade / year" required value={teaching.options.grades.includes(value.grade) ? value.grade : ""} disabled={!teaching.ready || !teaching.options.grades.length} onChange={event => {
      const grade = event.target.value;
      const inferredStage = teacherEducationStage(grade);
      const education_stage = inferredStage && teaching.stages.includes(inferredStage) ? inferredStage : value.education_stage;
      onChange({ ...value, grade, education_stage, framework: education_stage === "university" ? "not_specified" : value.framework });
    }}><option value="" disabled>Select your grade / year</option>{teaching.options.grades.map(grade => <option key={grade}>{grade}</option>)}</Select></Field>
    <Field label="Curriculum"><Select value={value.curriculum} onChange={event => update("curriculum", event.target.value)}>{Array.from(new Set([value.curriculum, "UAE MoE", "British", "American", "IB", "CBSE", "University", "Other"])).map(curriculum => <option key={curriculum}>{curriculum}</option>)}</Select></Field>
    <Field label="Output language"><Select value={value.language} onChange={event => update("language", event.target.value)}><option value="en">English</option><option value="ar">Arabic</option></Select></Field>
    {showFramework && <Field label="Planning framework" hint={value.education_stage === "university" ? "Choose your institution’s framework or no school framework. School inspection frameworks do not apply to university lessons." : "Choose the framework used by your school. This is a teacher-reviewed draft, not regulator approval."}><Select value={value.framework} onChange={event => update("framework", event.target.value)}>{value.education_stage !== "university" && <><option value="khda">Dubai · KHDA</option><option value="adek">Abu Dhabi · ADEK</option><option value="moe">UAE · MoE</option></>}<option value="other">Other framework</option><option value="not_specified">No school framework</option></Select></Field>}
  </div>;
}

export function EducatorSources({ value, onChange, onBlocked }: { value: EducatorContext; onChange: (value: EducatorContext) => void; onBlocked: (blocked: boolean) => void }) {
  return <div className="space-y-2"><ChapterSources maxFiles={5} value={value.source_file_ids} onChange={ids => {
    const selected = ids.slice(0, 5);
    onChange({ ...value, source_file_ids: selected, source_page_ranges: Object.fromEntries(Object.entries(value.source_page_ranges).filter(([id]) => selected.includes(id))) });
  }} onBlocked={onBlocked} pageRanges={value.source_page_ranges} onPagesChange={ranges => onChange({ ...value, source_page_ranges: ranges })} />
    <p className="px-1 text-xs text-muted">Use up to five saved books or notes. Choose chapter pages to ground your draft in the right material.</p>
  </div>;
}

export type EducatorItem = { id: string; title: string; topic?: string; subject?: string; grade?: string; language?: string; status: string; education_stage?: string; origin?: string; kind?: string; framework?: string; error?: string; version?: number; content?: Record<string, unknown> | null; downloads?: Record<string, string | null>; job?: Job | null; [key: string]: unknown };

export function SavedEducatorItems({ items, selected, onSelect, title = "Saved drafts", empty }: { items: EducatorItem[]; selected: string | null; onSelect: (id: string) => void; title?: string; empty: string }) {
  return <Card className="min-w-0 p-4"><h2 className="mb-3 font-semibold text-ink">{title}</h2>{!items.length ? <EmptyState icon={<FileText className="h-5 w-5" />} title={empty} description="Your finished work stays available here for future use." /> : <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">{items.map(item => <button type="button" key={item.id} aria-pressed={selected === item.id} onClick={() => onSelect(item.id)} className={`focus-ring min-w-0 rounded-xl border p-3 text-start ${selected === item.id ? "border-brand-500 bg-brand-50" : "border-line hover:bg-surface-2"}`}><span className="block break-words font-medium text-ink">{item.title}</span><span className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">{item.subject} {item.grade && `· ${item.grade}`}<Badge tone={item.status === "failed" ? "danger" : item.status === "reviewed" ? "success" : "neutral"}>{item.status.replaceAll("_", " ")}</Badge>{item.origin === "generated" && <Badge tone="brand">AI-generated guide</Badge>}</span></button>)}</div>}</Card>;
}

export function EducatorJobStatus({ job }: { job?: Job | null }) {
  if (!job) return null;
  if (job.status === "failed" || job.status === "cancelled") return <Alert tone="danger" title={job.status === "failed" ? "Generation could not finish" : "Generation cancelled"}>{job.error || "Your request is saved. Review your inputs and try again."}</Alert>;
  if (job.status === "succeeded") return <Alert tone="success" title="Ready for your review">Your generated draft has been saved.</Alert>;
  return <Alert tone="brand" title={job.stage || "Preparing your draft"}><Progress value={job.progress || 0} className="mt-2" /><p className="mt-2 text-xs">You can leave this page. Your work continues in Activity.</p></Alert>;
}

const LABELS: Record<string, string> = {
  sen: "SEN / students of determination", ell: "ELL / language support", uae_context: "UAE connections", teacher_says: "Teacher script", teacher_does: "Teacher actions", url_or_file_id: "Source", page_or_section: "Page / section", question_or_task: "Question / task", connection_or_reason: "Connection and relevance", review_checks: "Teacher review checks", source_references: "Sources", observable_action: "Observable action", success_measure: "Success measure", printable_task: "Printable classroom task", expected_answers: "Teacher answer key",
};
const OMIT = new Set(["schema_version", "id", "cache_key", "origin", "alignment_status", "objective_ids", "assessment_ids"]);
function label(key: string) { return LABELS[key] || key.replaceAll("_", " ").replace(/^./, letter => letter.toUpperCase()); }

function DocumentValue({ value, depth = 0 }: { value: unknown; depth?: number }): ReactNode {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "boolean") return <span>{value ? "Yes" : "No"}</span>;
  if (typeof value === "string" && /^https:\/\/\S+$/i.test(value)) return <a className="break-all text-sm text-brand-700 underline" href={value} target="_blank" rel="noopener noreferrer">{value}</a>;
  if (typeof value === "string" && /^[\da-f]{8}(?:-[\da-f]{4}){3}-[\da-f]{12}$/i.test(value)) return <p className="text-sm text-muted">Saved source from your book library</p>;
  if (typeof value === "string" || typeof value === "number") return <p className="whitespace-pre-wrap break-words text-sm leading-6 text-ink-2">{String(value)}</p>;
  if (Array.isArray(value)) return <div className="space-y-3">{value.map((item, index) => <div key={index} className={typeof item === "object" && item !== null ? "rounded-xl border border-line p-3" : "border-s-2 border-brand-200 ps-3"}><DocumentValue value={item} depth={depth + 1} /></div>)}</div>;
  if (typeof value !== "object") return null;
  return <div className="space-y-3">{Object.entries(value as Record<string, unknown>).filter(([key, item]) => !OMIT.has(key) && item !== null && item !== "" && (!Array.isArray(item) || item.length > 0)).map(([key, item]) => <Fragment key={key}><div className="min-w-0"><div className={`${depth ? "mb-1 text-xs font-semibold uppercase tracking-wide text-muted" : "mb-2 text-base font-semibold text-ink"}`}>{label(key)}</div><DocumentValue value={item} depth={depth + 1} /></div></Fragment>)}</div>;
}

export function EducatorDocument({ title, content, downloads, children, language }: { title: string; content: unknown; downloads?: Record<string, string | null>; children?: ReactNode; language?: string }) {
  const contentLanguage = language || (content && typeof content === "object" && "language" in content ? String(content.language) : "en");
  return <Card className="min-w-0 p-5 sm:p-6"><div className="mb-5 flex flex-wrap items-start justify-between gap-3"><h2 className="min-w-0 break-words text-xl font-semibold text-ink">{title}</h2><div className="flex flex-wrap gap-2">{Object.entries(downloads || {}).filter(([, url]) => !!url).map(([format, url]) => <Button key={format} variant="outline" size="sm" href={url!}>Download {format === "slides_pdf" ? "Slides PDF" : format.toUpperCase()}</Button>)}<Button variant="outline" size="sm" onClick={() => window.print()}><Printer className="h-4 w-4" /> Print / save PDF</Button></div></div>{children}<article data-educator-document dir={contentLanguage === "ar" ? "rtl" : "ltr"} lang={contentLanguage} className="space-y-5"><h1 className="hidden print:block">{title}</h1><DocumentValue value={content} /></article><style jsx global>{`@media print { body * { visibility: hidden !important; } [data-educator-document], [data-educator-document] * { visibility: visible !important; } [data-educator-document] { position: absolute; inset: 0; padding: 24px; background: white; color: black; width: 100%; } [data-educator-document] p { color: black; } [data-educator-document] h1 { margin-bottom: 24px; font-size: 24px; } }`}</style></Card>;
}
