import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
const base=process.env.BASE_URL||'http://localhost:3000';
const browser=await chromium.launch({executablePath:process.env.CHROME||undefined});
const page=await browser.newPage();
try{
 await page.goto(`${base}/#product-video`);
 await page.getByRole('heading',{name:'Big ideas. A little less prep.',exact:true}).waitFor();
 const video=page.locator('#product-video video');
 assert.equal(await video.getAttribute('preload'),'none');
 assert.equal(await video.getAttribute('autoplay'),null);
 await video.evaluate(async el=>{el.muted=true;await el.play();});
 await page.waitForFunction(()=>document.querySelector('video').currentTime>.5);
 const info=await video.evaluate(el=>({width:el.videoWidth,height:el.videoHeight,duration:el.duration,error:el.error?.message}));
 assert.equal(info.width,1920);assert.equal(info.height,1080);assert.equal(info.duration,30);assert.equal(info.error,undefined);
 await video.evaluate(el=>el.pause());
 await page.getByText('Read the video transcript',{exact:true}).click();
 await page.getByText('Clastio: Plan. Teach. Shine. Start your next lesson.',{exact:true}).waitFor();
 for(const width of [320,390,768,1440]){
  await page.setViewportSize({width,height:900});
  const fits=await video.evaluate(el=>el.getBoundingClientRect().right<=innerWidth);
  assert.ok(fits,`player fits ${width}px`);
 }
 for(const file of ['clastio-doodle-vertical.mp4','clastio-doodle.vtt','clastio-doodle-web-poster.jpg']){
  const r=await page.request.get(`${base}/videos/${file}`);assert.equal(r.status(),200,file);
 }
 console.log('✓ Video decodes and plays, transcript works, exports load, player fits mobile and desktop.');
}finally{await browser.close();}
