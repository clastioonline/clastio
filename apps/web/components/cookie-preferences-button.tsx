"use client";

import { useEffect, useState } from "react";
import { requestCookiePreferences } from "@/lib/cookie-preferences";

export function CookiePreferencesButton() {
  const [ready, setReady] = useState(false);
  useEffect(() => setReady(true), []);
  return <button type="button" className="underline disabled:opacity-60" disabled={!ready} onClick={requestCookiePreferences}>Cookie preferences</button>;
}
