// Reproducible canvas motion graphics -> H.264. Requires ffmpeg, Python and Chrome.
import { chromium } from 'playwright-core';
import { spawn, execFileSync } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('../..');
const source=path.join(root,'assets/product-video');
const out=path.resolve('public/videos');fs.mkdirSync(out,{recursive:true});
execFileSync('python3',[path.join(source,'soundtrack.py')],{stdio:'inherit'});
const browser=await chromium.launch({executablePath:process.env.CHROME||undefined});
const page=await browser.newPage();const artwork='data:image/png;base64,'+fs.readFileSync(path.resolve('public/brand/clastio-original.png')).toString('base64');await page.setContent(fs.readFileSync(path.join(source,'film.html'),'utf8').replace('../../apps/web/public/brand/clastio-original.png',artwork));await page.evaluate(()=>Promise.all([document.fonts.ready, window.brandReady]));
try{
for(const vertical of process.env.VIDEO_FORMAT === "web" ? [false] : process.env.VIDEO_FORMAT === "vertical" ? [true] : [false,true]){
 const name=vertical?'clastio-doodle-vertical':'clastio-doodle-web';
 const encoder=spawn('ffmpeg',['-y','-hide_banner','-loglevel','error','-f','image2pipe','-framerate','24','-vcodec','mjpeg','-i','pipe:0','-i',path.join(source,'soundtrack.wav'),'-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-af','loudnorm=I=-18:TP=-2:LRA=7','-movflags','+faststart','-t','30',path.join(out,`${name}.mp4`)],{stdio:['pipe','inherit','inherit']});
 const done=once(encoder,'close');
 for(let f=0;f<720;f++){
   const jpeg=await page.evaluate(([t,v])=>window.renderFrame(t,v),[f/24,vertical]);
   const buffer=Buffer.from(jpeg,'base64');
   if(f===Math.round(26*24)) fs.writeFileSync(path.join(out,`${name}-poster.jpg`),buffer);
   if(!encoder.stdin.write(buffer)) await once(encoder.stdin,'drain');
   if(f%120===0)console.log(`${name}: ${f/24}s / 30s`);
 }
 encoder.stdin.end();const [code]=await done;if(code!==0)throw new Error(`ffmpeg exited ${code}`);
 console.log(`Rendered ${name}.mp4`);
}
}finally{await browser.close();}
