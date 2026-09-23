import fs from 'fs'; import {SP,SIG,byId,songs,norm,ERA_YEARS} from './common.mjs';
const manualKeys=new Set(Object.keys(SP.shelfPicksBySong));
const out={nobasis:[],missing:[],pages:0,picks:0,manualPages:0};
const A=+process.env.A||0, Z=+process.env.Z||songs.length;
for(let i=A;i<Math.min(Z,songs.length);i++){
  const {a,s}=songs[i]; let picks=[]; try{picks=SP.getShelfPicks(a.id,s.id)||[]}catch{continue}
  if(!picks.length) continue;
  const manual=manualKeys.has(`${a.id}:${s.id}`); out.pages++; if(manual)out.manualPages++;
  for(const p of picks){ out.picks++;
    if(manual||p.to) continue;
    const ta=byId.get(p.artistId); if(!ta){out.missing.push({page:`${a.id}:${s.id}`,pick:`${p.artistId}:${p.songId}`,why:'参照先のアーティストが名簿に無い'});continue;}
    const ts=(ta.songs||[]).find(x=>x.id===p.songId); if(!ts){out.missing.push({page:`${a.id}:${s.id}`,pick:`${p.artistId}:${p.songId}`,why:'参照先の曲が無い'});continue;}
    if(ta.id===a.id) continue;
    if((s.originalRef&&s.originalRef.artistId===ta.id)||(ts.originalRef&&ts.originalRef.artistId===a.id)) continue;
    if(s.year&&ts.year&&Math.abs(s.year-ts.year)<=ERA_YEARS) continue;
    let ctx=false; try{ctx=SIG.sharesMusicalContext(a,ta)}catch{}
    if(ctx) continue;
    out.nobasis.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name}${s.year?` (${s.year})`:''}`,
      pick:`${ts.title} / ${ta.name}${ts.year?` (${ts.year})`:''}`,shelf:p.shelf,
      why:'同じ棚に入っているだけ（同一人物でも・原曲/カバー関係でも・同年代でも・同系統でもない）'});
  }
}
fs.writeFileSync(process.env.OUT||'flow.json',JSON.stringify(out));
console.log('pages',out.pages,'picks',out.picks,'手選び',out.manualPages,'根拠なし',out.nobasis.length,'参照先なし',out.missing.length);
