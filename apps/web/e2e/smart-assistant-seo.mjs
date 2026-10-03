import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
const base = process.env.BASE_URL || 'http://localhost:3100';
const browser = await chromium.launch({executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page = await browser.newPage();
const errors = []; page.on('pageerror', e => errors.push({url:page.url(),message:e.message}));
let phase = 0, confirmBody, startBody, authRequests = 0;
const action = {type:'image_brief', message_id:'brief-1', slide_version:1, lesson_id:'lesson-1', slide_number:4, brief:{change:'Show four leaves',preserve:'Keep the plant and plain background',source:'ai',style:'illustration'}};
await page.route('**/api/v1/**', async route => {
  const path = new URL(route.request().url()).pathname.replace('/api/v1','');
  let data = {items:[],unread:0,total:0};
  if (path === '/auth/me') authRequests++;
  if (path === '/auth/me') data = {user:{id:'review',email:'teacher@example.com',name:'Test Teacher',role:'teacher',permissions:[],status:'active',email_verified:true,locale:'en',timezone:'Asia/Dubai',onboarding_completed:true},pending_legal:[]};
  if (path === '/me/usage') data={plan:{code:'pro',name:'Pro'},usage:{credits:{used:0,limit:50}},trial:{active:false}};
  if (path === '/usage/estimates') data = {costs:{slide:1,course_plan:2},remaining:50,reset_at:'2026-11-01'};
  if (path === '/memory') data = {preferences:[],items:[],known_preferences:{preferred_image_style:'Preferred image style'}};
  if (path === '/assistant/tasks') {phase++;if (phase === 1) startBody=route.request().postDataJSON(); data={conversation_id:'conversation-1',job_id:`reply-${phase}`};}
  if (path === '/assistant/conversations/conversation-1') data={id:'conversation-1',mode:'image_edit',job:{status:'succeeded'},messages:[{role:'user',content:'Please clarify my image change'},{role:'assistant',content:'What should change, what should stay, and which image source do you prefer?',actions:[]},...(phase>=2?[{role:'user',content:'Four leaves, keep the plant, use AI'},{role:'assistant',content:'Review the confirmed requirements.',actions:[confirmBody?{...action,job_id:'image-job-1'}:action]}]:[])]};
  if (path === '/assistant/conversations/conversation-1/confirm-image') {confirmBody=route.request().postDataJSON();data={job_id:'image-job-1'};}
  if (path === '/jobs/image-job-1') data={id:'image-job-1',status:'succeeded',result:{changed:true,credits_used:1},stage:'Done'};
  await route.fulfill({status:200,json:data});
});
try {
  const guides=['ai-ppt-maker-for-teachers-uae','lesson-planning-for-uae-teachers','eal-lessons-uae','british-curriculum-lesson-planning','cbse-lesson-planning-uae','edit-ppt-without-regenerating','personal-ai-teaching-assistant'];
  for (const slug of guides) {
    const response=await page.goto(`${base}/solutions/${slug}`, {waitUntil: "networkidle"});assert.equal(response.status(),200);
    await page.getByRole('heading', {name: 'Example teacher prompt'}).waitFor();
    await page.getByRole('dialog', {name: 'Cookie preferences'}).waitFor();
    assert.equal(await page.locator('h1').count(),1);
    assert.equal(await page.locator('link[rel="canonical"]').getAttribute('href'),`https://clastio.online/solutions/${slug}`);
    assert.equal(JSON.parse(await page.locator('script[type="application/ld+json"]').first().textContent())['@graph'][0]['@type'],'Article');
    assert.ok((await response.text()).includes('Example teacher prompt'));
    for (const width of [390,1440]) {await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${slug} fits ${width}`);}
  }
  const sitemap=await(await page.request.get(`${base}/sitemap.xml`)).text();assert.ok(guides.every(slug=>sitemap.includes(`/solutions/${slug}`)));assert.ok(!sitemap.includes('/login')&&!sitemap.includes('/assistant'));
  const robots=await(await page.request.get(`${base}/robots.txt`)).text();assert.ok(robots.includes('Disallow: /teacher-memory')&&robots.includes('https://clastio.online/sitemap.xml'));
  assert.ok((await(await page.request.get(`${base}/llms.txt`)).text()).includes('## Public resources'));
  assert.equal((await page.request.get(`${base}/solutions/not-a-real-guide`)).status(),404);
  assert.equal(authRequests,0,'public guides do not start authenticated polling');
  await page.goto(`${base}/assistant?mode=image_edit&lesson=lesson-1&slide=4`);
  await page.getByRole('button',{name:'I want to change this slide’s image. Please ask me what should change and what must stay.'}).click();
  await page.getByText('What should change, what should stay, and which image source do you prefer?',{exact:true}).waitFor();
  assert.equal(startBody.mode,'image_edit');assert.equal(startBody.lesson_id,'lesson-1');assert.equal(startBody.slide_number,4);
  assert.equal(await page.getByRole('button',{name:'Confirm image replacement',exact:true}).count(),0);
  await page.getByPlaceholder('Describe the change or answer the clarification questions…').fill('Four leaves, keep the plant, use AI');
  await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.getByRole('button',{name:'Confirm image replacement',exact:true}).waitFor();
  await page.getByRole('switch',{name:'Remember this style and source for future PPTs'}).click();
  await page.getByRole('button',{name:'Confirm image replacement',exact:true}).click();
  await page.getByRole('button',{name:'Replacement requested',exact:true}).waitFor();
  assert.deepEqual(confirmBody,{message_id:'brief-1',remember_style:true});
  await page.getByText('Image request completed',{exact:true}).waitFor();
  for (const width of [390,1440]) {await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`assistant fits ${width}`);}
  await page.getByRole('button', {name: 'Open activity', exact: true}).click();
  const dialog = page.getByRole('dialog', {name: 'Your activity'});
  await dialog.getByText('Your work keeps going when you leave this page—even if you close the browser.', {exact: true}).click();
  assert.ok(await dialog.isVisible(), 'clicking inside a dialog keeps it open');
  await dialog.getByRole('button', {name: 'Keep exploring'}).click();
  assert.deepEqual(errors,[]);
  console.log('Seven guides, server HTML, canonical/structured data, sitemap, robots, 404, responsive layouts and clarify/confirm/remember flow passed.');
} finally {await browser.close();}
