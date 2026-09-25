"use client";

import { SWRConfig } from "swr";
import { CookieBanner } from "@/components/cookie-banner";
import { ToastProvider } from "@/components/toast";
import { fetcher } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false }}>
      <ThemeProvider>
        <I18nProvider>
          <ToastProvider>{children}<CookieBanner /></ToastProvider>
        </I18nProvider>
      </ThemeProvider>
    </SWRConfig>
  );
}
