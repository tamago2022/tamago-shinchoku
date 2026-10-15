/* 1024番の確かめ：**ページに実際に書いてある関数をそのまま切り出して**、棚の本物のデータで回す。
   ブラウザを開かない・AIを呼ばない＝0円。 */
import fs from "fs";
import path from "path";
import {fileURLToPath} from "url";
const REPO=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const P=path.join(REPO,"share/check/431-seihon.html");
const A_=path.join(REPO,"share/check/assets/953-songs")+"/";
const src=fs.readFileSync(P,"utf8");
const take=(name)=>{                       // function 名 { ... } を対応する } まで切る
  const i=src.indexOf("function "+name+"(");
  if(i<0) throw new Error("見つからない: "+name);
  let j=src.indexOf("{",i), d=0;
  for(let k=j;k<src.length;k++){ const c=src[k];
    if(c==="{")d++; else if(c==="}"){d--; if(!d) return src.slice(i,k+1);} }
  throw new Error("閉じない: "+name);
};
const names=["kyokuJanai","usuiEra","usuiKuni","mezurashi","boukenTen","nyukaHi","nyukaDoor","saikinList","mezuraList","kuniOf","kuniDoor"];
const head=JSON.parse(fs.readFileSync(A_+"head.json"));
const reg =JSON.parse(fs.readFileSync(A_+"region.json"));
const ny  =JSON.parse(fs.readFileSync(A_+"nyuka.json"));
const CAT={head,reg,ny};
let ERAN={}; for(const a of head.A) for(const e of (a.e||[])) ERAN[e]=(ERAN[e]||0)+1;
let KUNIN={},KUNIWAKARU=0;
for(const a of head.A){ const c=reg.r[a.i]; if(c){ KUNIN[c]=(KUNIN[c]||0)+1; KUNIWAKARU++; } }
const REGION_JA=eval("("+/const REGION_JA=(\{[\s\S]*?\n\});/.exec(src)[1]+")");
const KUNI_JA=Object.assign({},REGION_JA,eval("("+/const KUNI_JA=Object.assign\(\{\},REGION_JA,(\{[\s\S]*?\n\})\);/.exec(src)[1]+")"));
const NAMUSIC_AB=/俳優|女優|声優|お笑い|芸人|漫才|コンビ。|落語|タレント|監督。|監督、|年公開|テレビ番組|バラエティ|ドラマ作品|アナウンサー/;
const fn=new Function("CAT","ERAN","KUNIN","KUNIWAKARU","REGION_JA","KUNI_JA","NAMUSIC_AB",
  names.map(take).join("\n")+"\nreturn {"+names.join(",")+"};");
const F=fn(CAT,ERAN,KUNIN,KUNIWAKARU,REGION_JA,KUNI_JA,NAMUSIC_AB);

console.log("窓:",ny.mado,"日 ／ 境:",ny.sakai,"／ 窓の中の人:",Object.keys(ny.a).length,"組");
const sk=F.saikinList();
console.log("\n【案内人に渡す『最近入荷したなかでも面白いもの』】", sk.length+"組");
sk.forEach(s=>console.log("  "+s));
console.log("\n【札に刷る1行（最近入荷ぶん）】");
let n=0;
for(const a of head.A){ const d=F.nyukaDoor(a); if(d){ if(n<6) console.log("  "+a.n+" → 「"+d+"」"); n++; } }
console.log("  …札に「入ったばかり」が出る人:",n,"組");
console.log("\n【念のため】窓の外の人に日付が出ないこと:");
const soto=head.A.filter(a=>!ny.a[a.i]).slice(0,3);
soto.forEach(a=>console.log("  "+a.n+" → 「"+F.nyukaDoor(a)+"」(空なら正しい)"));
console.log("\n【1023からの持ち物が壊れていないか】mezuraList:",F.mezuraList().length,"組");
