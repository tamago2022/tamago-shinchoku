import fs from "node:fs"; import os from "node:os"; import path from "node:path";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));
function findShell(){const base=path.join(os.homedir(),"Library","Caches","ms-playwright");for(const d of fs.readdirSync(base).filter(x=>x.startsWith("chromium_headless_shell-")).sort().reverse()){for(const s of ["chrome-headless-shell-mac-arm64","chrome-headless-shell-mac-x64"]){const p=path.join(base,d,s,"chrome-headless-shell");if(fs.existsSync(p))return p;}}return "";}
const url=process.argv[2]||"https://joy-relief-station.lovable.app/";
const b=await chromium.launch({executablePath:findShell(),args:["--mute-audio"]});
const ctx=await b.newContext({viewport:{width:375,height:810},deviceScaleFactor:2,isMobile:true,hasTouch:true,userAgent:"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 koutai-kanmon"});
const pg=await ctx.newPage();
await pg.goto(url,{waitUntil:"load",timeout:90000});await pg.waitForTimeout(3000);
try{await pg.waitForLoadState("networkidle",{timeout:15000})}catch{}
const r=await pg.evaluate(()=>{const vis=[];for(const e of document.querySelectorAll('body *')){if(vis.length>=1500)break;const r=e.getBoundingClientRect();if(r.width>0&&r.height>0&&r.top<4000)vis.push([e,r]);}
const hasText=e=>Array.from(e.childNodes).some(n=>n.nodeType===3&&n.textContent.trim().length>0);
const F={},C={};for(const [e,r] of vis){if(!hasText(e))continue;const cs=getComputedStyle(e);const f=(cs.fontFamily||'').split(',')[0].trim().replace(/["']/g,'').toLowerCase();
const s=(e.tagName+'.'+(e.className&&e.className.baseVal===undefined?String(e.className).slice(0,60):'')+' top='+Math.round(r.top)+' "'+e.textContent.trim().slice(0,30)+'"');
(F[f]=F[f]||[]).push(s);(C[cs.color]=C[cs.color]||[]).push(s);}
const o={fonts:{},colors:{}};for(const k in F)o.fonts[k]={n:F[k].length,ex:F[k].slice(0,6)};for(const k in C)o.colors[k]={n:C[k].length,ex:C[k].slice(0,3)};o.nVis=vis.length;o.nAll=document.querySelectorAll('body *').length;return o;});
console.log(JSON.stringify(r,null,1));
await pg.screenshot({path:process.argv[3]||"/tmp/x.png",fullPage:false});
await b.close();
