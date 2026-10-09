import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
const base=process.env.BASE_URL||'http://localhost:3003';
const user={id:'teacher',name:'Teacher',email:'teacher@example.com',role:'teacher',permissions:[],status:'active',email_verified:true,locale:'en',timezone:'Asia/Dubai',onboarding_completed:true};
const book={id:'book-1',filename:'Algebra.pdf',status:'ready',stage:'Ready',page_count:80,metadata:{title:'Algebra',curriculum:'British',grade:'10',edition:'2026'},chapters:[{title:'Variables',start:12,end:18}],download:'https://publisher.example/saved.pdf'};
const browser=await launchBrowser();
try{
 const page=await browser.newPage();const errors=[];let searches=0;let importBody;
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname.replace('/api/v1','');let data={items:[],unread:0};
  if(path==='/auth/me')data={user,pending_legal:[]};
  if(path==='/me/usage')data={plan:{code:'pro',name:'Pro'},usage:{credits:{used:0,limit:100,reserved:0,remaining:100}}};
  if(path==='/me/profile')data={grades:['10'],subjects:['Mathematics'],curriculum:'british'};
  if(path==='/memory')data={preferences:[]};
  if(path==='/usage/estimates')data={costs:{course_plan:2,slide:1},remaining:100,reset_at:'2026-11-01'};
  if(path==='/books')data={items:[book]};
  if(path==='/books/discover'){searches++;data={results:'Official book https://publisher.example/algebra.pdf',cached:searches>1};}
  if(path==='/books/import'){importBody=route.request().postDataJSON();data={job_id:'import-job'};}
  if(path==='/jobs/import-job')data={id:'import-job',type:'book_import',status:'succeeded',result:{file_id:book.id}};
  if(path==='/books/book-1/chapters'){const body=route.request().postDataJSON();book.chapters.push(body);data=book;}
  await route.fulfill({json:data});
 });
 for(const width of [320,390,768,1280]){
  await page.setViewportSize({width,height:844});await page.goto(base+'/books');
  await page.getByRole('heading',{name:'Books & notes',exact:true}).waitFor();await page.getByRole('heading',{name:'Algebra',exact:true}).waitFor();
  const consent=page.getByRole('button',{name:'Essential only',exact:true});if(await consent.isVisible())await consent.click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,`Library overflow at ${width}px`);
 }
 await page.getByLabel('Book, curriculum, grade and language',{exact:true}).fill('British grade 10 mathematics');
 await page.getByRole('button',{name:'Find books',exact:true}).click();await page.getByRole('button',{name:'Use PDF link: publisher.example',exact:true}).waitFor();
 await page.getByRole('button',{name:'Find books',exact:true}).click();await page.getByText('Saved search results — no new research call.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Use PDF link: publisher.example',exact:true}).click();await page.getByLabel('Book title',{exact:true}).fill('Algebra');
 await page.getByLabel('I have permission to use this PDF for teaching.').check();await page.getByRole('button',{name:'Save PDF once',exact:true}).click();
 await page.getByText('Saving your PDF',{exact:true}).waitFor();assert.equal(importBody.url,'https://publisher.example/algebra.pdf');assert.equal(importBody.rights_confirmed,true);
 await page.getByLabel('Algebra.pdf chapter title',{exact:true}).fill('Equations');await page.getByLabel('Algebra.pdf chapter start',{exact:true}).fill('19');await page.getByLabel('Algebra.pdf chapter end',{exact:true}).fill('24');
 await page.getByRole('button',{name:'Save chapter',exact:true}).click();await page.getByText('Equations · PDF pages 19–24',{exact:true}).waitFor();
 await page.goto(base+'/projects/new');await page.getByText('Algebra.pdf',{exact:true}).waitFor();await page.getByRole('checkbox',{name:/Algebra.pdf/}).check();
 const chapter=page.getByRole('combobox',{name:'Chapter pages from Algebra.pdf',exact:true});await chapter.selectOption('[19,24]');assert.equal(await chapter.inputValue(),'[19,24]');
 await page.setViewportSize({width:320,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,'Course form has no mobile overflow');assert.deepEqual(errors,[]);
 console.log('Verified saved PDF import, cached discovery, chapter reuse, and library layouts at 320/390/768/1280px.');
}finally{await browser.close();}
