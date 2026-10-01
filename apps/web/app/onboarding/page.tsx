"use client";

import { ArrowLeft, ArrowRight, Check, Plus, Sparkles, Trash } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ActivityButton } from "@/components/activity-center";
import { Logo } from "@/components/brand";
import { useToast } from "@/components/toast";
import { Alert, Button, Card, Chips, Field, Input, Select, Textarea, Toggle } from "@/components/ui";
import { UploadDropzone } from "@/components/upload";
import { api } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { CURRICULA, DAYS, GRADES, SUBJECTS, cn } from "@/lib/utils";

const STEPS = ["About you", "Your slides", "How you teach", "Your classes", "Ready"];

export default function Onboarding() {
  const router = useRouter();
  const { notify } = useToast();
  const { user, error, mutate: refreshMe } = useMe();
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [uploadAccepted, setUploadAccepted] = useState(false);
  const [basics, setBasics] = useState({
    name: "", country: "AE", region: "Dubai", school_name: "", curriculum: "british", subjects: ["Science"],
    grades: ["8"], teaching_languages: ["en"], class_duration_minutes: 45, working_days: [0, 1, 2, 3, 4], teaching_style: "",
  });
  const [prefs, setPrefs] = useState({
    language_level: "simple English", explanation_depth: "balanced", slide_density: "light", recap_first: true,
    homework_last: true, quiz_length: 5, preferred_activities: ["think-pair-share", "group work"], real_world_examples: true,
    local_context: true, bilingual_vocabulary: false,
  });
  const [classes, setClasses] = useState([{ name: "8A", grade: "8", subject: "Science" }]);

  useEffect(() => {
    if (error) router.replace("/login?next=/onboarding");
    if (user) setBasics((b) => ({ ...b, name: b.name || user.name }));
  }, [user, error, router]);

  const saveBasics = async () => {
    setSaving(true);
    try {
      await api("/me/profile", { method: "PUT", body: basics });
      setStep(1);
    } catch (e: any) {
      notify({ tone: "error", title: "Couldn't save", body: e.message });
    } finally {
      setSaving(false);
    }
  };
  const savePrefs = async () => {
    setSaving(true);
    try {
      await api("/me/profile", { method: "PUT", body: { preferences: prefs } });
      setStep(3);
    } catch (e: any) {
      notify({ tone: "error", title: "Couldn't save preferences", body: e.message });
    } finally {
      setSaving(false);
    }
  };
  const saveClasses = async () => {
    setSaving(true);
    try {
      for (const c of classes.filter((c) => c.name.trim())) {
        await api("/classes", { body: { ...c, curriculum: basics.curriculum } });
      }
      await api("/me/onboarding/complete", { method: "POST" });
      await refreshMe(); // the app shell guards on onboarding_completed - refresh the cached user first
      setStep(4);
    } catch (e: any) {
      notify({ tone: "error", title: "Couldn't save classes", body: e.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4">
          <Logo href="/" />
          <div className="flex items-center gap-3"><ActivityButton /><span className="text-sm text-muted">Step {step + 1} of {STEPS.length}</span></div>
        </div>
      </header>
      <div className="mx-auto max-w-3xl px-4 py-8">
        <ol className="mb-8 flex gap-2">
          {STEPS.map((s, i) => (
            <li key={s} className="flex-1">
              <div className={cn("h-1.5 rounded-full", i <= step ? "bg-brand-600" : "bg-line")} />
              <div className={cn("mt-2 hidden text-xs sm:block", i === step ? "font-medium text-ink" : "text-muted")}>{s}</div>
            </li>
          ))}
        </ol>

        {step === 0 && (
          <Card className="p-6 sm:p-8">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Welcome to PPT Genie 👋</h1>
            <p className="mt-1 text-muted">A few details so every lesson fits your classroom.</p>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <Field label="Your name"><Input value={basics.name} onChange={(e) => setBasics({ ...basics, name: e.target.value })} /></Field>
              <Field label="School (optional)"><Input value={basics.school_name} onChange={(e) => setBasics({ ...basics, school_name: e.target.value })} placeholder="e.g. Al Noor Academy" /></Field>
              <Field label="Country">
                <Select value={basics.country} onChange={(e) => setBasics({ ...basics, country: e.target.value })}>
                  <option value="AE">United Arab Emirates</option><option value="IN">India</option><option value="SA">Saudi Arabia</option>
                  <option value="QA">Qatar</option><option value="GB">United Kingdom</option><option value="US">United States</option><option value="OT">Other</option>
                </Select>
              </Field>
              <Field label="Emirate / state"><Input value={basics.region} onChange={(e) => setBasics({ ...basics, region: e.target.value })} /></Field>
              <Field label="Curriculum" className="sm:col-span-2">
                <Chips options={CURRICULA.map((c) => ({ value: c.code, label: c.label }))} value={basics.curriculum} onChange={(v) => setBasics({ ...basics, curriculum: v })} />
              </Field>
              <Field label="Subjects you teach" className="sm:col-span-2">
                <Chips multiple options={SUBJECTS.slice(0, 13).map((s) => ({ value: s, label: s }))} value={basics.subjects} onChange={(v) => setBasics({ ...basics, subjects: v })} />
              </Field>
              <Field label="Grades" className="sm:col-span-2">
                <Chips multiple options={GRADES.map((g) => ({ value: g, label: g === "KG" ? "KG" : `Grade ${g}` }))} value={basics.grades} onChange={(v) => setBasics({ ...basics, grades: v })} />
              </Field>
              <Field label="Teaching language">
                <Select value={basics.teaching_languages[0]} onChange={(e) => setBasics({ ...basics, teaching_languages: [e.target.value] })}>
                  <option value="en">English</option><option value="ar">Arabic</option><option value="hi">Hindi</option>
                </Select>
              </Field>
              <Field label="Typical lesson length">
                <Select value={basics.class_duration_minutes} onChange={(e) => setBasics({ ...basics, class_duration_minutes: Number(e.target.value) })}>
                  {[30, 35, 40, 45, 50, 55, 60, 90].map((m) => <option key={m} value={m}>{m} minutes</option>)}
                </Select>
              </Field>
              <Field label="Working days" className="sm:col-span-2">
                <Chips multiple options={DAYS.map((d, i) => ({ value: String(i), label: d.slice(0, 3) }))} value={basics.working_days.map(String)}
                  onChange={(v: string[]) => setBasics({ ...basics, working_days: v.map(Number).sort() })} />
              </Field>
              <Field label="Describe your teaching style (optional)" className="sm:col-span-2" hint="e.g. lots of questioning, visual, real-world UAE examples, short bullet points">
                <Textarea value={basics.teaching_style} onChange={(e) => setBasics({ ...basics, teaching_style: e.target.value })} />
              </Field>
            </div>
            <div className="mt-6 flex justify-end">
              <Button onClick={saveBasics} loading={saving}>Continue <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Button>
            </div>
          </Card>
        )}

        {step === 1 && (
          <Card className="p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-ink">Upload a presentation you like</h2>
            <p className="mt-1 text-muted">We read its colours, fonts, layouts, header bands and logo, so new lessons look like yours. This is optional; you can use a built-in style for now.</p>
            <div className="mt-6">
              <UploadDropzone onQueued={() => setUploadAccepted(true)} onReady={({ templateId }) => { setTemplateId(templateId || null); notify({ tone: "success", title: "Your style is ready", body: "New lessons will use your design." }); }} />
            </div>
            {templateId && <Alert tone="success" className="mt-4" title="Template created">It's set as your default. You can fine-tune it later in My designs.</Alert>}
            {uploadAccepted && !templateId && <Alert tone="brand" className="mt-4" title="Carry on with setup">Your design is being prepared in the background. It will appear in My designs when it’s ready.</Alert>}
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(0)}><ArrowLeft className="h-4 w-4 rtl:rotate-180" /> Back</Button>
              <Button onClick={() => setStep(2)}>{templateId || uploadAccepted ? "Continue" : "Skip for now"} <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Button>
            </div>
          </Card>
        )}

        {step === 2 && (
          <Card className="p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-ink">How do you like to teach?</h2>
            <p className="mt-1 text-muted">These become your teacher memory and apply to every lesson. You can change them any time.</p>
            <div className="mt-6 space-y-5">
              <Field label="Language level"><Chips options={["simple English", "standard", "academic"].map((v) => ({ value: v, label: v }))} value={prefs.language_level} onChange={(v) => setPrefs({ ...prefs, language_level: v })} /></Field>
              <Field label="Explanation depth"><Chips options={["brief", "balanced", "detailed"].map((v) => ({ value: v, label: v }))} value={prefs.explanation_depth} onChange={(v) => setPrefs({ ...prefs, explanation_depth: v })} /></Field>
              <Field label="Text on slides"><Chips options={[{ value: "light", label: "Light — short bullets" }, { value: "standard", label: "Standard" }, { value: "detailed", label: "Detailed" }]} value={prefs.slide_density} onChange={(v) => setPrefs({ ...prefs, slide_density: v })} /></Field>
              <Field label="Quiz length"><Chips options={[5, 10, 20].map((v) => ({ value: String(v), label: `${v} questions` }))} value={String(prefs.quiz_length)} onChange={(v) => setPrefs({ ...prefs, quiz_length: Number(v) })} /></Field>
              <Field label="Favourite activities">
                <Chips multiple options={["think-pair-share", "group work", "experiments", "games", "mini whiteboards", "debates", "card sorts"].map((v) => ({ value: v, label: v }))}
                  value={prefs.preferred_activities} onChange={(v) => setPrefs({ ...prefs, preferred_activities: v })} />
              </Field>
              <div className="divide-y divide-line rounded-xl border border-line px-3">
                <Toggle checked={prefs.recap_first} onChange={(v) => setPrefs({ ...prefs, recap_first: v })} label="Start each lesson with a recap" />
                <Toggle checked={prefs.homework_last} onChange={(v) => setPrefs({ ...prefs, homework_last: v })} label="End with homework" />
                <Toggle checked={prefs.real_world_examples} onChange={(v) => setPrefs({ ...prefs, real_world_examples: v })} label="Real-world examples" />
                <Toggle checked={prefs.local_context} onChange={(v) => setPrefs({ ...prefs, local_context: v })} label="Local examples (UAE / India)" />
                <Toggle checked={prefs.bilingual_vocabulary} onChange={(v) => setPrefs({ ...prefs, bilingual_vocabulary: v })} label="Bilingual vocabulary slides" description="Adds Arabic translations to key terms" />
              </div>
            </div>
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(1)}><ArrowLeft className="h-4 w-4 rtl:rotate-180" /> Back</Button>
              <Button onClick={savePrefs} loading={saving}>Continue <ArrowRight className="h-4 w-4 rtl:rotate-180" /></Button>
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card className="p-6 sm:p-8">
            <h2 className="text-xl font-semibold text-ink">Add your classes</h2>
            <p className="mt-1 text-muted">Each section gets its own progress, pace and history. You can add your timetable afterwards in Calendar.</p>
            <div className="mt-6 space-y-3">
              {classes.map((c, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_1.4fr_auto] items-end gap-2">
                  <Field label={i === 0 ? "Class" : ""}><Input value={c.name} onChange={(e) => setClasses(classes.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} placeholder="8A" /></Field>
                  <Field label={i === 0 ? "Grade" : ""}>
                    <Select value={c.grade} onChange={(e) => setClasses(classes.map((x, j) => j === i ? { ...x, grade: e.target.value } : x))}>
                      {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
                    </Select>
                  </Field>
                  <Field label={i === 0 ? "Subject" : ""}>
                    <Select value={c.subject} onChange={(e) => setClasses(classes.map((x, j) => j === i ? { ...x, subject: e.target.value } : x))}>
                      {SUBJECTS.map((s) => <option key={s}>{s}</option>)}
                    </Select>
                  </Field>
                  <Button variant="ghost" size="icon" onClick={() => setClasses(classes.filter((_, j) => j !== i))} aria-label="Remove class"><Trash className="h-4 w-4" /></Button>
                </div>
              ))}
              <Button variant="outline" size="sm" onClick={() => setClasses([...classes, { name: "", grade: basics.grades[0] || "8", subject: basics.subjects[0] || "Science" }])}>
                <Plus className="h-4 w-4" /> Add class
              </Button>
            </div>
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(2)}><ArrowLeft className="h-4 w-4 rtl:rotate-180" /> Back</Button>
              <Button onClick={saveClasses} loading={saving}>Finish setup <Check className="h-4 w-4" /></Button>
            </div>
          </Card>
        )}

        {step === 4 && (
          <Card className="p-8 text-center">
            <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600"><Sparkles className="h-7 w-7" /></div>
            <h2 className="mt-4 text-2xl font-semibold tracking-tight text-ink">PPT Genie is ready</h2>
            <p className="mx-auto mt-2 max-w-md text-muted">Create your first set of lessons. Try something you're teaching next week, like “Photosynthesis · 5 lessons · 10 slides”.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button size="lg" href="/projects/new">Create my first lessons</Button>
              <Button size="lg" variant="outline" href="/dashboard">Go to dashboard</Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
