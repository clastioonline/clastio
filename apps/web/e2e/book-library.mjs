// Deterministic curriculum catalogue checks; no paid AI or production downloads.
import assert from 'node:assert/strict';
import { launchBrowser } from './browser.mjs';
const base=process.env.BASE_URL||'http://localhost:3003';
const user={id:'teacher',name:'Teacher',email:'teacher@example.com',role:'teacher',permissions:[],status:'active',email_verified:true,locale:'en',timezone:'Asia/Dubai',onboarding_completed:true};
const book={id:'book-1',filename:'Algebra.pdf',status:'ready',stage:'Ready',page_count:80,metadata:{title:'Algebra',curriculum:'moe',subject:'Mathematics',grade:'10',language:'en',edition:'2026'},chapters:[{title:'Variables',start:12,end:18}],download:'https://publisher.example/saved.pdf'};
const ncert={...book,id:'ncert-1',filename:'NCERT Mathematics.pdf',metadata:{...book.metadata,title:'NCERT Mathematics',curriculum:'moe'}};
const shared={...book,id:'shared-1',catalogue_id:'shared-1',filename:'Geometry.pdf',chapters:book.chapters.map(item=>({...item})),metadata:{...book.metadata,title:'Geometry'},license:'School permission',license_url:'https://school.example/permission'};
const subjects=['Mathematics','Science','Biology','Chemistry','Physics','English','Arabic','Islamic Education','Social Studies & Moral Education','Geography','History','Computing','Artificial Intelligence','Business','Economics','Art','Music','Physical Education'];
const directories=Object.fromEntries(['moe','british','american','ib','cbse','icse','other'].map(curriculum=>[curriculum,subjects.map(subject=>({subject,sources:[{label:curriculum==='cbse'?'NCERT — CBSE':'Official school library',url:curriculum==='cbse'?'https://ncert.nic.in/textbook.php':'https://minhaji.moe.gov.ae/',access:'school_login',note:'Use a school-authorised copy.'}]}))]));
const browser=await launchBrowser();
try{
 const page=await browser.newPage();const errors=[];let searches=0;let importBody;let searchBody;let publicationBody;const saved=[book,ncert];
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname.replace('/api/v1','');let data={items:[],unread:0};
  if(path==='/auth/me')data={user,pending_legal:[]};
  if(path==='/me/usage')data={plan:{code:'pro',name:'Pro'},usage:{credits:{used:0,limit:100,reserved:0,remaining:100}}};
  if(path==='/me/profile')data={grades:['10'],subjects:['Mathematics'],curriculum:'british'};
  if(path==='/memory')data={preferences:[]};
  if(path==='/usage/estimates')data={costs:{course_plan:2,slide:1},remaining:100,reset_at:'2026-11-01'};
  if(path==='/books')data={items:saved};
  if(path==='/books/catalogue')data={items:[shared],directories};
  if(path==='/books/catalogue/shared-1/save'){saved.push({...shared,id:'saved-shared',metadata:{...shared.metadata,catalogue_source_id:shared.id}});data={job_id:'copy-job'};}
  if(path==='/books/discover'){searches++;searchBody=route.request().postDataJSON();data={books:[{title:'UAE Mathematics',publisher:'Ministry of Education',source_url:'https://publisher.example/book',pdf_url:'https://publisher.example/algebra.pdf',access:'public_pdf',subject:'Mathematics',grade:'10',language:'en',edition:'2026',curriculum:'moe'}],cached:searches>1};}
  if(path==='/books/import'){importBody=route.request().postDataJSON();data={job_id:'import-job'};}
  if(path.startsWith('/jobs/'))data={id:path.split('/').at(-1),type:'book_import',status:'succeeded',result:{file_id:book.id}};
  if(path==='/books/book-1/publication'){publicationBody=route.request().postDataJSON();book.catalogue=publicationBody;data={book};}
  if(path==='/books/book-1/chapters'){book.chapters.push(route.request().postDataJSON());data=book;}
  await route.fulfill({json:data});
 });
 for(const width of [320,390,768,1280]){
  await page.setViewportSize({width,height:844});await page.goto(base+'/books');
  await page.getByRole('heading',{name:'Books & notes',exact:true}).waitFor();await page.getByRole('heading',{name:'Algebra',exact:true}).waitFor();
  await page.getByRole('region',{name:'Curriculum subject directory'}).waitFor();
  assert.equal(await page.getByLabel('Book curriculum',{exact:true}).inputValue(),'moe');
  assert.equal(await page.getByRole('heading',{name:'NCERT Mathematics',exact:true}).count(),0);
  assert.equal(await page.getByRole('link',{name:'NCERT — CBSE',exact:true}).count(),0);
  assert.equal(searches,0,'Catalogue browsing makes no model search calls');
  const consent=page.getByRole('button',{name:'Essential only',exact:true});if(await consent.isVisible())await consent.click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,`Catalogue overflow at ${width}px`);
 }
 await page.getByLabel('Book curriculum',{exact:true}).selectOption('cbse');await page.getByRole('heading',{name:'NCERT Mathematics',exact:true}).waitFor();
 assert.ok(await page.getByRole('link',{name:'NCERT — CBSE',exact:true}).count()>0);
 await page.getByLabel('Book curriculum',{exact:true}).selectOption('moe');await page.getByLabel('Book subject',{exact:true}).selectOption('Science');
 await page.getByText('No saved PDF in this selection',{exact:true}).waitFor();assert.equal(await page.getByRole('heading',{name:'Algebra',exact:true}).count(),0);
 await page.getByLabel('Book availability',{exact:true}).selectOption('ready');assert.equal(await page.getByRole('region',{name:'Curriculum subject directory'}).count(),0);
 await page.getByLabel('Book availability',{exact:true}).selectOption('all');await page.getByLabel('Book subject',{exact:true}).selectOption('Mathematics');await page.getByLabel('Book grade / year',{exact:true}).selectOption('10');
 await page.getByRole('button',{name:'Add to my library',exact:true}).click();await page.getByRole('button',{name:'Add to my library',exact:true}).waitFor({state:'hidden'});
 await page.getByText('Find an additional book online',{exact:true}).click();await page.getByLabel('Book, curriculum, grade and language',{exact:true}).fill('UAE Mathematics 2026');
 await page.getByRole('button',{name:'Find books',exact:true}).click();await page.getByRole('button',{name:'Use PDF link: publisher.example',exact:true}).waitFor();
 assert.equal(searchBody.curriculum,'moe');assert.equal(searchBody.subject,'Mathematics');assert.equal(searchBody.grade,'10');
 await page.getByRole('button',{name:'Find books',exact:true}).click();await page.getByText('Saved search results — no new research call.',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Use PDF link: publisher.example',exact:true}).click();await page.getByLabel('I have permission to use this PDF for teaching.').check();
 await page.getByRole('button',{name:'Save PDF once',exact:true}).click();await page.getByText('Saving your PDF',{exact:true}).waitFor();assert.equal(importBody.curriculum,'moe');assert.equal(importBody.url,'https://publisher.example/algebra.pdf');
 await page.getByLabel('Algebra.pdf chapter title',{exact:true}).fill('Equations');await page.getByLabel('Algebra.pdf chapter start',{exact:true}).fill('19');await page.getByLabel('Algebra.pdf chapter end',{exact:true}).fill('24');
 await page.getByRole('region',{name:'Available book PDFs'}).getByRole('button',{name:'Save chapter',exact:true}).first().click();await page.getByText('Equations · PDF pages 19–24',{exact:true}).waitFor();
 assert.equal(await page.getByText('Share in the school book catalogue',{exact:true}).count(),0,'Teachers cannot publish shared books');
 await page.goto(base+'/projects/new');await page.getByText('Algebra.pdf',{exact:true}).waitFor();await page.getByRole('checkbox',{name:/Algebra.pdf/}).check();
 const chapter=page.getByRole('combobox',{name:'Chapter pages from Algebra.pdf',exact:true});await chapter.selectOption('[19,24]');assert.equal(await chapter.inputValue(),'[19,24]');
 await page.setViewportSize({width:320,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,'Course form has no mobile overflow');assert.deepEqual(errors,[]);
 user.role='admin';user.permissions=['settings.modify'];
 await page.goto(base+'/books');await page.reload();
 await page.getByText('Share in the school book catalogue',{exact:true}).first().waitFor();
 await page.getByText('Share in the school book catalogue',{exact:true}).first().click();
 await page.getByLabel('Sharing licence for Algebra.pdf',{exact:true}).fill('School permission');
 await page.getByLabel('Permission reference URL for Algebra.pdf',{exact:true}).fill('https://school.example/permission');
 await page.getByLabel('I have permission to share this PDF and reuse its content with all Clastio teachers.').first().check();
 await page.getByRole('button',{name:'Publish book',exact:true}).first().click();
 await page.getByText('Published in the shared book catalogue.',{exact:true}).waitFor();
 assert.equal(publicationBody.published,true);assert.equal(publicationBody.sharing_rights_confirmed,true);
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)<=1,'Admin publication controls fit mobile');
 assert.deepEqual(errors,[]);
 console.log('Verified curriculum isolation, subject/grade/availability filters, no-search browsing, shared-book reuse, cached discovery, imports and chapter selection at mobile/desktop widths.');
}finally{await browser.close();}
