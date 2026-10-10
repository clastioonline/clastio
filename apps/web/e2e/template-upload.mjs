// Multipart submission test with deterministic fixtures; no AI calls or database mutations.
import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
import path from 'node:path';
const base=process.env.BASE_URL||'http://localhost:3003';
const browser=await launchBrowser();
try{
 const page=await browser.newPage();const errors=[];let received;
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/v1/**',async route=>{
  const url=new URL(route.request().url()).pathname.replace('/api/v1','');
  let data={items:[],unread:0};
  if(url==='/auth/me')data={user:{id:'teacher',name:'Teacher',email:'teacher@example.com',role:'teacher',permissions:[],status:'active',email_verified:true,locale:'en',timezone:'Asia/Dubai',onboarding_completed:true},pending_legal:[]};
  if(url==='/me/usage')data={plan:{code:'pro',name:'Pro'},usage:{credits:{used:0,limit:100,reserved:0,remaining:100}}};
  if(url==='/me/profile')data={grades:['10'],subjects:['Mathematics'],curriculum:'moe'};
  if(url==='/memory')data={preferences:[]};
  if(url==='/usage/estimates')data={costs:{course_plan:2,slide:1},remaining:100,reset_at:'2026-11-01'};
  if(url==='/courses/from-template'){
   received={type:route.request().headers()['content-type'],body:route.request().postDataBuffer().toString('utf8')};
   return route.fulfill({status:400,json:{error:{message:'Fixture captured the multipart request.',code:'fixture'}}});
  }
  await route.fulfill({json:data});
 });
 for(const width of [320,390,1280]){
  await page.setViewportSize({width,height:844});await page.goto(base+'/projects/new');
  await page.getByLabel('Base PowerPoint template',{exact:true}).waitFor();
  await page.getByLabel('Base PowerPoint template',{exact:true}).setInputFiles(path.resolve('samples/preserved-template.pptx'));
  await page.getByText('preserved-template.pptx',{exact:true}).waitFor();
  const consent=page.getByRole('button',{name:'Essential only',exact:true});if(await consent.isVisible())await consent.click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,`Template upload overflow at ${width}px`);
 }
 await page.getByLabel('Chapter / topic',{exact:true}).fill('Algebra');
 await page.getByRole('button',{name:'Plan chapter & build first lesson',exact:true}).click();
 await page.getByText('Fixture captured the multipart request.',{exact:true}).waitFor();
 assert.ok(received.type.startsWith('multipart/form-data; boundary='));
 assert.ok(received.body.includes('name="file"; filename="preserved-template.pptx"'));
 assert.ok(received.body.includes('name="payload"'));
 assert.ok(received.body.includes('"topic":"Algebra"'));
 assert.deepEqual(errors,[]);
 console.log('Verified template upload and multipart file + teaching-payload submission at mobile and desktop widths.');
}finally{await browser.close();}
