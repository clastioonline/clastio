"use client";

import { ArrowRight, Check, Clock, Lightbulb } from "lucide-react";
import { useEffect, useState } from "react";
import { startWalkthrough } from "@/components/app-walkthrough";
import { DashHeader, PillButton } from "@/components/dash";
import { Modal } from "@/components/ui";
import { useApi } from "@/lib/hooks";
import { TUTORIALS, SETUP_STEPS, type Tutorial } from "@/lib/tutorials";
import { cn } from "@/lib/utils";

function TutorialModal({ t, onClose }: { t: Tutorial | null; onClose: () => void }) {
  return (
    <Modal open={!!t} onClose={onClose} title={t?.title || ""} size="lg"
      footer={t && <PillButton href={t.href}>{t.cta} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></PillButton>}>
      {t && (
        <div className="space-y-5">
          <p className="text-ink-2">{t.summary}</p>
          <ol className="space-y-3">
            {t.steps.map((s, i) => (
              <li key={i} className="flex gap-3">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-brand-600 text-sm font-semibold text-white">{i + 1}</span>
                <span className="pt-0.5 text-ink">{s}</span>
              </li>
            ))}
          </ol>
          {t.tip && <p className="flex gap-2 rounded-2xl bg-accent-50 p-3 text-sm text-ink-2"><Lightbulb className="mt-0.5 h-4 w-4 shrink-0 text-accent-600" />{t.tip}</p>}
        </div>
      )}
    </Modal>
  );
}

export default function Tutorials() {
  const { data } = useApi<any>("/me/dashboard");
  const [open, setOpen] = useState<Tutorial | null>(null);
  const checklist = data?.checklist || {};
  const done = SETUP_STEPS.filter((s) => checklist[s.check!]).length;

  useEffect(() => {
    const id = window.location.hash.slice(1);
    const t = TUTORIALS.find((x) => x.id === id);
    if (t) setOpen(t);
  }, []);

  return (
    <div className="space-y-6">
      <DashHeader title="Tutorials & help" subtitle="Short guides to get the most out of Clastio. Each takes two or three minutes." />

      <PillButton onClick={startWalkthrough}>Start the complete app walkthrough <ArrowRight className="h-4 w-4" /></PillButton>

      <section className="ui-hero flex flex-col gap-5 overflow-hidden rounded-3xl bg-brand-800 p-6 text-white sm:flex-row sm:items-center sm:justify-between sm:p-8">
        <div>
          <div className="text-sm text-white/75">Your setup</div>
          <div className="mt-1 text-2xl font-bold sm:text-3xl">{done} of {SETUP_STEPS.length} steps done</div>
          <div className="mt-3 h-2 w-72 max-w-full overflow-hidden rounded-full bg-white/20"><div className="h-full rounded-full bg-accent-400" style={{ width: `${(done / SETUP_STEPS.length) * 100}%` }} /></div>
        </div>
        <p className="max-w-md text-white/80">Finish these once and Clastio knows your design, your classes and your week, so every lesson it prepares fits.</p>
      </section>

      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {TUTORIALS.map((t) => {
          const ok = t.check ? checklist[t.check] : false;
          return (
            <button key={t.id} id={t.id} onClick={() => setOpen(t)}
              className="focus-ring group flex flex-col overflow-hidden rounded-3xl bg-surface text-start transition hover:shadow-[var(--shadow-pop)]">
              <div className="relative grid aspect-[16/9] place-items-center" style={{ background: t.color }}>
                <span className="grid h-16 w-16 place-items-center rounded-2xl bg-white/90 text-[#141414] shadow-sm transition group-hover:scale-105"><t.icon className="h-8 w-8" /></span>
                {ok && <span className="absolute end-3 top-3 flex items-center gap-1 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-brand-700"><Check className="h-3.5 w-3.5" />Done</span>}
              </div>
              <div className="flex flex-1 flex-col p-5">
                <h2 className={cn("font-semibold text-ink")}>{t.title}</h2>
                <p className="mt-1 flex-1 text-sm text-muted">{t.summary}</p>
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1.5 text-muted"><Clock className="h-4 w-4" />{t.minutes} min</span>
                  <span className="font-semibold text-brand-600 group-hover:underline">Read guide</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>

      <section className="rounded-3xl bg-surface p-6">
        <h2 className="text-lg font-semibold text-ink">Still stuck?</h2>
        <p className="mt-1 text-muted">Ask the assistant in plain words, for example “How do I make a quiz for 8B?”. It can also do the task for you.</p>
        <div className="mt-4"><PillButton href="/assistant" variant="outline">Ask the assistant</PillButton></div>
      </section>
      <TutorialModal t={open} onClose={() => { setOpen(null); history.replaceState(null, "", "/tutorials"); }} />
    </div>
  );
}
