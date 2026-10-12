"use client";

import { Check, Download, Trash } from "lucide-react";
import { useEffect, useState } from "react";
import { ConsentsCard, NotificationPrefsCard, SecurityCard } from "@/components/account-settings";
import { EDUCATION_STAGES } from "@/components/educator-workspace";
import { InstallAppCard } from "@/components/mobile-app";
import { PushNotificationsCard } from "@/components/push-notifications";
import { errorMessage, useToast } from "@/components/toast";
import { Button, Card, CardHeader, Chips, Field, Input, PageHeader, Select, Skeleton, Textarea, Toggle } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi, useMe } from "@/lib/hooks";
import { useI18n } from "@/lib/i18n";
import { useTheme, type Skin } from "@/lib/theme";
import { CURRICULA, DAYS, GRADES, SUBJECTS } from "@/lib/utils";

const SKINS: { value: Skin; label: string; desc: string; swatch: string[] }[] = [
  { value: "classic", label: "Classic", desc: "Indigo and amber, crisp cards", swatch: ["#4f46e5", "#f59e0b", "#f6f7fb"] },
  { value: "forest", label: "Forest", desc: "Calm greens, rounded and soft", swatch: ["#1b7446", "#74c495", "#f2f3f0"] },
];

function Appearance() {
  const { skin, mode, setSkin, setMode } = useTheme();
  return (
    <Card>
      <CardHeader title="Appearance" subtitle="Saved on this device" />
      <div className="space-y-4 p-5">
        <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label="Theme">
          {SKINS.map((s) => (
            <button key={s.value} role="radio" aria-checked={skin === s.value} onClick={() => setSkin(s.value)}
              className={`focus-ring relative rounded-2xl border p-3 text-start transition ${skin === s.value ? "border-brand-500 ring-2 ring-brand-200" : "border-line hover:border-line-strong"}`}>
              <div className="flex h-14 overflow-hidden rounded-xl">
                {s.swatch.map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}
              </div>
              <div className="mt-2 text-sm font-medium text-ink">{s.label}</div>
              <div className="text-xs text-muted">{s.desc}</div>
              {skin === s.value && <Check className="absolute end-3 top-3 h-4 w-4 rounded-full bg-brand-600 p-0.5 text-white" />}
            </button>
          ))}
        </div>
        <Field label="Light or dark">
          <Chips options={[{ value: "system", label: "Match device" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} value={mode} onChange={setMode} />
        </Field>
      </div>
    </Card>
  );
}

export default function Settings() {
  const { notify } = useToast();
  const { user, mutate: refreshMe } = useMe();
  const { locale, setLocale } = useI18n();
  const { data, mutate } = useApi<any>("/me/profile");
  const [p, setP] = useState<any>(null);
  const [supportText, setSupportText] = useState({ sen: "", ell: "" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (data) { setP(data); setSupportText({ sen: (data.planning_preferences?.sen_scaffolds || []).join("\n"), ell: (data.planning_preferences?.ell_scaffolds || []).join("\n") }); } }, [data]);
  if (user?.role === "admin") {
    // Admins have no teaching profile, plan or classes: only how the app looks for them.
    return (
      <div className="space-y-6">
        <PageHeader title="Settings" subtitle={`Signed in as ${user.email} (${user.admin_role_label || "staff"})`} />
        <div className="grid gap-6 lg:grid-cols-2">
          <SecurityCard />
          <div className="space-y-6"><Appearance /><NotificationPrefsCard /><InstallAppCard /><PushNotificationsCard /></div>
        </div>
      </div>
    );
  }
  if (!p) return <Skeleton className="h-96" />;

  const save = async () => {
    setBusy(true);
    try {
      await api("/me/profile", { method: "PUT", body: { ...p, planning_preferences: { ...(p.planning_preferences || {}), sen_scaffolds: supportText.sen.split("\n").map(line => line.trim()).filter(Boolean).slice(0, 12), ell_scaffolds: supportText.ell.split("\n").map(line => line.trim()).filter(Boolean).slice(0, 12) } } });
      notify({ tone: "success", title: "Settings saved" });
      mutate();
      refreshMe();
    } catch (e) {
      notify({ tone: "error", title: "Couldn't save", body: errorMessage(e) });
    } finally {
      setBusy(false);
    }
  };
  const exportData = async () => {
    try {
      const data = await api("/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = "clastio-account-summary.json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      notify({ tone: "error", title: "Couldn't export account summary", body: errorMessage(e) });
    }
  };
  const mp = p.metadata_policy || {};

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" actions={<Button onClick={save} loading={busy}>Save changes</Button>} />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Profile & school" />
          <div className="grid gap-4 p-5 sm:grid-cols-2">
            <Field label="Name"><Input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} /></Field>
            <Field label="School"><Input value={p.school_name || ""} onChange={(e) => setP({ ...p, school_name: e.target.value })} /></Field>
            <Field label="Curriculum"><Select value={p.curriculum} onChange={(e) => setP({ ...p, curriculum: e.target.value })}>{CURRICULA.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}</Select></Field>
            <Field label="Time zone"><Select value={p.timezone} onChange={(e) => setP({ ...p, timezone: e.target.value })}>{["Asia/Dubai", "Asia/Kolkata", "Asia/Riyadh", "Asia/Qatar", "Europe/London", "UTC"].map((z) => <option key={z}>{z}</option>)}</Select></Field>
            <Field label="Lesson length"><Select value={p.class_duration_minutes} onChange={(e) => setP({ ...p, class_duration_minutes: Number(e.target.value) })}>{[30, 35, 40, 45, 50, 55, 60, 90].map((m) => <option key={m} value={m}>{m} min</option>)}</Select></Field>
            <Field label="App language">
              <Select value={locale} onChange={(e) => setLocale(e.target.value)}><option value="en">English</option><option value="ar">العربية</option></Select>
            </Field>
            <Field label="Subjects" className="sm:col-span-2"><Chips multiple options={SUBJECTS.map((s) => ({ value: s, label: s }))} value={p.subjects} onChange={(v) => setP({ ...p, subjects: v })} /></Field>
            <Field label="Grades" className="sm:col-span-2"><Chips multiple options={GRADES.map((g) => ({ value: g, label: g }))} value={p.grades} onChange={(v) => setP({ ...p, grades: v })} /></Field>
            <Field label="Working days" className="sm:col-span-2">
              <Chips multiple options={DAYS.map((d, i) => ({ value: String(i), label: d.slice(0, 3) }))} value={p.working_days.map(String)} onChange={(v: string[]) => setP({ ...p, working_days: v.map(Number).sort() })} />
            </Field>
            <Field label="Teaching style" className="sm:col-span-2"><Textarea value={p.teaching_style || ""} onChange={(e) => setP({ ...p, teaching_style: e.target.value })} /></Field>
          </div>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader title="Lesson planning defaults" subtitle="Used by lesson planners, demos and teacher copilot. Each draft stays editable for your class." />
            <div className="space-y-4 p-5">
              <Field label="School planning framework" hint="Choose the framework used by your school; generated plans do not establish regulatory approval."><Select value={p.regulatory_authority || "not_specified"} onChange={event => setP({ ...p, regulatory_authority: event.target.value })}><option value="not_specified">No school framework</option><option value="khda">Dubai · KHDA</option><option value="adek">Abu Dhabi · ADEK</option><option value="moe">UAE · MoE</option><option value="other">Other framework</option></Select></Field>
              <Field label="Education stages"><Chips multiple options={EDUCATION_STAGES.map(stage => ({ value: stage.value, label: stage.label }))} value={p.education_stages || []} onChange={(value: string[]) => setP({ ...p, education_stages: value })} /></Field>
              <Field label="Class support needs" hint="Describe aggregate learning barriers and language support without student names or individual diagnoses."><Textarea maxLength={2000} value={p.planning_preferences?.inclusion_notes || ""} onChange={event => setP({ ...p, planning_preferences: { ...(p.planning_preferences || {}), inclusion_notes: event.target.value } })} placeholder="Some learners need shorter reading sections and labelled diagrams; use ELL sentence frames." /></Field>
              <Field label="Preferred SEN scaffolds" hint="One strategy per line, up to 12."><Textarea maxLength={6000} value={supportText.sen} onChange={event => setSupportText(previous => ({ ...previous, sen: event.target.value }))} placeholder="Chunk instructions into short steps" /></Field>
              <Field label="Preferred ELL scaffolds" hint="One strategy per line, up to 12."><Textarea maxLength={6000} value={supportText.ell} onChange={event => setSupportText(previous => ({ ...previous, ell: event.target.value }))} placeholder="Pre-teach academic vocabulary" /></Field>
            </div>
          </Card>
          <SecurityCard />
          <NotificationPrefsCard />
          <InstallAppCard />
          <PushNotificationsCard />
          <ConsentsCard />
          <Appearance />
          <Card>
            <CardHeader title="Presentation files" subtitle="Teacher attribution, page numbers and file properties" />
            <div className="divide-y divide-line px-5">
              <Toggle checked={mp.include_author !== false} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, include_author: v } })} label="Put my name as the author" />
              <Toggle checked={!!mp.teacher_footer_enabled} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, teacher_footer_enabled: v } })} label="Show my name at the bottom right" description="An editable teacher-name section on every slide. Off by default." />
              {mp.teacher_footer_enabled && <div className="py-3"><Field label="Teacher name on slides" hint="Leave blank to use your profile name."><Input maxLength={80} value={mp.teacher_footer_text || ""} placeholder={p.name} onChange={(e) => setP({ ...p, metadata_policy: { ...mp, teacher_footer_text: e.target.value } })} /></Field></div>}
              <Toggle checked={!!mp.page_numbers_enabled} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, page_numbers_enabled: v } })} label="Show PPT page numbers" description="Adds slide number / total at the bottom left. Applies to PPT and PDF when rebuilt." />
              <Toggle checked={!!mp.watermark_enabled} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, watermark_enabled: v } })} label="Add my teacher watermark" description="Shown on every slide in newly generated or rebuilt PPT and PDF files." />
              {mp.watermark_enabled && <div className="space-y-3 py-3"><Field label="Watermark text" hint="Leave blank to use your name."><Input maxLength={120} value={mp.watermark_text || ""} onChange={(e) => setP({ ...p, metadata_policy: { ...mp, watermark_text: e.target.value } })} placeholder={p.name} /></Field><Field label="Watermark position"><Select value={mp.watermark_position || "footer"} onChange={(e) => setP({ ...p, metadata_policy: { ...mp, watermark_position: e.target.value } })}><option value="footer">Bottom right</option><option value="diagonal">Faint diagonal</option></Select></Field></div>}
              <Toggle checked={!!mp.ai_disclosure} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, ai_disclosure: v } })} label="Add an AI-assistance note to file properties"
                description="Some schools ask for this. Off by default; nothing is ever added to your slides." />
            </div>
            <p className="px-5 pb-5 pt-2 text-xs text-muted">Your watermark is optional and remains editable in PowerPoint. Save changes, then rebuild an existing lesson to apply it.</p>
          </Card>
          <Card>
            <CardHeader title="Your data" subtitle="Download an account summary or review an account deletion request. Contact support for a wider data request." />
            <div className="flex flex-wrap gap-2 p-5">
              <Button variant="outline" onClick={exportData}><Download className="h-4 w-4" /> Export account summary</Button>
              <Button variant="danger" href="/delete-account"><Trash className="h-4 w-4" /> Request account deletion</Button>
              <Button variant="outline" href="/contact?topic=privacy">Data request help</Button>
            </div>
            <p className="px-5 pb-5 text-xs text-muted">The JSON summary does not include every uploaded or generated file. Download presentations and documents from their workspace pages before closing access.</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
