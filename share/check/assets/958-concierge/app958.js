
import { Lipsync } from "https://cdn.jsdelivr.net/npm/wawa-lipsync@0.0.2/dist/wawa-lipsync.es.js";

const $=id=>document.getElementById(id);
const gkeyEl=$("gkey"), goEl=$("go"), stopEl=$("stop");
const stateEl=$("state"), logEl=$("log"), meterEl=$("meter");
const cardsEl=$("cards"), emptyEl=$("empty"), moreEl=$("more");
const YEN=157;

/* ══════════════ 値段（公式の表そのまま）══════════════
   gemini-3.8-live / gemini-3.1-flash-live-preview は同じ値段の欄に載っている。
     音声 入  $3.00 /100万トークン ＝ $0.005/分
     音声 出  $12.00/100万トークン ＝ $0.018/分
   このページは「マイクを開けていた秒数」と「返ってきた声の秒数」を実際に数えて、
   この単価を掛ける。見積もりではない。                                        */
const PRICE={ audioInPerMin:0.005, audioOutPerMin:0.018 };

const MODELS=[
  ["gemini-3.1-flash-live-preview","3.1 Flash Live"],
  ["gemini-3.8-live","3.8 Live（Google の既定）"]
];
const VOICES=["Puck","Charon","Kore","Fenrir","Aoede","Leda","Orus","Zephyr"];

function paintChips(box,list,storeKey,def){
  const cur=(()=>{ try{return localStorage.getItem(storeKey)||def;}catch(e){return def;} })();
  box.innerHTML="";
  list.forEach(item=>{
    const [v,t]=Array.isArray(item)?item:[item,item];
    const l=document.createElement("label");
    l.innerHTML=`<input type="radio" name="${storeKey}" value="${v}"${v===cur?" checked":""}><span>${t}</span>`;
    box.appendChild(l);
  });
  if(!box.querySelector("input:checked")) box.querySelector("input").checked=true;
  box.addEventListener("change",e=>{ try{localStorage.setItem(storeKey,e.target.value);}catch(_){} });
}
paintChips($("models"),MODELS,"tamago_gemini_model",MODELS[0][0]);
paintChips($("voices"),VOICES,"tamago_gemini_voice","Puck");
const pick=k=>(document.querySelector(`input[name=${k}]:checked`)||{}).value;
try{ const k=localStorage.getItem("tamago_gemini_key"); if(k) gkeyEl.value=k; }catch(_){}

/* ══════════════ 棚（947番と同じ在庫・同じ引き方）══════════════ */
const ASSET="assets/953-songs/";
const CAT={ head:null, joy:null, t:{}, a:{}, loading:null,
  async load(){
    if(this.head) return;
    if(this.loading) return this.loading;
    this.loading=Promise.all([
      fetch(ASSET+"head.json").then(r=>r.json()),
      fetch(ASSET+"joy.json").then(r=>r.ok?r.json():{cards:[],kind:{}}).catch(()=>({cards:[],kind:{}}))
    ]).then(([h,j])=>{ this.head=h; this.joy=j; });
    return this.loading;
  },
  async title(n){ if(!this.t[n]) this.t[n]=fetch(ASSET+"t/"+n+".json").then(r=>r.ok?r.json():[]).catch(()=>[]);
                  return this.t[n]; },
  async byArtist(n){ if(!this.a[n]) this.a[n]=fetch(ASSET+"a/"+n+".json").then(r=>r.ok?r.json():[]).catch(()=>[]);
                  return this.a[n]; }
};
const norm=s=>String(s).normalize("NFKC").toLowerCase()
  .replace(/[\s'’`\-_.,!?/()（）「」『』・:;"]+/g," ").trim();
const bucketOf=pre=>(pre.charCodeAt(0)*131+(pre.length>1?pre.charCodeAt(1):0))%(CAT.head?CAT.head.nb:128);
function prefixes(s){ const o=new Set(); for(const w of norm(s).split(" ")) if(w) o.add(w.slice(0,2)); return [...o]; }
function tidy(title){
  let p=0;
  if(title.length>45) p-=60; else if(title.length>30) p-=20;
  if(/[|｜]/.test(title)) p-=50;
  if(/[【】]/.test(title)) p-=25;
  if(/[☀-⟿✨🎵🔥]/u.test(title)) p-=30;
  return p;
}
const shown=new Set();
let pool=[], poolLabel="";

async function findSongs({artists=[], mood=[], song_title=""}){
  await CAT.load();
  const A=CAT.head.A;
  const an=artists.map(norm).filter(Boolean);
  const mo=mood.map(norm).filter(x=>x.length>=2);
  const artScore=new Map();
  A.forEach((a,i)=>{
    const name=norm(a.n);
    const alias=(a.al||[]).map(norm);
    const about=norm([(a.ab||""),(a.g||[]).join(" "),(a.e||[]).join(" ")].join(" "));
    let sc=0;
    for(const q of an){
      if(name===q) sc+=120;
      else if(q.length>=4 && name.includes(q)) sc+=70;
      else if(alias.some(x=>x===q)) sc+=70;
    }
    for(const q of mo){ if(about.includes(q)) sc+=25; }
    if(sc) artScore.set(i,sc);
  });
  const out=[], seen=new Set();
  const push=(row,sc)=>{
    const k=row[0]+"/"+row[1];
    if(seen.has(k)||shown.has(k)) return;
    seen.add(k);
    out.push({ai:row[0],sid:row[1],title:row[2],year:row[3]||0,yt:row[4]||"",
      sc:sc+tidy(row[2])+(row[3]?10:0)+((row[5]===1)?45:0)+Math.random()*8});
  };
  if(artScore.size){
    const top=[...artScore.entries()].sort((a,b)=>b[1]-a[1]).slice(0,20);
    const keep=new Map(top);
    const nums=[...new Set(top.map(([i])=>i%CAT.head.nb))].slice(0,24);
    const packs=await Promise.all(nums.map(n=>CAT.byArtist(n)));
    for(const rows of packs) for(const row of rows){
      const sc=keep.get(row[0]); if(sc) push(row,sc);
    }
  }
  const st=norm(song_title);
  if(st){
    const nums=[...new Set(prefixes(st).map(bucketOf))].slice(0,4);
    const packs=await Promise.all(nums.map(n=>CAT.title(n)));
    for(const rows of packs) for(const row of rows){
      const t=norm(row[2]);
      let sc=0;
      if(t===st) sc=200; else if(t.includes(st)) sc=120; else if(st.includes(t)&&t.length>=3) sc=90;
      if(sc) push(row,sc+(artScore.get(row[0])||0));
    }
  }
  out.sort((x,y)=>y.sc-x.sc);
  return spread(out);
}
function findJoy(mood, categories){
  if(!CAT.joy||!CAT.joy.cards.length) return [];
  const mo=(mood||[]).map(norm).filter(x=>x.length>=2);
  const want=(categories||[]).filter(k=>k&&k!=="music");
  const out=[];
  for(const c of CAT.joy.cards){
    if(c.k==="music") continue;
    if(want.length && !want.includes(c.k)) continue;
    const hay=norm((c.t||"")+" "+(c.w||""));
    let sc=8;
    for(const q of mo) if(hay.includes(q)) sc+=30;
    out.push(Object.assign(joyCard(c),{sc:sc+Math.random()*10}));
  }
  out.sort((a,b)=>b.sc-a.sc);
  return out;
}
function spread(list){
  const byA=new Map();
  for(const s of list){ if(!byA.has(s.ai)) byA.set(s.ai,[]); byA.get(s.ai).push(s); }
  const order=[...byA.keys()].sort((a,b)=>byA.get(b)[0].sc-byA.get(a)[0].sc);
  const out=[]; let left=true;
  while(left){
    left=false;
    for(const ai of order){ const q=byA.get(ai); if(q.length){ out.push(q.shift()); left=true; } }
  }
  return out;
}
const artistName=s=>CAT.head.A[s.ai].n;
const cardUrl=s=>CAT.head.base+"?artist="+encodeURIComponent(CAT.head.A[s.ai].i)
                 +"&song="+encodeURIComponent(s.sid);
const songCard=s=>({kind:"music",title:s.title,
  sub:artistName(s)+(s.year?("　"+s.year+"年"):""),
  thumb:"https://i.ytimg.com/vi/"+s.yt+"/mqdefault.jpg", yt:s.yt, url:cardUrl(s),
  key:"m:"+s.ai+"/"+s.sid});
const ytOf=u=>{ const m=/\/vi\/([A-Za-z0-9_-]{6,})\//.exec(u||""); return m?m[1]:""; };
const joyCard=c=>({kind:c.k,title:c.t,sub:c.w||"",thumb:c.i,yt:ytOf(c.i),
  url:(CAT.joy.base||"")+c.u, key:"j:"+c.u});
const kindJa=k=>((CAT.joy&&CAT.joy.kind&&CAT.joy.kind[k])||{}).ja||"";

/* ══════════════ その場の再生窓 ══════════════ */
const playerEl=$("player"), frameEl=$("frame");
let playing=null;
function openPlayer(c){
  playing=c; frameEl.innerHTML="";
  const f=document.createElement("iframe");
  f.allow="autoplay; encrypted-media; picture-in-picture";
  f.allowFullscreen=true; f.referrerPolicy="strict-origin-when-cross-origin";
  f.src="https://www.youtube-nocookie.com/embed/"+encodeURIComponent(c.yt)+"?autoplay=1&rel=0&playsinline=1";
  frameEl.appendChild(f);
  $("pTitle").textContent=c.title;
  $("pArtist").textContent=c.sub;
  playerEl.classList.add("on");
  playerEl.scrollIntoView({behavior:"smooth",block:"nearest"});
  setMic(false);
  setState("聴いています（話すときは『止めて案内人と話す』）");
}
function closePlayer(back){
  frameEl.innerHTML=""; playerEl.classList.remove("on"); playing=null;
  if(back!==false){ setMic(true); setState(live()?"聞いています":"やめました"); }
}
$("pBig").addEventListener("click",()=>{ if(playing) window.open(playing.url,"_blank","noopener"); });
$("pTalk").addEventListener("click",()=>closePlayer(true));
$("pClose").addEventListener("click",()=>closePlayer(true));

function drawCards(list){
  if(window.Seihon&&Seihon.drawCards){ Seihon.drawCards(list,(c)=>{ c.yt?openPlayer(c):window.open(c.url,"_blank","noopener"); }); emptyEl.style.display="none"; return; }
  cardsEl.innerHTML="";
  if(!list.length){ emptyEl.style.display="block"; return; }
  emptyEl.style.display="none";
  for(const c of list){
    const b=document.createElement("button"); b.className="card k-"+c.kind; b.type="button";
    const img=document.createElement("img"); img.className="thumb"; img.loading="lazy"; img.alt="";
    img.src=c.thumb; img.onerror=()=>{img.style.visibility="hidden"};
    const body=document.createElement("div"); body.className="body";
    const ja=kindJa(c.kind);
    if(ja){ const tag=document.createElement("span"); tag.className="tag"; tag.textContent=ja;
            body.appendChild(tag); }
    const t=document.createElement("p"); t.className="t"; t.textContent=c.title;
    const ar=document.createElement("p"); ar.className="a"; ar.textContent=c.sub;
    const go=document.createElement("p"); go.className="go";
    go.textContent=c.yt?"▶ ここで聴く・見る":"→ ひらく";
    body.append(t,ar,go); b.append(img,body);
    b.addEventListener("click",()=>{ c.yt?openPlayer(c):window.open(c.url,"_blank","noopener"); });
    cardsEl.appendChild(b);
  }
}
let page=0;
function dealFour(){
  const take=[];
  while(take.length<4 && pool.length){
    const c=pool.shift();
    if(shown.has(c.key)) continue;
    shown.add(c.key); take.push(c);
  }
  if(take.length) page++;
  drawCards(take);
  moreEl.disabled = pool.length===0;
  $("trayTitle").textContent = take.length
    ? "— "+(poolLabel||"どうぞ")+"　"+page+"枚目 —"
    : "— この気分の棚は、ここで打ち止めです —";
  return take;
}
async function newSearch(args,label){
  page=0;
  await CAT.load();
  const music=(await findSongs(args)).map(songCard);
  const cats=args.categories||[];
  const onlyMusic = cats.length===1 && cats[0]==="music";
  const joy = onlyMusic ? [] : findJoy(args.mood||[], cats);
  if(joy.length && music.length){
    const mixed=[]; let mi=0, ji=0;
    while(mi<music.length || ji<joy.length){
      for(let k=0;k<3 && mi<music.length;k++) mixed.push(music[mi++]);
      if(ji<joy.length) mixed.push(joy[ji++]);
    }
    pool=mixed;
  } else pool = music.length? music : joy;
  poolLabel=label||"";
  return dealFour();
}
/* ★道具は1個だけ登録している（search_songs）。
   「ほかのを見せて」は画面側でめくる。案内人には知らせるだけで、道具は呼ばせない。 */
moreEl.addEventListener("click",()=>{
  const got=dealFour();
  tellModel(got.length
    ? "（画面の合図）お客さんが「ほかのを見せて」を押しました。次の4枚はもう画面に出し終えています："
      +got.map(c=>`「${c.title}」`).join("、")
      +"。道具は呼ばないこと。短く一言そえるだけにしてください。"
    : "（画面の合図）もう在庫がありません。道具は呼ばずに、正直に「この気分の棚はここまで」と伝えて、別の気分を聞いてください。");
});

/* ══════════════ 顔（多面体の卵・3Dメガネ・赤いボウタイ）══════════════ */
const face=Tamako.stand($("tamako"));

/* ══════════════ 口パク（wawa-lipsync・MIT）══════════════
   公式の使い方は connectAudio(<audio>) だが、ここで鳴らしている声は
   WebSocket から来る生のPCMで <audio> 要素が無い。そこで、
   wawa-lipsync が中に持っている AudioContext / analyser をそのまま
   このページの再生先として使う（＝公式と同じ結線を手で1回やる）。       */
const lip=new Lipsync({fftSize:2048,historySize:10});
const actx=lip.audioContext;
lip.analyser.connect(actx.destination);
face.attach(lip.analyser);
(function tick(){ lip.processAudio(); face.viseme(lip.viseme); requestAnimationFrame(tick); })();

/* ══════════════ 財布（1日100円で止まる栓）══════════════
   947番と同じ入れもの（同じ localStorage の鍵）を使う。
   だからこのページと947番で、今日の合計は合算される。            */
const SAIFU={
  capDefault:100,
  day(){ const d=new Date(Date.now()+9*3600e3); return d.toISOString().slice(0,10); },
  kDay(){ return "tamago_voice_yen_"+this.day(); },
  cap(){ try{ const v=parseFloat(localStorage.getItem("tamago_voice_cap_yen"));
              return (isFinite(v)&&v>0)?v:this.capDefault; }catch(_){ return this.capDefault; } },
  setCap(v){ try{ localStorage.setItem("tamago_voice_cap_yen",String(v)); }catch(_){} paintMeter(); },
  today(){ try{ const v=parseFloat(localStorage.getItem(this.kDay())); return isFinite(v)?v:0; }
           catch(_){ return 0; } },
  put(v){ try{ localStorage.setItem(this.kDay(),String(Math.max(0,v))); }catch(_){} },
  base:0, stopped:false,
  hajime(){ this.base=this.today(); this.stopped=false; },
  nokori(){ return this.cap()-this.today(); }
};
function saifuKire(){
  if(SAIFU.stopped) return;
  SAIFU.stopped=true;
  try{ closeAll(); }catch(_){}
  try{ closePlayer(false); }catch(_){}
  goEl.disabled=false;
  setState("今日のぶんは使い切りました");
  say("sys","今日の上限（"+SAIFU.cap().toFixed(0)+"円）に達したので切りました。"
    +"続けるなら下の「1日の上限」を上げてください。（Google側の上限とは別に、この画面で止めています）");
}

/* ══════════════ 実測メーター ══════════════ */
const USE={micSec:0,outSec:0,usd:0,apiIn:0,apiOut:0,apiTotal:0};
let startedAt=0, meterTimer=0;
function cost(){
  USE.usd = USE.micSec/60*PRICE.audioInPerMin + USE.outSec/60*PRICE.audioOutPerMin;
  return USE.usd;
}
function paintMeter(){
  const sec=startedAt?(Date.now()-startedAt)/1000:0;
  const yen=cost()*YEN;
  const perMin=sec>5?(yen/(sec/60)):0;
  if(startedAt) SAIFU.put(SAIFU.base+yen);
  const kyou=SAIFU.today(), cap=SAIFU.cap();
  const nokori=Math.max(0,cap-kyou);
  meterEl.innerHTML=`${Math.floor(sec/60)}分${String(Math.floor(sec%60)).padStart(2,"0")}秒 ／ `
    +`<b>${yen.toFixed(1)}円</b>`+(perMin?`（このペースで1分 約${perMin.toFixed(1)}円）`:"")
    +`<br>今日ここまで <b>${kyou.toFixed(1)}円</b> ／ 上限 ${cap.toFixed(0)}円`
    +`（あと ${nokori.toFixed(1)}円）`
    +`<br><span style="opacity:.7">実測（マイクを開けていた ${USE.micSec.toFixed(0)}秒 ＋ `
    +`返ってきた声 ${USE.outSec.toFixed(0)}秒）</span>`;
  if(startedAt && kyou>=cap) saifuKire();
  paintCostTable();
}
function paintCostTable(){
  const y=v=>v*YEN;
  const rows=[
    ["聞く（マイクを開けていた秒数）", USE.micSec.toFixed(1)+"秒", y(USE.micSec/60*PRICE.audioInPerMin)],
    ["喋る（返ってきた声の秒数）",     USE.outSec.toFixed(1)+"秒", y(USE.outSec/60*PRICE.audioOutPerMin)]
  ];
  let html=rows.map(([k,v,c])=>`<tr><td>${k}</td><td>${v}　${c.toFixed(2)}円</td></tr>`).join("")
    +`<tr><td><b>合計</b></td><td><b>$${USE.usd.toFixed(5)}（${(USE.usd*YEN).toFixed(2)}円）</b></td></tr>`;
  if(USE.apiTotal){
    html+=`<tr><td>Googleが返してきたトークン数（参考）</td><td>入 ${USE.apiIn.toLocaleString()}`
      +` ／ 出 ${USE.apiOut.toLocaleString()} ／ 計 ${USE.apiTotal.toLocaleString()}</td></tr>`;
  }
  $("costTable").innerHTML=html;
}

/* ══════════════ 案内人の仕込み ══════════════ */
const INSTRUCTIONS=[
  "あなたは「ごきげん補給所」の案内人、たまこ。日本語だけで、短く、やわらかく話す。1回の返事は2文まで。",
  "英語で話しかけられても日本語で答える。",
  "",
  "■ ここは音楽屋ではありません",
  "この店に置いてあるのは、音楽・動画・食べもの・動物・旅・踊り・ことば・笑い、ぜんぶ「ごきげんの種」です。",
  "『音楽しかない店』と思わせないこと。気分の相談には、音楽以外の札も混ぜて差し出す。",
  "お客さんが「音楽で」と言ったときだけ categories を [\"music\"] にする。",
  "",
  "■ 破ったら失格の約束",
  "曲名・アーティスト名を口に出してよいのは、道具 search_songs が返してきたものだけ。",
  "自分の記憶の曲名をそのまま言わない。棚に無いかもしれないから。",
  "",
  "■ search_songs の使い方（ここが一番大事）",
  "artists ＝ その気分に似合うと思う実在のアーティスト名を、あなたの知識から8〜15組。多いほどよい。",
  "mood    ＝ 気分や手ざわりの言葉（ジャズ、アシッドジャズ、80年代、ソウル、アンビエント等）。",
  "song_title ＝ お客さんが曲名を口に出したときだけ入れる。気分のときは空にする。",
  "",
  "★ 気分の言葉を artists に入れてはいけない。★ 気分のときに song_title を使ってはいけない。",
  "  曲名で探すと『うれしい』でタイトルにHappyが付いた曲ばかりになる。それは失敗。",
  "",
  "例：「うれしい気分」→ artists:[\"Stevie Wonder\",\"Earth, Wind & Fire\",\"Jamiroquai\",\"Pharrell Williams\",",
  "  \"Kool & The Gang\",\"久保田利伸\",\"山下達郎\",\"Bruno Mars\",\"The Jackson 5\",\"Chic\"], mood:[\"ソウル\",\"ファンク\",\"ディスコ\"]",
  "例：「泣きたい」→ artists:[\"中島みゆき\",\"Eva Cassidy\",\"Antonio Carlos Jobim\",\"Nina Simone\",\"小椋佳\",",
  "  \"Sam Cooke\",\"Otis Redding\",\"あがた森魚\"], mood:[\"バラード\",\"ソウル\"]",
  "",
  "「他は？」と言われたら、画面の下の『ほかのを見せて』を押してもらう。道具は呼び直さない。",
  "",
  "■ カードが出たあと",
  "4枚全部は読み上げない。1〜2枚だけ名前を出して短く一言。",
  "「押すとその場で鳴りますよ」と伝える。曲ページへ誘導しない（飛ぶかはお客さんが決める）。",
  "最初のひとことは「こんばんは。今日はどんな気分で来られました？」のように短く。"
].join("\n");

/* ══════════════ つなぐ ══════════════ */
let api=null, mic=null, mctx=null, msrc=null, mnode=null, micOn=true;
let outAt=0, sources=[], retried=false, gotSetup=false, stopping=false;
const live=()=>!!(api&&api.connected);
/* ★970：tsuzuki=true は「喋っている途中の続き」。新しい行を足さず、同じ行に文字を足す。 */
let akiLine=null, akiCls=null;
const say=(cls,txt,tsuzuki)=>{
  txt=(txt==null?"":String(txt));
  if(!txt.replace(/[\s　]/g,"")) return;                 /* 空なら行を作らない */
  if(window.Seihon&&Seihon.say){ return Seihon.say(cls,txt,tsuzuki); }
  if(tsuzuki&&akiLine&&akiCls===cls&&logEl.contains(akiLine)){
    const mae=akiLine.textContent||"";
    if(!(mae.slice(-txt.length)===txt)) akiLine.textContent=mae+txt;
    logEl.scrollTop=logEl.scrollHeight; return;
  }
  const d=document.createElement("div"); d.className="line "+cls;
  d.textContent=txt; logEl.appendChild(d); logEl.scrollTop=logEl.scrollHeight;
  akiLine=tsuzuki?d:null; akiCls=tsuzuki?cls:null;
};
/* 話し終わり。次の台詞は新しい行から。 */
const sayOwari=()=>{ akiLine=null; akiCls=null;
  if(window.Seihon&&Seihon.seal) Seihon.seal(); };
const setState=s=>{stateEl.textContent=s;};
function setMic(on){ micOn=on; if(mic) mic.getAudioTracks().forEach(t=>t.enabled=on); }
function tellModel(text){ if(live()) api.sendTextMessage(text); }

/* 使い捨ての入場券（ephemeral token）をもらう。
   公式：POST /v1beta/auth_tokens （x-goog-api-key に鍵）。既定で30分・1セッション。 */
async function mintToken(key){
  const now=Date.now();
  const r=await fetch("https://generativelanguage.googleapis.com/v1beta/auth_tokens",{
    method:"POST",
    headers:{"x-goog-api-key":key,"Content-Type":"application/json"},
    body:JSON.stringify({
      uses:1,
      expireTime:new Date(now+30*60*1000).toISOString(),
      newSessionExpireTime:new Date(now+60*1000).toISOString()
    })
  });
  const j=await r.json().catch(()=>({}));
  if(!r.ok||!j.name){
    throw new Error("入場券がもらえませんでした（"+r.status+"）"+
      ((j.error&&j.error.message)?"："+j.error.message:""));
  }
  return j.name;
}

const WS_V1ALPHA="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContentConstrained?access_token=";
const WS_V1BETA ="wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContentConstrained?access_token=";

async function connect(){
  if(SAIFU.nokori()<=0){
    say("sys","今日の上限（"+SAIFU.cap().toFixed(0)+"円）を使い切っています。"
      +"明日また使えます。今すぐ続けるなら下の「1日の上限」を上げてください。");
    setState("今日のぶんは使い切りました"); paintMeter(); return;
  }
  /* ★969：鍵は「共通の1本」から取る。欄が空でも、端末に入っていれば話せる。 */
  const KAGI=window.TamagoKagi;
  const key=(gkeyEl.value||"").trim() || (KAGI?KAGI.get():"");
  if(!key){
    /* 文句を2度並べない。鍵を入れる場所そのものを出す。 */
    if(KAGI){ KAGI.ask(); }
    else { say("sys","Geminiの鍵が空です（「・」を押して設定の中に入れてください）");
           $("settings").hidden=false; $("settings").open=true; }
    return;
  }
  try{ localStorage.setItem("tamago_gemini_key",key); }catch(_){}

  SAIFU.hajime();
  goEl.disabled=true; logEl.innerHTML=""; sayOwari();
  shown.clear(); pool=[]; page=0; drawCards([]); moreEl.disabled=true; closePlayer(false);
  USE.micSec=USE.outSec=USE.usd=USE.apiIn=USE.apiOut=USE.apiTotal=0;
  retried=false; stopping=false;
  // 音の箱は「押した」この瞬間に起こす（そうしないとブラウザが鳴らしてくれない）
  try{ await actx.resume(); }catch(_){}
  CAT.load().catch(()=>{});
  setState("つないでいます…"); startedAt=Date.now();
  clearInterval(meterTimer); meterTimer=setInterval(paintMeter,1000);
  try{ await open(WS_V1ALPHA, key); }
  catch(err){ say("sys","つながりませんでした → "+err.message);
    setState("失敗しました"); goEl.disabled=false; closeAll(); }
}

async function open(wsBase, key){
  const token=await mintToken(key);
  gotSetup=false;

  api=new GeminiLiveAPI(token, pick("tamago_gemini_model"));
  api.serviceUrl = wsBase + token;      // ★公式サンプルから変えたのはここだけ
  api.setSystemInstructions(INSTRUCTIONS);
  api.setResponseModalities(["AUDIO"]);
  api.setVoice(pick("tamago_gemini_voice"));
  api.setInputAudioTranscription(true);
  api.setOutputAudioTranscription(true);
  api.setEnableFunctionCalls(true);

  const f=new FunctionCallDefinition(
    "search_songs",
    "棚を実際に引く。ここが返した曲だけが口に出してよい曲。4枚のカードが画面に出て、押すとその場で鳴る。",
    { type:"object", properties:{
        artists:{type:"array",items:{type:"string"},
          description:"その気分に似合う実在のアーティスト名を8〜15組。ここが結果の質を決める。"},
        mood:{type:"array",items:{type:"string"},
          description:"気分・ジャンル・年代の言葉。曲名は入れない。"},
        song_title:{type:"string",
          description:"お客さんが曲名を口に出したときだけ。気分のときは空にする。"},
        categories:{type:"array",items:{type:"string"},
          description:"出す種類。music/food/travel/dance/joy から。省略すると音楽と音楽以外が混ざる。「音楽だけ」と言われたときだけ [\"music\"] にする。"},
        label:{type:"string",description:"この棚につける短い見出し。例：うれしい夜に"}
      } },
    ["artists"]
  );
  api.addFunction(f);

  api.onOpen=()=>{ setState("聞いています"); };
  api.onError=()=>{ say("sys","つなぎめでエラーが出ました。"); };
  api.onClose=async(ev)=>{
    // v1alpha で開かないときは、公式ドキュメントに載っている v1beta でもう一度だけ試す。
    if(!stopping && !gotSetup && !retried && wsBase===WS_V1ALPHA){
      retried=true;
      say("sys","つなぎ先を v1beta に替えてもう一度試します。");
      try{ await open(WS_V1BETA, key); return; }
      catch(e){ say("sys","そちらも駄目でした → "+e.message); }
    }
    if(startedAt){ setState("切れました"); goEl.disabled=false; }
  };
  api.onRawMessage=(m)=>{
    const u=m&&m.usageMetadata; if(!u) return;
    USE.apiIn   = Math.max(USE.apiIn,   u.promptTokenCount||0);
    USE.apiOut  = Math.max(USE.apiOut,  u.responseTokenCount||0);
    USE.apiTotal= Math.max(USE.apiTotal,u.totalTokenCount||0);
  };
  api.onReceiveResponse=onResponse;

  api.connect();
  await startMicPump();
}

async function onResponse(r){
  switch(r.type){
    case "SETUP COMPLETE":
      gotSetup=true; setState("聞いています");
      say("sys","つながりました。話しかけてください。");
      break;
    case "AUDIO": playPcm(r.data); break;
    /* ★970：切れ端は同じ行に足していく（1発言＝1行） */
    case "INPUT_TRANSCRIPTION":
      if(r.data.text) say("me",r.data.text,true); break;
    case "OUTPUT_TRANSCRIPTION":
      if(r.data.text) say("her",r.data.text,true); break;
    case "TURN COMPLETE": sayOwari(); break;        /* 話し終わり＝行を閉じる */
    case "INTERRUPTED": stopAudio(); sayOwari(); break;
    case "TOOL_CALL": await onToolCall(r.data); break;
  }
}

async function onToolCall(toolCall){
  const responses=[];
  for(const fc of (toolCall.functionCalls||[])){
    let payload;
    try{
      const a=fc.args||{};
      const got=await newSearch(
        {artists:a.artists||[],mood:a.mood||[],song_title:a.song_title||"",
         categories:a.categories||[]}, a.label||"");
      payload=got.length
        ? {ok:true,count:got.length,rest:pool.length,
           songs:got.map(c=>({title:c.title,by:c.sub,kind:c.kind})),
           note:"この曲だけが実在する。ここに無い曲名を口に出さないこと。カードは画面に出し終えた。押せばその場で鳴る。"}
        : {ok:false,count:0,rest:0,
           note:"棚に見つからなかった。artists にもっと多くのアーティスト名を入れて呼び直すこと。曲名を作らないこと。"};
      if(got.length) say("sys","棚から "+got.length+"枚："+got.map(s=>s.title).join(" / "));
    }catch(err){
      payload={ok:false,error:String(err&&err.message||err)};
      say("sys","棚を引けませんでした："+payload.error);
    }
    responses.push({ id:fc.id, name:fc.name, response:{ result:payload } });
  }
  if(responses.length) api.sendToolResponse(responses);
}

/* マイク。Live API は 16kHz・16bit・モノラルの生PCM。 */
async function startMicPump(){
  if(mnode) return;              // つなぎ直しのとき、マイクを二重に回さない（値段が倍になる）
  mic=await navigator.mediaDevices.getUserMedia(
    {audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
  mctx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:16000});
  if(mctx.state==="suspended") await mctx.resume();
  msrc=mctx.createMediaStreamSource(mic);
  mnode=mctx.createScriptProcessor(2048,1,1);
  mnode.onaudioprocess=ev=>{
    if(!live()||!micOn) return;
    const f=ev.inputBuffer.getChannelData(0);
    USE.micSec += f.length/mctx.sampleRate;      // ★ここが「聞く」の実測
    const buf=new ArrayBuffer(f.length*2), view=new DataView(buf);
    for(let i=0;i<f.length;i++){ const v=Math.max(-1,Math.min(1,f[i]));
      view.setInt16(i*2, v<0?v*0x8000:v*0x7FFF, true); }
    let bin=""; const b=new Uint8Array(buf);
    for(let i=0;i<b.length;i+=8192) bin+=String.fromCharCode.apply(null,b.subarray(i,i+8192));
    api.sendAudioMessage(btoa(bin));
  };
  msrc.connect(mnode); mnode.connect(mctx.destination);
}

/* 返ってきた声は 24kHz。鳴らす先は wawa-lipsync の analyser（＝そのまま口が動く）。 */
function playPcm(b64){
  if(actx.state==="suspended") actx.resume();
  const bin=atob(b64), n=bin.length>>1;
  const buf=actx.createBuffer(1,n,24000), ch=buf.getChannelData(0);
  for(let i=0;i<n;i++){ let v=(bin.charCodeAt(i*2+1)<<8)|bin.charCodeAt(i*2);
    if(v>=0x8000) v-=0x10000; ch[i]=v/32768; }
  const src=actx.createBufferSource(); src.buffer=buf;
  src.connect(lip.analyser);
  const now=actx.currentTime; if(outAt<now+0.06) outAt=now+0.06;
  src.start(outAt); outAt+=buf.duration;
  USE.outSec += buf.duration;                   // ★ここが「喋る」の実測
  sources.push(src);
  src.onended=()=>{ const i=sources.indexOf(src); if(i>=0) sources.splice(i,1); };
}
function stopAudio(){
  sources.forEach(s=>{ try{s.stop()}catch(_){} });
  sources=[]; outAt=0;
}
function closeAll(){
  stopping=true;
  try{ api&&api.disconnect(); }catch(_){}
  try{ mnode&&mnode.disconnect(); msrc&&msrc.disconnect(); }catch(_){}
  if(mic) mic.getTracks().forEach(t=>t.stop());
  stopAudio();
  api=null; mic=null; mnode=null; msrc=null;
  clearInterval(meterTimer);
  paintMeter();
  startedAt=0;
}

/* 1日の上限を変える口。客前に出す（怖いのは「いくらまで」が見えないこと）。 */
(function(){
  try{
    const box=document.createElement("p");
    box.style.cssText="text-align:center;color:#9d947f;font-size:.74rem;margin:6px 0 0";
    box.innerHTML='1日の上限 <input id="capIn" type="number" min="10" step="10" '
      +'style="width:5.5em;background:#1a1712;color:#e8e2d4;border:1px solid #3a352c;'
      +'border-radius:6px;padding:2px 4px;text-align:right"> 円 '
      +'<button id="capSet" style="background:#2a2622;color:#e8e2d4;border:1px solid #3a352c;'
      +'border-radius:6px;padding:2px 8px;cursor:pointer;flex:0 0 auto;font-size:.74rem">決める</button>';
    meterEl.parentNode.insertBefore(box,meterEl.nextSibling);
    const inp=box.querySelector("#capIn"); inp.value=SAIFU.cap();
    box.querySelector("#capSet").addEventListener("click",()=>{
      const v=parseFloat(inp.value); if(isFinite(v)&&v>0) SAIFU.setCap(v);
    });
  }catch(_){}
  paintMeter();
})();

$("devLink").addEventListener("click",e=>{ e.preventDefault();
  const d=$("settings"); d.hidden=false; d.open=true; });
goEl.addEventListener("click",connect);
stopEl.addEventListener("click",()=>{ closeAll(); closePlayer(false);
  setState("やめました"); goEl.disabled=false; });
