"use client";

import { Check, Download, Trash } from "lucide-react";
import { useEffect, useState } from "react";
import { errorMessage, useToast } from "@/components/toast";
import { Alert, Button, Card, CardHeader, Chips, Field, Input, Modal, PageHeader, Select, Skeleton, Textarea, Toggle } from "@/components/ui";
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
  const { mutate: refreshMe } = useMe();
  const { locale, setLocale } = useI18n();
  const { data, mutate } = useApi<any>("/me/profile");
  const [p, setP] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  useEffect(() => { if (data) setP(data); }, [data]);
  if (!p) return <Skeleton className="h-96" />;

  const save = async () => {
    setBusy(true);
    try {
      await api("/me/profile", { method: "PUT", body: p });
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
    const data = await api("/me/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "ppt-genie-export.json";
    a.click();
  };
  const deleteAccount = async () => {
    try {
      await api("/me/delete", { body: { confirm_email: confirmEmail } });
      window.location.href = "/";
    } catch (e) {
      notify({ tone: "error", title: "Couldn't delete", body: errorMessage(e) });
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
          <Appearance />
          <Card>
            <CardHeader title="Presentation files" subtitle="Control the metadata in files you download" />
            <div className="divide-y divide-line px-5">
              <Toggle checked={mp.include_author !== false} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, include_author: v } })} label="Put my name as the author" />
              <Toggle checked={!!mp.ai_disclosure} onChange={(v) => setP({ ...p, metadata_policy: { ...mp, ai_disclosure: v } })} label="Add an AI-assistance note to file properties"
                description="Some schools ask for this. Off by default; nothing is ever added to your slides." />
            </div>
            <p className="px-5 pb-5 pt-2 text-xs text-muted">We never add watermarks or hidden product text to your files.</p>
          </Card>
          <Card>
            <CardHeader title="Your data" subtitle="UAE PDPL and India DPDP: export or delete everything we store about you." />
            <div className="flex flex-wrap gap-2 p-5">
              <Button variant="outline" onClick={exportData}><Download className="h-4 w-4" /> Export my data</Button>
              <Button variant="danger" onClick={() => setDeleting(true)}><Trash className="h-4 w-4" /> Delete account</Button>
            </div>
          </Card>
        </div>
      </div>
      <Modal open={deleting} onClose={() => setDeleting(false)} title="Delete your account"
        footer={<><Button variant="ghost" onClick={() => setDeleting(false)}>Cancel</Button><Button variant="danger" onClick={deleteAccount} disabled={confirmEmail.toLowerCase() !== p.email.toLowerCase()}>Delete permanently</Button></>}>
        <Alert tone="danger">This permanently deletes your lessons, templates, uploads and memory. This can't be undone.</Alert>
        <Field label={`Type ${p.email} to confirm`} className="mt-4"><Input value={confirmEmail} onChange={(e) => setConfirmEmail(e.target.value)} /></Field>
      </Modal>
    </div>
  );
}
