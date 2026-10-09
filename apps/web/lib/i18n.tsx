"use client";

import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

type Dict = Record<string, string>;

const ar: Dict = {
  "nav.activity": "النشاط",
  "nav.today": "اليوم",
  "nav.assistant": "المساعد",
  "nav.projects": "المشاريع",
  "nav.lessons": "الدروس والمستندات",
  "nav.calendar": "التقويم والجدول",
  "nav.curriculum": "الصفوف والمنهج",
  "nav.books": "الكتب والملاحظات",
  "nav.templates": "قوالب التصميم",
  "nav.media": "استوديو الوسائط",
  "nav.memory": "ذاكرة المعلم",
  "nav.whatsapp": "واتساب",
  "nav.billing": "الاشتراك",
  "nav.settings": "الإعدادات",
  "nav.admin": "الإدارة",
  "nav.signout": "تسجيل الخروج",
  "dash.todayClasses": "حصص اليوم",
  "dash.prepareToday": "حضّر دروس اليوم",
  "dash.prepareTomorrow": "حضّر الغد",
  "dash.prepareWeek": "حضّر أسبوعي",
  "dash.createPpt": "عرض تقديمي جديد",
  "dash.worksheet": "ورقة عمل",
  "dash.quiz": "اختبار قصير",
  "dash.recent": "المشاريع الأخيرة",
  "dash.templates": "قوالبك",
  "common.new": "جديد",
  "common.save": "حفظ",
  "common.download": "تنزيل",
};

const dicts: Record<string, Dict> = { ar };

type Ctx = { locale: string; dir: "ltr" | "rtl"; t: (key: string, fallback: string) => string; setLocale: (l: string) => void };

const I18nContext = createContext<Ctx>({ locale: "en", dir: "ltr", t: (_k, f) => f, setLocale: () => {} });

export function I18nProvider({ children, initial = "en" }: { children: ReactNode; initial?: string }) {
  const [locale, setLocaleState] = useState(initial);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("ata.locale");
      if (saved) setLocaleState(saved);
    } catch {}
  }, []);
  const dir: "ltr" | "rtl" = locale === "ar" ? "rtl" : "ltr";
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = dir;
  }, [locale, dir]);
  const value = useMemo<Ctx>(
    () => ({
      locale,
      dir,
      t: (key, fallback) => dicts[locale]?.[key] || fallback,
      setLocale: (l) => {
        setLocaleState(l);
        try {
          localStorage.setItem("ata.locale", l);
        } catch {}
      },
    }),
    [locale, dir],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
