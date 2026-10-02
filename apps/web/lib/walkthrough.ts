export type WalkthroughStep = { title: string; text: string; route: string; target?: string; permission?: string };
export const TEACHER_WALKTHROUGH: WalkthroughStep[] = [
  { route: '/dashboard', title: 'Your teaching day', text: 'See your next class, ready lessons and preparation tasks. Generation continues in the background while you teach.' },
  { route: '/templates', title: 'Keep your own slide design', text: 'Upload a PowerPoint you already use. Check the extracted layouts and choose a default design before building new lessons.' },
  { route: '/curriculum', title: 'Classes and curriculum', text: 'Add your classes, grades and subjects. Each class keeps separate pace, support needs and curriculum coverage.' },
  { route: '/calendar', title: 'Timetable and school dates', text: 'Add teaching periods, holidays and shortened days so planning uses the right class and lesson duration.' },
  { route: '/projects/new', title: 'Upload chapter references', text: 'Use Upload books / notes for a textbook chapter or typed notes. Select the sources to use and wait until they are ready. Scanned PDFs need searchable text.', target: '[data-tour="chapter-sources"]' },
  { route: '/projects/new', title: 'Prepare the way you teach', text: 'Choose the complete chapter, selected parts or day-by-day preparation. Daily mode builds the first lesson and leaves later parts for you to prepare after class.', target: '[data-tour="chapter-mode"]' },
  { route: '/projects/new', title: 'Previous teaching and revision', text: 'Describe what the class already covered and what needs another explanation. Include examples, activities and timing in your instructions.', target: '[data-tour="chapter-revision"]' },
  { route: '/projects', title: 'Review, build and edit', text: 'Open a project to review the chapter sequence. Open a ready lesson for the manual editor: change content, tables, charts or images, then Save & rebuild. Download the editable PPT for full desktop editing.' },
  { route: '/lessons', title: 'Your lesson library', text: 'Find completed lessons and documents. After class, record what you taught and where students struggled so the next lesson includes the right recap.' },
  { route: '/activity', title: 'Follow background work', text: 'Check upload, planning and rendering progress here. You can leave a page while work runs; reopen it when the task finishes. Failed tasks show their error.' },
  { route: '/assistant', title: 'Your teaching assistant', text: 'Ask for lesson planning, subject explanations, assessments or classroom help. Include the topic and grade. Unrelated requests are redirected to a teaching task.' },
  { route: '/teacher-memory', title: 'Remember classroom needs', text: 'Review preferences, classroom feedback and revision needs. Correct anything that is inaccurate before relying on it in future lessons.' },
  { route: '/media', title: 'Pictures and media', text: 'Create illustrations when live generation and image credits are available. Placeholders are marked for replacement; check every diagram before using it in class.' },
  { route: '/whatsapp', title: 'WhatsApp planning', text: 'When connected, receive plans and share classroom feedback through WhatsApp. The local simulator lets you try the workflow without sending messages.' },
  { route: '/notifications', title: 'Updates and reminders', text: 'Find finished jobs, reminders and important account updates. Choose notification preferences in Settings.' },
  { route: '/billing', title: 'Plans and credits', text: 'Check your lesson and media allowances before generating a large chapter. Billing changes do not happen as part of this walkthrough.' },
  { route: '/support', title: 'Help when you need it', text: 'Contact support with the project and request reference when work fails. Tutorials & help contains short guides and lets you replay this walkthrough.' },
  { route: '/settings', title: 'Your preferences', text: 'Review profile, language, notification and account settings. You can replay a page guide or the complete walkthrough from the header at any time.' },
];
export const ADMIN_WALKTHROUGH: WalkthroughStep[] = [
  { route: '/admin', title: 'Platform overview', text: 'Review usage, active users and operational status.', permission: 'analytics.view' },
  { route: '/admin/users', title: 'Teachers and access', text: 'Find teachers and inspect account status. Account changes are separate actions and are recorded in the audit log.', permission: 'users.view' },
  { route: '/admin/plans', title: 'Plans and allowances', text: 'Review lesson credits, upload sizes and concurrent job allowances before changing a plan.', permission: 'billing.view' },
  { route: '/admin/ai-costs', title: 'AI costs and limits', text: 'Approve model prices and spending caps before enabling paid calls. Inspect recorded costs and unresolved reservations.', permission: 'api_usage.view' },
  { route: '/admin/system', title: 'System health', text: 'Check database, Redis, storage, worker heartbeat and queue state before a release. Queued jobs are different from failed jobs.', permission: 'system.logs.view' },
  { route: '/admin/support', title: 'Support requests', text: 'Review teacher reports and use request references to locate failures.', permission: 'support.manage' },
  { route: '/admin/security', title: 'Security events', text: 'Inspect authentication and access events. This guide makes no changes to accounts or permissions.', permission: 'security.view' },
  { route: '/admin/audit', title: 'Audit history', text: 'Review recorded administrative changes and their actor.', permission: 'audit.view' },
  { route: '/admin/settings', title: 'Platform configuration', text: 'Review maintenance, integrations and feature flags. Production deployment still needs HTTPS, approved live providers, backups and monitoring.', permission: 'settings.modify' },
];
export function walkthroughSteps(pathname: string, admin: boolean, permissions: string[], pageOnly = false): WalkthroughStep[] {
  const all = (admin ? ADMIN_WALKTHROUGH : TEACHER_WALKTHROUGH).filter(step => !step.permission || permissions.includes(step.permission));
  if (!pageOnly) return all;
  if (!admin && /^\/lessons\/[^/]+$/.test(pathname)) return [
    { route: pathname, title: 'Read the lesson', text: 'Check slide previews and teacher notes before class. The quality panel reports layout checks and image placeholders.' },
    { route: pathname, title: 'Edit manually', text: 'Choose a slide and use Slides & manual editor to edit text, tables, charts and notes. Upload / replace image fixes an unsuitable picture. Save & rebuild keeps a version history.', target: '[data-tour="slide-editor"]' },
    { route: pathname, title: 'Download and teach', text: 'Download editable PPT to open in PowerPoint. Use PDF for sharing or printing. Review factual content and diagrams before class.' },
    { route: pathname, title: 'Record the previous class', text: 'After class, add what you taught, what needs revision and the last completed slide. Prepare the next day from the chapter page.', target: '[data-tour="class-reflection"]' },
  ];
  if (!admin && /^\/projects\/[^/]+$/.test(pathname) && pathname !== '/projects/new') return [
    { route: pathname, title: 'Your chapter sequence', text: 'Review lesson parts, objectives and readiness. Edit sequence changes the plan; it does not rewrite finished slide files.' },
    { route: pathname, title: 'Prepare a part or the next day', text: 'Build a selected part or Prepare next day. Supply previous-class notes, revision topics and instructions before starting the job.' },
    { route: pathname, title: 'Open the ready lesson', text: 'Open a finished lesson to use its manual editor, download files and record how the class went.' },
  ];
  return all.filter(step => step.route === pathname);
}
