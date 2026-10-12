/** Search Console uses case-insensitive, partial RE2 matching by default.
 * Keep these expressions portable: no lookarounds, backreferences or inline flags.
 * These are overlapping intent filters, not evidence of volume or buying intent.
 */
export type SearchQueryPattern = {
  id: string;
  label: string;
  regex: string;
  page: string;
  examples: string[];
};

export const searchQueryPatterns: SearchQueryPattern[] = [
  { id: "brand", label: "Clastio brand", regex: "\\bclastio\\b|clastio\\.online", page: "/", examples: ["Clastio pricing", "clastio.online"] },
  { id: "uae", label: "UAE and local context", regex: "\\b(u[ .-]?a[ .-]?e|united arab emirates|dubai|abu[ -]?dhabi|sharjah|ajman|ras al khaimah|fujairah|umm al quwain)\\b", page: "/solutions/ai-ppt-maker-for-teachers-uae", examples: ["AI PowerPoint for teachers Dubai", "British curriculum lesson planner UAE", "slide creation in Abu-Dhabi", "lesson slides Abudhabi"] },
  { id: "abu-dhabi-slides", label: "Abu Dhabi presentation context", regex: "\\b(slides?|slide[ -]?decks?|presentations?|power[ -]?point|pptx?)\\b.*\\babu[ -]?dhabi\\b|\\babu[ -]?dhabi\\b.*\\b(slides?|slide[ -]?decks?|presentations?|power[ -]?point|pptx?)\\b", page: "/solutions/ai-ppt-maker-for-teachers-uae#abu-dhabi-lesson-slides", examples: ["slides creation in abu dhabi", "slide creation in abu dhabi", "Abu-Dhabi lesson slide maker", "editable PPTX Abudhabi"] },
  { id: "moe-context", label: "UAE MoE context (may be navigational)", regex: "\\b(moe[ -]?u[ .-]?a[ .-]?e|u[ .-]?a[ .-]?e[ -]?moe|u[ .-]?a[ .-]?e ministry of education|ministry of education (in )?(the )?(uae|united arab emirates)|uae national curriculum)\\b", page: "/solutions/ai-ppt-maker-for-teachers-uae#british-or-moe", examples: ["moe uae", "UAE MoE curriculum lesson", "Ministry of Education UAE", "MoE-U.A.E textbooks"] },
  { id: "presentation-creation", label: "Presentation creation (AI or teacher context not required)", regex: "\\b(slides?|slide[ -]?decks?|presentations?|pptx?|power[ -]?point)\\b.*\\b(creat(e|es|ed|ing|ion|ors?)|makers?|generators?|build|builders?|building)\\b|\\b(creat(e|es|ed|ing|ion|ors?)|makers?|generators?|build|builders?|building)\\b.*\\b(slides?|slide[ -]?decks?|presentations?|pptx?|power[ -]?point)\\b", page: "/solutions/ai-ppt-maker-for-teachers-uae", examples: ["slides creation in Abu Dhabi", "slide creation in Abu Dhabi", "create lesson slides", "PowerPoint presentation creator"] },
  { id: "british", label: "British curriculum", regex: "\\b(british curriculum|national curriculum|key stage [1-5]|ks[1-5]|gcse|igcse|a[ -]?levels?)\\b", page: "/solutions/british-curriculum-lesson-planning", examples: ["AI lesson planner British curriculum", "KS3 science lesson slides"] },
  { id: "gcse-igcse", label: "GCSE and IGCSE specifications", regex: "\\b(gcse|igcse|cambridge international|aqa|edexcel|pearson)\\b", page: "/solutions/gcse-igcse-lesson-presentations", examples: ["IGCSE physics lesson PowerPoint", "GCSE lesson slides from specification"] },
  { id: "ai-presentations", label: "AI lesson presentations", regex: "\\b(ai|artificial intelligence)\\b.*\\b(pptx?|power[ -]?point|presentations?|slides?)\\b|\\b(pptx?|power[ -]?point|presentations?|slides?)\\b.*\\b(ai|artificial intelligence)\\b", page: "/solutions/ai-ppt-maker-for-teachers-uae", examples: ["AI PowerPoint generator for teachers", "editable teaching presentations AI"] },
  { id: "teacher-context", label: "Teachers and classroom context", regex: "\\b(teachers?|teaching|classrooms?|educators?|schools?|lessons?)\\b", page: "/solutions", examples: ["presentation maker for teachers", "classroom quiz generator"] },
  { id: "editable-exports", label: "Editable PPT and export concerns", regex: "\\b(editable|editability|pptx|powerpoint export|download powerpoint|native powerpoint)\\b", page: "/solutions/how-to-choose-ai-presentation-maker-for-teachers", examples: ["editable AI PPT maker for teachers", "lesson slides PPTX download"] },
  { id: "source-conversion", label: "Textbook, PDF and notes to slides", regex: "\\b(textbooks?|pdf|notes?|documents?)\\b.*\\b(pptx?|power[ -]?point|presentations?|slides?)\\b|\\b(pptx?|power[ -]?point|presentations?|slides?)\\b.*\\b(textbooks?|pdf|notes?|documents?)\\b", page: "/solutions/turn-teaching-notes-into-powerpoint", examples: ["textbook PDF to lesson slides", "PowerPoint from teaching notes"] },
  { id: "school-design", label: "School presentation design", regex: "\\b(school|own|custom|existing)\\b.*\\b(templates?|designs?|branding)\\b|\\b(templates?|designs?)\\b.*\\b(school|own|custom|existing)\\b", page: "/solutions/reuse-school-powerpoint-design", examples: ["AI PowerPoint using school template", "reuse existing teaching presentation design"] },
  { id: "lesson-planning", label: "Lesson planning", regex: "\\blesson[ -]?(plans?|planning|planners?)\\b", page: "/solutions/lesson-planning-for-uae-teachers", examples: ["AI lesson planning UAE", "British curriculum lesson plan generator"] },
  { id: "editing", label: "Edit existing slides", regex: "\\b(edit|editing|change|rewrite|regenerate)\\b.*\\b(slides?|pptx?|powerpoint)\\b|\\b(slides?|pptx?|powerpoint)\\b.*\\b(edit|editing|change|rewrite|regenerate)\\b", page: "/solutions/edit-ppt-without-regenerating", examples: ["edit one slide without regenerating PPT", "PowerPoint change one image"] },
  { id: "cost", label: "Cost and plan evaluation", regex: "\\b(pric(e|es|ing)|costs?|credits?|subscriptions?|affordable|paid plans?|aed)\\b", page: "/solutions/ai-lesson-planning-costs-and-credits", examples: ["AI lesson planner cost AED", "teacher PPT generation credits"] },
  { id: "trial-free", label: "Free and trial research", regex: "\\b(free|trial|no card|without credit card)\\b", page: "/pricing", examples: ["free AI PPT generator teachers", "teacher lesson planner no card trial"] },
  { id: "comparison", label: "Pre-purchase comparisons", regex: "\\b(best|compare|comparison|alternatives?|versus|vs|reviews?|choose|choosing)\\b", page: "/solutions/how-to-choose-ai-presentation-maker-for-teachers", examples: ["best AI presentation maker for teachers", "how to choose a lesson slide generator"] },
  { id: "privacy", label: "Upload and privacy questions", regex: "\\b(privacy|private|student data|gdpr|data protection|upload safety|safe to upload|copyright|licen[cs]e)\\b", page: "/faq", examples: ["safe to upload textbook to AI lesson planner", "AI teaching tools student data privacy"] },
  { id: "worksheets", label: "Worksheets and answer keys", regex: "\\b(worksheets?|answer keys?|question papers?)\\b", page: "/solutions/worksheet-maker-for-uae-teachers", examples: ["worksheet maker UAE teachers", "AI worksheet with answer key"] },
  { id: "assessment", label: "Quizzes and exit tickets", regex: "\\b(quizzes|quiz|exit tickets?|formative assessment)\\b", page: "/solutions/quiz-and-exit-ticket-maker", examples: ["exit ticket generator for teachers", "AI classroom quiz maker"] },
  { id: "differentiation", label: "EAL and differentiated teaching", regex: "\\b(eal|ell|differentiation|differentiat(ed|ion|e)|mixed ability|english as an additional language)\\b", page: "/solutions/differentiated-lesson-presentations", examples: ["differentiate lesson slides with AI", "EAL lesson planning UAE"] },
];

export function matchingSearchIntents(query: string): SearchQueryPattern[] {
  // Bound untrusted imported query text; no raw query is sent to a remote service.
  if (query.length > 1024) throw new RangeError("Search query exceeds 1,024 characters.");
  return searchQueryPatterns.filter((pattern) => new RegExp(pattern.regex, "iu").test(query));
}
