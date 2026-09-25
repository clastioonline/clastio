"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type Skin = "classic" | "forest";
export type Mode = "system" | "light" | "dark";

const SKIN_KEY = "ata-skin";
const MODE_KEY = "ata-mode";
const DEFAULT_KEY = "ata-skin-default";

/** Runs before first paint (inlined in <head>) so the stored look applies without a flash. */
export const THEME_BOOT_SCRIPT = `(function(){try{var d=document.documentElement;var s=localStorage.getItem("${SKIN_KEY}")||localStorage.getItem("${DEFAULT_KEY}");if(s!=="classic")d.setAttribute("data-skin","forest");var m=localStorage.getItem("${MODE_KEY}");if(m==="light"||m==="dark")d.setAttribute("data-theme",m);}catch(e){}})();`;

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* private mode: the choice lasts for this page view only */
  }
}

function apply(skin: Skin, mode: Mode) {
  const d = document.documentElement;
  if (skin === "forest") d.setAttribute("data-skin", "forest");
  else d.removeAttribute("data-skin");
  if (mode === "system") d.removeAttribute("data-theme");
  else d.setAttribute("data-theme", mode);
}

type Ctx = { skin: Skin; mode: Mode; setSkin: (s: Skin) => void; setMode: (m: Mode) => void };
const ThemeContext = createContext<Ctx>({ skin: "forest", mode: "system", setSkin: () => {}, setMode: () => {} });

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [skin, setSkinState] = useState<Skin>("forest");
  const [mode, setModeState] = useState<Mode>("system");

  useEffect(() => {
    const own = read(SKIN_KEY) as Skin | null;
    const m = (read(MODE_KEY) as Mode | null) || "system";
    setModeState(m);
    if (own) {
      setSkinState(own);
      apply(own, m);
      return;
    }
    // No personal choice: follow the admin's default.
    const cached = (read(DEFAULT_KEY) as Skin | null) || "forest";
    setSkinState(cached);
    apply(cached, m);
    fetch("/api/v1/public/config")
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => {
        const def: Skin = cfg?.default_skin === "classic" ? "classic" : "forest";
        write(DEFAULT_KEY, def);
        if (!read(SKIN_KEY)) {
          setSkinState(def);
          apply(def, m);
        }
      })
      .catch(() => {});
  }, []);

  const setSkin = useCallback((s: Skin) => {
    write(SKIN_KEY, s);
    setSkinState(s);
    apply(s, (read(MODE_KEY) as Mode | null) || "system");
  }, []);
  const setMode = useCallback((m: Mode) => {
    write(MODE_KEY, m === "system" ? null : m);
    setModeState(m);
    apply(document.documentElement.getAttribute("data-skin") === "forest" ? "forest" : "classic", m);
  }, []);

  return <ThemeContext.Provider value={{ skin, mode, setSkin, setMode }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
