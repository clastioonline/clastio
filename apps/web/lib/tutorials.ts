import {
  CalendarDays,
  ClipboardList,
  FolderKanban,
  GraduationCap,
  ImagePlay,
  MessageCircle,
  Palette,
  PencilLine,
  type LucideIcon,
} from "lucide-react";

export type Tutorial = {
  id: string;
  /** Key in the dashboard checklist that marks this step done, if it is a setup step. */
  check?: "template" | "class" | "timetable" | "course" | "document" | "whatsapp";
  title: string;
  summary: string;
  minutes: number;
  icon: LucideIcon;
  color: string;
  href: string;
  cta: string;
  steps: string[];
  tip?: string;
};

export const TUTORIALS: Tutorial[] = [
  {
    id: "design", check: "template", title: "Teach Clastio your slide design", minutes: 2, icon: Palette, color: "#fbcab8",
    summary: "Upload a deck you've taught with so every new lesson looks like yours.",
    href: "/templates", cta: "Upload a deck",
    steps: [
      "Open My designs and drop in a PowerPoint (.pptx) you like. A PDF works too, but PowerPoint gives an exact match.",
      "Clastio reads the colours, fonts, slide master, logo, header bands and footer. Your original file is never changed.",
      "Check the preview. If it looks right, keep it as your default design.",
      "You can add more designs later, for example one per subject or school.",
    ],
    tip: "Choose a deck with a title slide and a few content slides so all your layouts are learned.",
  },
  {
    id: "classes", check: "class", title: "Add your classes", minutes: 2, icon: GraduationCap, color: "#93b4ff",
    summary: "Each class keeps its own pace, progress and curriculum coverage.",
    href: "/curriculum", cta: "Add a class",
    steps: [
      "Open Classes and choose Add class.",
      "Enter the section (for example 8A), grade, subject and a colour.",
      "Set the pace and ability mix, and the share of EAL learners, so lessons are pitched right.",
      "Coverage fills in automatically as you teach lessons for that class.",
    ],
  },
  {
    id: "timetable", check: "timetable", title: "Add your timetable", minutes: 3, icon: CalendarDays, color: "#fde047",
    summary: "So the dashboard knows your next class and what to prepare each day.",
    href: "/calendar?tab=timetable", cta: "Set up timetable",
    steps: [
      "Open Calendar and choose the Timetable tab.",
      "Add each period: day, start and end time, and the class. Or import a CSV exported from your school system.",
      "Holidays, short days and Ramadan timings in the School calendar tab adjust lesson length automatically.",
      "Use Prepare my week on the dashboard to build everything for the coming week at once.",
    ],
  },
  {
    id: "lessons", check: "course", title: "Create a unit of lessons", minutes: 3, icon: FolderKanban, color: "#7fd18f",
    summary: "One request, a connected sequence of editable PowerPoints in your design.",
    href: "/projects/new", cta: "Create lessons",
    steps: [
      "Choose New lessons and enter the topic, grade and subject, for example Photosynthesis, Grade 8, Science.",
      "Pick the number of lessons and slides per lesson. The planner builds a real progression, not copies.",
      "Review the plan (outcomes, big idea, lesson titles), then build the slides.",
      "Each lesson comes with speaker notes, activities, a quiz and an exit ticket, checked so nothing overflows.",
    ],
  },
  {
    id: "edit", title: "Edit slides in seconds", minutes: 2, icon: PencilLine, color: "#c4b5fd",
    summary: "Quick changes keep your design while you adjust the content.",
    href: "/projects", cta: "Open a lesson",
    steps: [
      "Open a lesson and pick a slide on the left.",
      "Use a quick change such as Make simpler, Add examples or Turn into activity, or describe your own change.",
      "Edit the title, text or speaker notes directly and choose Save & rebuild.",
      "Every change is saved as a version you can restore. Download the PowerPoint or PDF when you're ready.",
    ],
  },
  {
    id: "documents", check: "document", title: "Make worksheets and quizzes", minutes: 2, icon: ClipboardList, color: "#ffb86b",
    summary: "Printable documents with a separate answer key, matched to the lesson.",
    href: "/lessons", cta: "Create a worksheet",
    steps: [
      "Open a lesson, go to the Documents tab and choose Worksheet, Quiz, Homework or Test.",
      "Set the number of questions and difficulty. Support and extension versions are optional.",
      "Download Word or PDF. Quizzes also export to Kahoot and Moodle.",
    ],
  },
  {
    id: "whatsapp", check: "whatsapp", title: "Get your day on WhatsApp", minutes: 2, icon: MessageCircle, color: "#86efac",
    summary: "Your plan every school morning and a one-tap check-in after class.",
    href: "/whatsapp", cta: "Connect WhatsApp",
    steps: [
      "Open WhatsApp and enter your mobile number.",
      "Send the code shown to the Clastio number to confirm it's you.",
      "Choose when the morning plan and the after-class check-in arrive. Reply STOP at any time to pause.",
    ],
  },
  {
    id: "media", title: "Create images and videos", minutes: 2, icon: ImagePlay, color: "#f9a8d4",
    summary: "Illustrations and short clips for your slides, from the Media studio.",
    href: "/media", cta: "Open Media studio",
    steps: [
      "Open Media studio, choose Image or Video and describe what you need.",
      "Pick a style and shape. The cost in media credits is shown before you generate.",
      "Download the result. Everything made here is labelled as AI-generated.",
    ],
  },
];

export const SETUP_STEPS = TUTORIALS.filter((t) => t.check);
