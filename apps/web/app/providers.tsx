"use client";

import { SWRConfig } from "swr";
import { ToastProvider } from "@/components/toast";
import { fetcher } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false }}>
      <I18nProvider>
        <ToastProvider>{children}</ToastProvider>
      </I18nProvider>
    </SWRConfig>
  );
}
