"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { Download, Smartphone } from "lucide-react";
import { Button, Card, CardHeader } from "@/components/ui";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> };
type MobileState = { registration: ServiceWorkerRegistration | null; install: InstallEvent | null; installed: boolean; ios: boolean };
const MobileContext = createContext<MobileState>({ registration: null, install: null, installed: false, ios: false });

export function MobileAppProvider({ children }: { children: React.ReactNode }) {
  const [registration, setRegistration] = useState<ServiceWorkerRegistration | null>(null);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  const [installed, setInstalled] = useState(false);
  const [ios, setIos] = useState(false);
  useEffect(() => {
    const standalone = window.matchMedia("(display-mode: standalone)");
    setInstalled(standalone.matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
    setIos(/iPad|iPhone|iPod/.test(navigator.userAgent) || navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
    const ready = (event: Event) => { event.preventDefault(); setInstall(event as InstallEvent); };
    const done = () => { setInstalled(true); setInstall(null); };
    window.addEventListener("beforeinstallprompt", ready);
    window.addEventListener("appinstalled", done);
    if (window.isSecureContext && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" })
        .then(() => navigator.serviceWorker.ready).then(setRegistration).catch(() => { /* App remains usable when installation is unsupported. */ });
    }
    return () => { window.removeEventListener("beforeinstallprompt", ready); window.removeEventListener("appinstalled", done); };
  }, []);
  return <MobileContext.Provider value={{ registration, install, installed, ios }}>{children}</MobileContext.Provider>;
}

export const useMobileApp = () => useContext(MobileContext);

export function InstallAppCard() {
  const { install, installed, ios } = useMobileApp();
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [error, setError] = useState("");
  const prompt = async () => {
    if (!install) return;
    setBusy(true);
    setError("");
    try {
      await install.prompt();
      await install.userChoice;
      setDismissed(true); // A browser install event can only be used once, whichever choice was made.
    } catch { setError("Use your browser menu to install Clastio."); }
    finally { setBusy(false); }
  };
  return <Card id="install-app">
    <CardHeader title="Clastio on your phone" subtitle="Open Clastio from your home screen, like an app." />
    <div className="space-y-3 p-5 text-sm text-muted">
      <div className="flex items-start gap-3"><Smartphone className="h-5 w-5 shrink-0 text-brand-600" />
        <p>{installed ? "Clastio is installed on this device." : ios
          ? "On iPhone or iPad, open the browser Share menu, choose Add to Home Screen, then open Clastio using the new icon."
          : "In Chrome on Android or desktop, choose Install Clastio when offered, or use the browser menu and choose Install app / Add to Home Screen."}</p>
      </div>
      {!installed && install && !dismissed && <Button onClick={prompt} loading={busy}><Download className="h-4 w-4" /> Install Clastio</Button>}
      {error && <p role="alert">{error}</p>}
      <p className="text-xs">An internet connection is needed to load your lessons and generate content. Device notifications are optional below.</p>
    </div>
  </Card>;
}
