import fs from 'fs'; import {songs,artists,norm} from './common.mjs';
const R={cover_candidate:[],linked_nosource:[],no_video:[],no_year:[],no_note:[],note_spotify:[],note_cut:[],same_name:[]};
const titleIdx=new Map();
for(const {a,s} of songs){const k=norm(s.title); if(!k||k.length<3)continue; (titleIdx.get(k)||titleIdx.set(k,[]).get(k)).push({a,s});}
const hasSrc=t=>/https?:\/\//.test(t||'');
for(const {a,s} of songs){
  // カバー「かもしれない」候補（★曲名一致は証拠ではない。出典が取れるまで繋がない）
  const k=norm(s.title);
  if(k&&!s.originalRef){
    const older=(titleIdx.get(k)||[]).filter(x=>x.a.id!==a.id&&x.s.year&&s.year&&x.s.year<s.year);
    if(older.length){
      const linked=(s.bridgeRelated||[]).some(b=>older.some(o=>b.includes(o.a.id)&&b.includes(o.s.id)));
      if(!linked){const o=older.sort((x,y)=>x.s.year-y.s.year)[0];
        R.cover_candidate.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name} (${s.year})`,maybe:`${o.s.title} / ${o.a.name} (${o.s.year})`});}
    }
  }
  // 既に繋いでいるのに出典URLが無い
  const src=hasSrc(s.note)||hasSrc(s.memo);
  if(s.originalRef&&!src) R.linked_nosource.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name}`,kind:'originalRef',to:`${s.originalRef.artistId}:${s.originalRef.songId}`});
  if((s.usedSongs||[]).length&&!src) R.linked_nosource.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name}`,kind:'usedSongs',n:s.usedSongs.length});
  if((s.famousUses||[]).length&&!src) R.linked_nosource.push({page:`${a.id}:${s.id}`,pageTitle:`${s.title} / ${a.name}`,kind:'famousUses',n:s.famousUses.length});
  // データの穴
  if(!s.youtubeId&&!(s.altYoutubeIds||[]).length) R.no_video.push({page:`${a.id}:${s.id}`,t:`${s.title} / ${a.name}`});
  if(!s.year) R.no_year.push({page:`${a.id}:${s.id}`,t:`${s.title} / ${a.name}`});
  const n=(s.note||'').trim();
  if(!n) R.no_note.push({page:`${a.id}:${s.id}`,t:`${s.title} / ${a.name}`});
  else{ if(/spotify/i.test(n)) R.note_spotify.push({page:`${a.id}:${s.id}`,text:n.slice(0,90)});
        if(n.length>20&&!/[。！？!?」）)…]$/.test(n)&&/[、,ぁ-んー]$/.test(n)) R.note_cut.push({page:`${a.id}:${s.id}`,tail:n.slice(-40)}); }
}
const NI=new Map();
for(const a of artists){const k=(a.name||'').toLowerCase().replace(/[^a-z0-9぀-ヿ一-龯]/g,''); if(!k)continue; (NI.get(k)||NI.set(k,[]).get(k)).push(a);}
for(const [,l] of NI) if(l.length>1) R.same_name.push({name:l[0].name,ids:l.map(x=>x.id)});
// 年が無いせいで「同じ時代」の門が効かないページ数
const noYearPages=new Set(R.no_year.map(x=>x.page)).size;
fs.writeFileSync('rest.json',JSON.stringify({...R,noYearPages}));
for(const k of Object.keys(R)) console.log(k,R[k].length);
console.log('曲総数',songs.length,'アーティスト',artists.length);
