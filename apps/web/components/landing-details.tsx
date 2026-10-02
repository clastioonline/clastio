"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, BookOpen, Check, Clock3, FileDown, Layers, ShieldCheck } from "lucide-react";

const examples = [
  { subject: "Science", grade: "8", topic: "Photosynthesis", title: "How do plants turn light into growth?", objective: "Explain how light, water and carbon dioxide help plants produce glucose.", activity: "Compare a plant kept in light with one kept in the dark. Predict the difference and explain your reasoning.", check: "Why does a plant still need water when it gets plenty of sunlight?", sequence: ["What plants need", "Inside the leaf", "Testing our explanations"] },
  { subject: "Mathematics", grade: "5", topic: "Equivalent fractions", title: "Different fractions, the same amount", objective: "Use visual models to recognise and create equivalent fractions.", activity: "Fold two paper strips into halves and quarters. Find different ways to show the same shaded amount.", check: "Is 3/6 equivalent to 1/2? Show how you know.", sequence: ["Build fraction models", "Find equivalent fractions", "Explain and apply the pattern"] },
  { subject: "English", grade: "7", topic: "Persuasive writing", title: "Make a claim. Give a reason.", objective: "Support a clear opinion with relevant reasons and evidence.", activity: "Choose an improvement for your school. Work with a partner to write a claim and two supporting reasons.", check: "Which sentence gives evidence, and which only repeats the opinion?", sequence: ["Recognise a strong argument", "Build a paragraph", "Revise for a reader"] },
];
const faqs = [
  ["Do I need an existing presentation?", "No. You can begin with a built-in design. Upload a PowerPoint when you want to reuse your own slide master, layouts and visual style. PDF designs are reconstructed, so they may not match exactly."],
  ["Can I edit what is generated?", "Yes. Review and revise slides in the lesson editor, then download an editable PowerPoint. Worksheets and quizzes include downloadable student and answer-key files when generation finishes."],
  ["Do I have to keep this page open?", "Only while a file is transferring. Once a task is accepted, it runs on the server. You can visit another page or close your browser, then return to Activity for results and in-app notifications."],
  ["How does curriculum planning work?", "Choose a subject, grade and available curriculum outcomes to guide the plan. You can add your own instructions and authorised reference material. Check generated content against your school’s requirements before teaching."],
  ["Will the generated lesson always be accurate?", "AI can make mistakes. Review facts, examples, answers and suitability for your class before using a lesson. Layout checks help identify presentation issues; they do not replace a teacher’s review."],
  ["How are plans and limits explained?", "The pricing page shows the currently available plans. Inside your account, Plan & billing shows usage and allowances. Features that use external services depend on the plan and the integrations enabled for your deployment."],
  ["What should I upload?", "Upload teaching materials you have permission to use. Avoid unnecessary student personal information. Your original uploaded presentation is preserved; generated lessons are separate files. Read the Privacy Policy for the handling of account and uploaded data."],
];
const actionClass = "focus-ring inline-flex items-center justify-center gap-2 rounded-full bg-[#1b7446] px-5 py-3 text-sm font-semibold text-white hover:bg-[#145b36]";

export function LandingDetails() {
  const [selected, setSelected] = useState(0);
  const example = examples[selected];
  return <>
    <section id="example" className="mx-auto max-w-6xl scroll-mt-8 px-4 pb-20 sm:px-6">
      <div className="mb-8 max-w-2xl"><p className="text-sm font-semibold text-[#1b7446]">Explore a lesson</p><h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">See what your starting point could look like</h2><p className="mt-3 text-[var(--l-muted)]">Choose a subject to explore an illustrative outline. Your generated lessons use your topic, class settings and selected design.</p></div>
      <div className="mb-5 flex flex-wrap gap-2" role="group" aria-label="Example subject">
        {examples.map((item, i) => <button key={item.subject} aria-pressed={selected === i} onClick={() => setSelected(i)} className={`focus-ring rounded-full border px-5 py-3 text-sm font-medium ${selected === i ? 'border-[#1b7446] bg-[#1b7446] text-white' : 'border-[var(--l-line)] bg-[var(--l-card)]'}`}>{item.subject}</button>)}
      </div>
      <div className="grid gap-6 rounded-[2rem] border border-[var(--l-line)] bg-[var(--l-card)] p-5 sm:p-8 lg:grid-cols-[1.4fr_1fr]">
        <div aria-live="polite" className="min-w-0"><span className="text-xs font-semibold uppercase tracking-wider text-[var(--l-muted)]">Illustrative example · Grade {example.grade}</span><h3 className="mt-3 text-2xl font-semibold">{example.title}</h3><dl className="mt-5 space-y-4">{[['Learning objective', example.objective], ['Classroom activity', example.activity], ['Check for understanding', example.check]].map(([label, text]) => <div key={label}><dt className="text-sm font-semibold text-[#1b7446]">{label}</dt><dd className="mt-1 text-sm leading-relaxed text-[var(--l-muted)]">{text}</dd></div>)}</dl></div>
        <div className="min-w-0 rounded-2xl bg-[var(--l-hero)] p-5"><h3 className="font-semibold">A connected lesson sequence</h3><ol className="mt-4 space-y-3">{example.sequence.map((title, i) => <li key={title} className="flex items-start gap-3 text-sm"><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-[#1b7446] text-xs text-white">{i + 1}</span>{title}</li>)}</ol><p className="mt-5 text-sm text-[var(--l-muted)]">Add slides, teacher notes and an assessment as you prepare your class.</p><Link href="/signup" className={`${actionClass} mt-5`}>Create your own lesson <ArrowRight className="h-4 w-4" /></Link></div>
      </div>
    </section>
    <section className="mx-auto max-w-6xl px-4 pb-20 sm:px-6" aria-labelledby="outputs-title">
      <h2 id="outputs-title" className="text-3xl font-bold tracking-tight sm:text-4xl">From the first idea to classroom materials</h2>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[
        { icon: Layers, title: 'Your design library', text: 'Reuse a PowerPoint design, explore built-in styles, search saved designs and choose a default for new lessons.' },
        { icon: BookOpen, title: 'Connected planning', text: 'Set your topic, class duration and learning outcomes. Review a sequence before generating the teaching materials.' },
        { icon: FileDown, title: 'Editable resources', text: 'Download PowerPoint slides and prepare worksheets or quizzes with student copies and answer keys.' },
        { icon: Clock3, title: 'Work without waiting', text: 'Submit a task and carry on. Activity keeps progress, results and completion notifications together.' },
        { icon: Check, title: 'Review and refine', text: 'Adjust slides, add instructions and record a reflection after class to inform future planning.' },
        { icon: ShieldCheck, title: 'Teacher control', text: 'Choose what to upload, review AI suggestions and manage your account, sessions and notification preferences.' },
      ].map(item => <article key={item.title} className="rounded-2xl border border-[var(--l-line)] bg-[var(--l-card)] p-6"><item.icon className="h-6 w-6 text-[#1b7446]" /><h3 className="mt-4 text-lg font-semibold">{item.title}</h3><p className="mt-2 text-sm leading-relaxed text-[var(--l-muted)]">{item.text}</p></article>)}</div>
    </section>
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-8 px-4 pb-20 sm:px-6"><h2 className="mb-7 text-3xl font-bold tracking-tight sm:text-4xl">Before your first lesson</h2><div className="space-y-3">{faqs.map(([question, answer]) => <details key={question} className="group rounded-2xl border border-[var(--l-line)] bg-[var(--l-card)] p-5"><summary className="focus-ring cursor-pointer rounded font-semibold">{question}</summary><p className="mt-3 text-sm leading-relaxed text-[var(--l-muted)]">{answer}</p></details>)}</div><div className="mt-8 flex flex-wrap gap-3"><Link href="/signup" className={actionClass}>Create your teaching workspace <ArrowRight className="h-4 w-4" /></Link><Link href="/pricing" className="focus-ring rounded-full border border-[var(--l-line)] px-5 py-3 text-sm font-semibold">Compare plans</Link></div></section>
  </>;
}
