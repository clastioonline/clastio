export type TeacherCourseProfile = {
  subjects?: string[];
  grades?: string[];
  education_stages?: string[];
};

export type TeacherCourseClass = {
  id: string;
  name: string;
  grade: string;
  subject: string;
  curriculum?: string | null;
};

export type TeacherCourseSelection = {
  grade: string;
  subject: string;
  class_section_id: string;
};

function uniqueValues(values: unknown[]): string[] {
  const seen = new Set<string>();
  return values.flatMap((value) => {
    const text = typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
    const key = text.toLowerCase();
    if (!text || seen.has(key)) return [];
    seen.add(key);
    return [text];
  });
}

function matchingValue(values: string[], value: string): string | undefined {
  return values.find((item) => item.toLowerCase() === value.trim().toLowerCase());
}

/** Teaching choices come from the teacher's profile, with saved classes for older profiles. */
export function teacherCourseOptions(profile: TeacherCourseProfile, savedClasses: TeacherCourseClass[]) {
  const selectedSubjects = uniqueValues(profile.subjects || []);
  const selectedGrades = uniqueValues(profile.grades || []);
  const subjects = selectedSubjects.length ? selectedSubjects : uniqueValues(savedClasses.map((item) => item.subject));
  const grades = selectedGrades.length ? selectedGrades : uniqueValues(savedClasses.map((item) => item.grade));
  const classes = savedClasses.flatMap((item) => {
    const subject = matchingValue(subjects, item.subject);
    const grade = matchingValue(grades, item.grade);
    return subject && grade ? [{ ...item, subject, grade }] : [];
  });
  return { subjects, grades, classes };
}

/** Keep imported briefs, URL values and class choices within the current teaching profile. */
export function normalizeTeacherCourseSelection(
  selection: TeacherCourseSelection,
  options: ReturnType<typeof teacherCourseOptions>,
): TeacherCourseSelection {
  const classroom = options.classes.find((item) => item.id === selection.class_section_id);
  if (classroom) return { class_section_id: classroom.id, subject: classroom.subject, grade: classroom.grade };
  return {
    class_section_id: "",
    subject: matchingValue(options.subjects, selection.subject) || options.subjects[0] || "",
    grade: matchingValue(options.grades, selection.grade) || options.grades[0] || "",
  };
}

export function teacherCourseSelectionValid(
  selection: TeacherCourseSelection,
  options: ReturnType<typeof teacherCourseOptions>,
): boolean {
  if (!options.subjects.includes(selection.subject) || !options.grades.includes(selection.grade)) return false;
  if (!selection.class_section_id) return true;
  return options.classes.some((item) => item.id === selection.class_section_id
    && item.subject === selection.subject && item.grade === selection.grade);
}

export function teacherEducationStage(grade: string): string | undefined {
  if (/university|undergraduate|postgraduate|college/i.test(grade)) return "university";
  if (/nursery|reception|kindergarten|early years|^kg\s*[12]?$|^fs\s*[12]$/i.test(grade.trim())) return "early_years";
  const year = Number(grade.trim().replace(/^(?:grade|year)\s*/i, ""));
  return year >= 1 && year <= 6 ? "primary" : year >= 7 && year <= 13 ? "secondary" : undefined;
}

export function teacherEducationStages(profile: TeacherCourseProfile, grades: string[]): string[] {
  const supported = ["early_years", "primary", "secondary", "university"];
  const selected = uniqueValues(profile.education_stages || []).filter((stage) => supported.includes(stage));
  return selected.length ? selected : uniqueValues(grades.map((grade) => teacherEducationStage(grade) || ""));
}

/** Editing onboarding subjects/grades must also update every pending classroom row. */
export function synchronizeOnboardingTeachingClasses<T extends { grade: string; subject: string }>(
  classes: T[], profile: TeacherCourseProfile,
): T[] {
  const options = teacherCourseOptions(profile, []);
  return classes.map((classroom) => {
    const selection = normalizeTeacherCourseSelection({ ...classroom, class_section_id: "" }, options);
    return classroom.grade === selection.grade && classroom.subject === selection.subject ? classroom
      : { ...classroom, grade: selection.grade, subject: selection.subject };
  });
}
