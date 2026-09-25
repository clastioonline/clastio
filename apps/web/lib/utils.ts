import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const CURRICULA = [
  { code: "british", label: "British (UK NC / IGCSE)" },
  { code: "cbse", label: "Indian — CBSE" },
  { code: "icse", label: "Indian — ICSE" },
  { code: "american", label: "American (Common Core / NGSS)" },
  { code: "ib", label: "IB (PYP / MYP / DP)" },
  { code: "moe", label: "UAE Ministry of Education" },
  { code: "uae_ai", label: "UAE AI Curriculum" },
  { code: "other", label: "Other" },
];

export const SUBJECTS = [
  "Science", "Biology", "Chemistry", "Physics", "Mathematics", "English", "Arabic", "Islamic Education",
  "Social Studies & Moral Education", "Geography", "History", "Computing", "Artificial Intelligence", "Business",
  "Economics", "Art", "Music", "Physical Education",
];

export const GRADES = ["KG", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"];

export const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const LAYOUT_LABELS: Record<string, string> = {
  cover: "Cover", section: "Section", objectives: "Objectives", concept: "Concept", image_text: "Image + text",
  two_column: "Two columns", comparison: "Comparison", process: "Process", cycle: "Cycle", timeline: "Timeline",
  table: "Table", key_vocabulary: "Vocabulary", quiz: "Quiz", discussion: "Discussion", activity: "Activity",
  worked_example: "Worked example", summary: "Summary", exit_ticket: "Exit ticket", homework: "Homework",
};

export const STATUS_TONE: Record<string, "neutral" | "brand" | "success" | "warn" | "danger"> = {
  planned: "neutral", planning: "brand", generating: "brand", generated: "success", ready: "success",
  taught: "success", reflected: "success", failed: "danger", partial: "warn", skipped: "warn", queued: "neutral",
  processing: "brand", draft: "neutral",
};
