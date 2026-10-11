// Deterministic educator workspace checks: no database writes or live model calls.
import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';

const base = process.env.BASE_URL || 'http://localhost:3003';
const user = { id: 'educator-teacher', name: 'Educator Teacher', email: 'educator@example.com', role: 'teacher', permissions: [], status: 'active', email_verified: true, locale: 'en', timezone: 'Asia/Dubai', onboarding_completed: true };
const metadata = { topic: 'Ecosystems', subject: 'Science', grade: '6', curriculum: 'UAE MoE', language: 'en', education_stage: 'primary', framework: 'khda', status: 'ready', version: 1 };
const planContent = {
 title: 'Mangroves and ecosystems', ...metadata, duration_minutes: 45,
 learning_objectives: [{ id: 'LO1', description: 'Explain two mangrove adaptations.', success_measure: 'Explain two adaptations using evidence.' }],
 success_criteria: [{ id: 'SC1', description: 'I can link an adaptation to its benefit.' }],
 lesson_sequence: [{ name: 'Explore', duration_minutes: 45, teacher_actions: 'Model how roots support mangroves.', student_actions: 'Discuss the diagram with a partner.' }],
 formative_assessment: [{ id: 'FA1', tool: 'Exit ticket', question_or_task: 'How do mangroves survive salty water?', expected_response: 'They have adaptations that manage salt.', teaching_response: 'Revisit the diagram when evidence is missing.' }],
 differentiation: { sen: [{ learning_barrier: 'Text density', scaffold: 'Use labelled images.', assessment_accommodation: 'Accept an oral explanation.' }], ell: [{ learning_barrier: 'Academic vocabulary', scaffold: 'Use sentence frames.', assessment_accommodation: 'Give vocabulary support.' }] },
 homework: 'Sketch and label a mangrove adaptation.', review_checks: { teacher_checks: ['Check source accuracy and class suitability.'], evidence_gaps: ['Confirm local examples.'] },
};
let plan = { id: 'plan-1', title: planContent.title, ...metadata, duration_minutes: 45, content: planContent, downloads: { pdf: '/fixture-plan.pdf', docx: '/fixture-plan.docx' } };
const demo = { id: 'demo-1', title: 'Mangrove micro-lesson', ...metadata, duration_minutes: 15, content: { hook: { teacher_says: 'How can trees grow in salty water?', learner_interaction: 'Think and share.' }, teacher_script: [{ order: 1, start_seconds: 0, end_seconds: 900, slide_numbers: [1], teacher_says: 'Observe this mangrove.', expected_student_response: 'Its roots look different.' }], slide_payload: { slides: [{ number: 1, title: 'Mangroves' }] } }, downloads: { pptx: '/fixture-demo.pptx', pdf: '/fixture-demo.pdf' } };
const resource = { id: 'guide-1', title: 'Ecosystems study guide', ...metadata, origin: 'generated', kind: 'study_guide', content: { title: 'Ecosystems study guide', overview: 'Learn how organisms interact.', chapters: [{ number: 1, title: 'Mangroves', explanation: 'Mangroves provide coastal habitat.', expected_answers: ['Roots support the tree.'] }] }, downloads: { pdf: '/fixture-guide.pdf' } };
const task = { id: 'task-1', title: 'Mangrove reading task', ...metadata, origin: 'generated', kind: 'study_guide', content: { printable_task: { title: 'Mangrove reading task', student_instructions: 'Read, then explain how roots help a mangrove.', differentiation: { ell: ['Use the sentence frame: Roots help because…'], sen: ['Match diagrams before reading.'] }, teacher_answer_key: ['Roots support the mangrove in soft soil.'] } }, downloads: { pdf: '/fixture-task.pdf', docx: '/fixture-task.docx' } };
task.request = { ...metadata, topic: 'ecosystems', source_file_ids: [], source_page_ranges: {}, conversation_id: 'conversation-1' };
const conversation = { id: 'conversation-1', title: 'Saved Grade 6 mangrove conversation', messages: [{ id: 'message-1', role: 'assistant', content: 'Your task is ready.', actions: [{ type: 'copilot_resource', resource_id: task.id }] }] };
const requests = [];
const browser = await launchBrowser();
try {
 const page = await browser.newPage();
 const errors = [];
 page.on('pageerror', error => errors.push(error.message));
 await page.route('**/api/v1/**', async route => {
  const request = route.request(); const url = new URL(request.url()); const path = url.pathname.replace('/api/v1', ''); const method = request.method();
  let body = null; if (method !== 'GET') { try { body = request.postDataJSON(); } catch {} requests.push({ path, method, body }); }
  let data = { items: [], unread: 0 };
  if (path === '/auth/me') data = { user, pending_legal: [] };
  else if (path === '/me/profile') data = { subjects: ['Science'], grades: ['6'], curriculum: 'british', teaching_languages: ['en'], regulatory_authority: 'not_specified', education_stages: ['primary'] };
  else if (path === '/me/usage') data = { plan: { code: 'pro', name: 'Pro' }, usage: { credits: { used: 0, limit: 200, reserved: 0, remaining: 200 } } };
  else if (path === '/books') data = { items: [] };
  else if (path === '/templates') data = { items: [{ id: 'template-1', name: 'Teacher design', status: 'ready' }] };
  else if (path === '/lesson-plans' && method === 'POST') data = { lesson_plan_id: plan.id, job_id: 'plan-job', lesson_plan: plan };
  else if (path === '/lesson-plans') data = { items: [plan] };
  else if (path === '/lesson-plans/plan-1' && method === 'PUT') { plan = { ...plan, title: body.content.title, content: body.content, version: plan.version + 1 }; data = plan; }
  else if (path === '/lesson-plans/plan-1/review') { plan = { ...plan, status: 'reviewed' }; data = plan; }
  else if (path === '/lesson-plans/plan-1') data = plan;
  else if (path === '/demo-classes' && method === 'POST') data = { demo_class_id: demo.id, job_id: 'demo-job', demo_class: demo };
  else if (path === '/demo-classes') data = { items: [demo] };
  else if (path === '/demo-classes/demo-1') data = demo;
  else if (path === '/digital-resources/generate') data = { resource_id: resource.id, resource, cached: true, job_id: null };
  else if (path === '/digital-resources') { requests.push({ path, method, query: Object.fromEntries(url.searchParams) }); data = { items: [resource] }; }
  else if (path === '/digital-resources/guide-1') data = resource;
  else if (path === '/digital-resources/task-1') data = task;
  else if (path === '/copilot/resources' && method === 'POST') data = { resource: task, job_id: 'task-job', cached: false, conversation_id: conversation.id };
  else if (path === '/copilot/resources') data = { items: [task] };
  else if (path === '/copilot/conversations') data = { items: [conversation] };
  else if (path === '/copilot/conversations/conversation-1') data = conversation;
  else if (path.startsWith('/jobs/')) data = { id: path.split('/').pop(), type: 'educator', status: 'succeeded', progress: 100, stage: 'Ready', error: null, result: {} };
  await route.fulfill({ json: data });
 });
 const headings = { '/lesson-planners': 'Lesson planners', '/demo-classes': 'Demo class generator', '/digital-library': 'Digital library', '/copilot': 'AI teacher copilot' };
 for (const width of [320, 390, 768, 1280]) {
  await page.setViewportSize({ width, height: 900 });
  for (const [path, heading] of Object.entries(headings)) {
   await page.goto(base + path); await page.getByRole('heading', { name: heading, exact: true }).waitFor();
   const consent = page.getByRole('button', { name: 'Essential only', exact: true }); if (await consent.isVisible()) await consent.click();
   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
   assert.ok(overflow <= 1, `${path} at ${width}px overflows by ${overflow}px`);
  }
 }
 await page.setViewportSize({ width: 1280, height: 900 });
 await page.goto(base + '/lesson-planners');
 await page.getByLabel(/^Topic$/).fill('Ecosystems');
 assert.equal(await page.getByLabel(/^Planning framework/).inputValue(), 'not_specified');
 await page.getByLabel(/^Planning framework/).selectOption('khda');
 await page.getByRole('button', { name: 'Generate lesson plan', exact: true }).click();
 await page.getByRole('heading', { name: plan.title, exact: true }).waitFor();
 assert.ok(page.url().includes('?id=plan-1'), 'Generated plan has a durable deep link');
 const planRequest = requests.find(item => item.path === '/lesson-plans' && item.method === 'POST');
 assert.equal(planRequest.body.framework, 'khda'); assert.equal(planRequest.body.duration_minutes, 45);
 await page.getByRole('button', { name: 'Edit plan', exact: true }).click();
 await page.getByLabel('Plan title', { exact: true }).fill('Reviewed mangrove lesson');
 await page.getByRole('button', { name: 'Save changes', exact: true }).click();
 await page.getByRole('heading', { name: 'Reviewed mangrove lesson', exact: true }).waitFor();
 assert.equal(requests.find(item => item.method === 'PUT').body.version, 1, 'Edits carry the version for conflict detection');
 await page.getByLabel('Review notes', { exact: true }).fill('Class suitability checked.');
 await page.getByRole('button', { name: 'Mark reviewed', exact: true }).click();
 await page.getByRole('button', { name: 'Reviewed by teacher', exact: true }).waitFor();
 await page.goto(base + '/demo-classes'); await page.getByLabel(/^Topic$/).fill('Ecosystems');
 await page.getByLabel(/^Presentation design/).selectOption('template-1');
 await page.getByRole('button', { name: 'Generate demo class', exact: true }).click();
 await page.getByRole('heading', { name: demo.title, exact: true }).waitFor();
 const demoRequest = requests.find(item => item.path === '/demo-classes' && item.method === 'POST');
 assert.equal(demoRequest.body.duration_minutes, 15); assert.equal(demoRequest.body.template_id, 'template-1');
 await page.getByRole('link', { name: 'Download PPTX', exact: true }).waitFor();
 await page.goto(base + '/digital-library');
 await Promise.all([page.waitForResponse(response => response.url().includes('/digital-resources?education_stage=university')), page.getByRole('button', { name: 'University', exact: true }).click()]);
 assert.ok(requests.some(item => item.query?.education_stage === 'university'), 'Stage category reaches the API');
 await page.getByLabel(/^Topic$/).fill('Ecosystems');
 await page.getByRole('button', { name: 'Find or create resource', exact: true }).click();
 await page.getByRole('heading', { name: resource.title, exact: true }).waitFor();
 assert.ok(requests.some(item => item.path === '/digital-resources/generate' && item.body.chapter_count === 4));
 await page.getByRole('link', { name: 'Download PDF', exact: true }).waitFor();
 await page.goto(base + '/copilot');
 await page.getByRole('button', { name: 'Adjust context', exact: true }).click();
 await page.getByLabel(/^Grade \/ year/).fill('7');
 await page.getByRole('button', { name: 'Hide context', exact: true }).click();
 await page.getByLabel('Ask your teacher copilot', { exact: true }).fill('Generate a differentiated reading task for Grade 6 Science about ecosystems, linking it to UAE mangroves.');
 await page.getByRole('button', { name: 'Generate printable classroom task', exact: true }).click();
 await page.getByRole('heading', { name: task.title, exact: true }).waitFor();
 const explicitTask = requests.find(item => item.path === '/copilot/resources' && item.body.request.includes('mangrove'));
 assert.ok(explicitTask); assert.equal(explicitTask.body.grade, '6'); assert.equal(explicitTask.body.subject, 'Science'); assert.equal(explicitTask.body.education_stage, 'primary');
 assert.equal(explicitTask.body.topic, 'ecosystems');
 await page.getByRole('link', { name: 'Download DOCX', exact: true }).waitFor();
 await page.getByRole('button', { name: 'Adjust context', exact: true }).click();
 await page.getByLabel(/^Grade \/ year/).fill('7');
 await page.getByRole('button', { name: conversation.title, exact: true }).click();
 await page.waitForFunction(() => [...document.querySelectorAll('input')].some(input => input.value === '6'));
 assert.equal(await page.getByLabel(/^Grade \/ year/).inputValue(), '6', 'Resuming a saved conversation restores its classroom grade');
 await page.getByLabel('Ask your teacher copilot', { exact: true }).fill('Make this reading task easier.');
 await Promise.all([page.waitForResponse(response => response.url().endsWith('/copilot/resources') && response.request().method() === 'POST'), page.getByRole('button', { name: 'Generate printable classroom task', exact: true }).click()]);
 const resumedTask = requests.find(item => item.path === '/copilot/resources' && item.body.request === 'Make this reading task easier.');
 assert.equal(resumedTask.body.grade, '6'); assert.equal(resumedTask.body.topic, 'ecosystems'); assert.equal(resumedTask.body.framework, 'khda');
 assert.equal(resumedTask.body.conversation_id, conversation.id);
 await page.goto(base + '/copilot?id=task-1');
 await page.getByRole('heading', { name: task.title, exact: true }).waitFor();
 assert.equal(await page.locator('[data-educator-document]').count(), 1, 'Saved task deep links reopen the printable component');
 await page.getByRole('button', { name: 'Adjust context', exact: true }).click();
 await page.getByLabel(/^Education stage/).selectOption('university');
 assert.equal(await page.getByLabel(/^Planning framework/).inputValue(), 'not_specified');
 const universityOptions = await page.getByLabel(/^Planning framework/).locator('option').evaluateAll(options => options.map(option => option.value));
 assert.deepEqual(universityOptions.sort(), ['not_specified', 'other']);
 assert.deepEqual(errors, []);
 console.log('✓ Educator pages fit four viewport widths; planner edit/review, timed demo, stage filters, cached guides and printable copilot deep links work.');
} finally { await browser.close(); }
