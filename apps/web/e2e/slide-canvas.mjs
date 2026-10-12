import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const base = 'http://localhost:3005';
page.on('pageerror', error => console.error(error.message));
let saved;
const preview = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="white"/><text x="320" y="220">Example text</text></svg>');
const spec = { number: 1, layout: 'concept', title: 'Example', bullets: [{text:'Explanation'}], steps: [], columns: [], visual: {}, timing_minutes: 3, speaker_notes: '', manual_objects: {} };
const objects = [{id:'text',name:'Teaching text',text:'Example text',x:.2,y:.2,width:.3,height:.1,aspect_ratio:16/9}, {id:'background',name:'Background',x:0,y:0,width:1,height:1,aspect_ratio:16/9}];
try {
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let value = { items: [] };
    if (path.endsWith('/auth/me')) value = {user:{id:'test',name:'Teacher',email:'test@example.com',role:'teacher',permissions:[],onboarding_completed:true,email_verified:true},pending_legal:[]};
    if (path.endsWith('/me/usage')) value = {plan:{code:'free',name:'Free'},usage:{credits:{limit:10,used:0,reserved:0,remaining:10}},trial:{active:false}};
    if (path.endsWith('/usage/estimates')) value = {costs:{slide:1}};
    if (path.endsWith('/lessons/test')) value = {lesson:{id:'test',number:1,title:'Example',status:'ready',qc:{}},course:{project_id:'test',topic:'Example',grade:'10'},slides:[{id:'slide',number:1,version:1,spec,preview,qc:{editable_objects:objects}}],documents:[],downloads:{},reflections:[]};
    if (path.endsWith('/slides/1') && route.request().method() === 'PATCH') { saved = route.request().postDataJSON(); value = {job_id:null}; }
    await route.fulfill({json:value});
  });
  await page.goto(`${base}/lessons/test#ppt-editor`);
  const consent = page.getByRole('button',{name:'Essential only',exact:true});
  if (await consent.count()) await consent.click();
  const canvas = page.getByLabel('Editable slide canvas', {exact:true});
  await canvas.waitFor();
  await canvas.scrollIntoViewIfNeeded();
  const bounds = await canvas.boundingBox();
  await page.mouse.move(bounds.x+bounds.width*.25,bounds.y+bounds.height*.25);
  await page.mouse.down();
  await page.mouse.move(bounds.x+bounds.width*.35,bounds.y+bounds.height*.35,{steps:8});
  await page.mouse.up();
  assert.equal(await page.getByText('Slide object',{exact:true}).locator('..').locator('select').inputValue(),'text');
  assert.equal(Number(await page.getByText('x (%)',{exact:true}).locator('..').locator('input').inputValue()),30);
  assert.equal(Number(await page.getByText('y (%)',{exact:true}).locator('..').locator('input').inputValue()),30);
  await page.getByRole('button',{name:'Undo',exact:true}).click();
  assert.equal(Number(await page.getByText('x (%)',{exact:true}).locator('..').locator('input').inputValue()),20);
  await page.getByRole('button',{name:'Redo',exact:true}).click();
  assert.equal(Number(await page.getByText('x (%)',{exact:true}).locator('..').locator('input').inputValue()),30);
  await canvas.focus();
  await page.keyboard.press('ArrowRight');
  assert.equal(Number(await page.getByText('x (%)',{exact:true}).locator('..').locator('input').inputValue()),31);
  await page.keyboard.press('ArrowLeft');
  await page.getByRole('button',{name:'Save & rebuild · 0 credits',exact:true}).click();
  await page.waitForTimeout(300);
  assert.ok(Math.abs(saved.spec.manual_objects.text.x-.3) < 1e-9);
  assert.ok(Math.abs(saved.spec.manual_objects.text.y-.3) < 1e-9);
  console.log('Canvas selects text over backgrounds, drags, undoes/redoes and saves geometry.');
} catch (error) { console.error((await page.locator('body').innerText()).slice(0, 2000)); throw error; }
finally { await browser.close(); }
