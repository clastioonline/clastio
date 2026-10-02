"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";

export function ConnectionStatus() {
  const [offline, setOffline] = useState(false);
  useEffect(() => {
    const update = () => setOffline(!navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => { window.removeEventListener("online", update); window.removeEventListener("offline", update); };
  }, []);
  if (!offline) return null;
  return <div role="status" className="sticky top-0 z-[100] flex items-center justify-center gap-2 bg-warn-50 px-4 py-3 text-sm text-warn-700"><WifiOff className="h-4 w-4 shrink-0" /><p>You’re offline. Submitted tasks continue on the server. Reconnect before saving new changes.</p></div>;
}
