"use client";

import { Compass } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Button, Modal } from "@/components/ui";
import { walkthroughSteps } from "@/lib/walkthrough";
import type { User } from "@/lib/hooks";

type Progress = { index: number; pageOnly: boolean; page: string; completed?: boolean };
export function startWalkthrough() { window.dispatchEvent(new CustomEvent("clastio:walkthrough", { detail: { full: true } })); }

export function AppWalkthrough({ user }: { user: User }) {
  const pathname = usePathname();
  const router = useRouter();
  const key = `clastio:walkthrough:v1:${user.id}`;
  const [open, setOpen] = useState(false);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [saved, setSaved] = useState<Progress | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [origin, setOrigin] = useState(pathname);
  const steps = walkthroughSteps(progress?.page || pathname, user.role === 'admin', user.permissions || [], progress?.pageOnly || false);
  const index = Math.min(progress?.index || 0, Math.max(0, steps.length - 1));
  const step = steps[index];
  const pageSteps = walkthroughSteps(pathname, user.role === 'admin', user.permissions || [], true);
  useEffect(() => {
    setOpen(false); setProgress(null);
    try { setSaved(JSON.parse(localStorage.getItem(key) || 'null')); } catch { setSaved(null); }
  }, [key]);
  useEffect(() => {
    const listener = () => { setOrigin(pathname); setProgress({ index: 0, pageOnly: false, page: pathname }); setOpen(true); };
    window.addEventListener('clastio:walkthrough', listener);
    return () => window.removeEventListener('clastio:walkthrough', listener);
  }, [pathname]);
  useEffect(() => {
    if (!open || !progress || !step) return;
    if (pathname !== step.route) router.push(step.route);
  }, [open, progress, step, pathname, router]);
  useEffect(() => {
    if (!open || !progress) return;
    try { localStorage.setItem(key, JSON.stringify(progress)); setSaved(progress); } catch { /* Storage is optional. */ }
  }, [key, open, progress]);
  useEffect(() => {
    if (!open || !progress || pathname !== step?.route || !step?.target) return;
    let target: HTMLElement | null = null;
    const highlight = () => {
      target = document.querySelector<HTMLElement>(step.target!);
      if (target) { target.scrollIntoView({ behavior: 'smooth', block: 'center' }); target.classList.add('walkthrough-highlight'); }
    };
    const timer = setTimeout(highlight, 350);
    return () => { clearTimeout(timer); target?.classList.remove('walkthrough-highlight'); };
  }, [open, progress, pathname, step]);
  const close = () => { setOpen(false); setProgress(null); setTimeout(() => trigger.current?.focus(), 0); };
  const finish = () => {
    const done = { index: 0, pageOnly: false, page: origin, completed: true };
    try { localStorage.setItem(key, JSON.stringify(done)); } catch { /* Optional persistence. */ }
    setSaved(done); close(); router.push(origin);
  };
  return <>
    <button ref={trigger} type="button" aria-label="Walkthrough" title="Walkthrough" className="focus-ring grid h-11 w-11 shrink-0 place-items-center rounded-full bg-surface text-ink-2 hover:text-brand-600" onClick={() => { setOrigin(pathname); setProgress(null); setOpen(true); }}><Compass className="h-5 w-5" /></button>
    <Modal open={open} onClose={close} title={progress && step ? step.title : 'Explore Clastio'} size="md" footer={progress ? <>
      <Button variant="ghost" onClick={close}>Pause tour</Button>
      <Button variant="outline" disabled={index === 0} onClick={() => setProgress({ ...progress, index: index - 1 })}>Back</Button>
      <Button onClick={() => index === steps.length - 1 ? finish() : setProgress({ ...progress, index: index + 1 })}>{index === steps.length - 1 ? 'Finish walkthrough' : 'Next step'}</Button>
    </> : undefined}>
      {progress && step ? <div className="space-y-4" aria-live="polite"><p className="text-xs font-medium text-brand-600">Step {index + 1} of {steps.length}</p><p className="text-ink-2">{step.text}</p><p className="text-xs text-muted">This guide only navigates and explains. Creating lessons, sending messages and changing settings require your own action.</p></div> : <div className="space-y-4">
        <p className="text-ink-2">Learn the complete workflow or get help with this page. You can pause and replay the guide at any time.</p>
        {pageSteps.length > 0 && <Button className="w-full" variant="outline" onClick={() => setProgress({ index: 0, pageOnly: true, page: pathname })}>Guide this page</Button>}
        <Button className="w-full" onClick={() => setProgress({ index: 0, pageOnly: false, page: pathname })}>Tour the complete app</Button>
        {saved && !saved.completed && <Button className="w-full" variant="outline" onClick={() => setProgress(saved)}>Resume walkthrough</Button>}
      </div>}
    </Modal>
  </>;
}
