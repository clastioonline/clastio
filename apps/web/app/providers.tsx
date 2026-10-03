"use client";

import { useEffect } from "react";
import dynamic from "next/dynamic";
import { SWRConfig } from "swr";
import { ConnectionStatus } from "@/components/connection-status";
const CookieBanner = dynamic(() => import("@/components/cookie-banner").then((mod) => mod.CookieBanner), { ssr: false });
import { ToastProvider } from "@/components/toast";
import { fetcher } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n";
import { ThemeProvider } from "@/lib/theme";

export function Providers({ children }: { children: React.ReactNode }) {
  const content = <div id="app-root"><ConnectionStatus />{children}<CookieBanner /></div>;
  useEffect(() => {
    const ref = new URLSearchParams(window.location.search).get("ref");
    if (ref && /^[a-f0-9]{8,16}$/i.test(ref)) {
      try { sessionStorage.setItem("clastio:referral", ref.toLowerCase()); } catch { /* storage is optional */ }
    }
  }, []);
  return (
    <SWRConfig value={{ fetcher, revalidateOnFocus: false }}>
      <ThemeProvider>
        <I18nProvider>
          <ToastProvider>{content}</ToastProvider>
        </I18nProvider>
      </ThemeProvider>
    </SWRConfig>
  );
}
