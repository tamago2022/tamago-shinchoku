import fs from 'fs'; import {CG,songs,ERA_YEARS} from './common.mjs';
const C=new Map(); const NC=new Map();
const FIND=n=>{const k=(n||'').toLowerCase(); if(!NC.has(k)){try{NC.set(k,CG.findArtistByName(n))}catch{NC.set(k,null)}} return NC.get(k);}; const out={nogate:[],gap:[],pages:0,shown:0};
const A=+process.env.A||0,Z=+process.env.Z||songs.length;
for(let _i=A;_i<Math.min(Z,songs.length);_i++){ const {a,s}=songs[_i];
  if(a.kind&&a.kind!=='music') continue; if(!a.eras?.length) continue;
  const cur=CG.getCurated(a.id,s.id); const curated=cur?.eraHits??[];
  let fb=[]; if(curated.length<5){ if(!C.has(a.id)){try{C.set(a.id,CG.getEraHitsFallback(a.id,30)||[])}catch{C.set(a.id,[])}} fb=C.get(a.id); }
  const seen=new Set(); const raw=[...curated,...fb].filter(p=>{const k=`${p.by}::${p.title}`.toLowerCase(); if(seen.has(k))return false; seen.add(k); return true;});
  const shown=raw.filter(p=>{
    if(!p.youtubeId) return false;
    if(FIND(p.by)?.id===a.id) return false;
    if(!p.year) return false;
    if(s.year&&Math.abs(p.year-s.year)>10) return false;
    return true;
  }).slice(0,5);
  if(!shown.length) continue; out.pages++; out.shown+=shown.length;
  for(const p of shown){
    if(!s.year){ out.nogate.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name}`,pick:`${p.title} / ${p.by} (${p.year})`,why:'この曲に year が無いため年差チェックが丸ごと素通りしている'}); continue; }
    const gap=Math.abs(p.year-s.year);
    if(gap>ERA_YEARS) out.gap.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name} (${s.year})`,pick:`${p.title} / ${p.by} (${p.year})`,gap});
  }
}
fs.writeFileSync(process.env.OUT||'era.json',JSON.stringify(out));
console.log('pages',out.pages,'shown',out.shown,'年チェック素通り',out.nogate.length,'年差'+ERA_YEARS+'超',out.gap.length);
