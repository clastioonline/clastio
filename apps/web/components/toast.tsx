"use client";

import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Toast = { id: number; tone: "success" | "error" | "info"; title: string; body?: string };
type Ctx = { notify: (t: Omit<Toast, "id">) => void };

const ToastContext = createContext<Ctx>({ notify: () => {} });

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const notify = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), t.tone === "error" ? 7000 : 4500);
  }, []);
  return (
    <ToastContext.Provider value={{ notify }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4 sm:inset-x-auto sm:end-4 sm:items-end" aria-live="polite">
        {items.map((t) => {
          const Icon = t.tone === "success" ? CircleCheck : t.tone === "error" ? CircleAlert : Info;
          return (
            <div key={t.id} className="pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border border-line bg-surface px-4 py-3 shadow-[var(--shadow-pop)]">
              <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", t.tone === "success" ? "text-success-500" : t.tone === "error" ? "text-danger-500" : "text-brand-600")} />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium text-ink">{t.title}</div>
                {t.body && <div className="mt-0.5 text-sm text-muted">{t.body}</div>}
              </div>
              <button className="text-muted hover:text-ink" onClick={() => setItems((xs) => xs.filter((x) => x.id !== t.id))} aria-label="Dismiss">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);

export function errorMessage(e: unknown): string {
  if (e && typeof e === "object" && "message" in e) return String((e as any).message);
  return "Something went wrong. Please try again.";
}
