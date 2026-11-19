/* 431番 — Issue #431 の正本HTML/CSSに、947番で動いている案内人（GPT Live・安い版既定・
 * 1日100円の栓・口が動く・4件おすすめ・その場で鳴る・大きい画面で見ますか・search_songs）を
 * そのまま移植したもの。中身は947番の写し。
 * 画面への出し方だけ Seihon（bridge.js）に預け、正本のDOMを一切作り替えない。 */
(function(){
  const $=id=>document.getElementById(id);
  const keyEl=$("key"), xkeyEl=$("xkey"), goEl=$("go"), stopEl=$("stop");
  const stateEl=$("state"), logEl=$("log"), meterEl=$("meter");
  const cardsEl=$("cards"), emptyEl=$("empty"), moreEl=$("more");
  const lagEl=$("lag");
  const YEN=157;
  // 正本§8：鍵・モデル・声の生UIは客前に出さない。?dev=1 のときだけ開く。
  try{
    const dev=new URLSearchParams(location.search).get("dev")==="1";
    const had=localStorage.getItem("tamago_openai_key")||localStorage.getItem("tamago_xai_key");
    if(dev || !had) $("settings").hidden=false;
  }catch(_){ $("settings").hidden=false; }
  try{ const k=localStorage.getItem("tamago_openai_key"); if(k) keyEl.value=k; }catch(e){}
  try{ const k=localStorage.getItem("tamago_xai_key");    if(k) xkeyEl.value=k; }catch(e){}

  /* ── 値段表（2026-09-19 公式より書き写し。1Mトークンあたりのドル） ── */
  /* 安い版の中身と値段（2026-09-19 公式より書き写し）
     聞く gpt-4o-mini-transcribe $0.003/分 ／ 考える gpt-4o-mini 入$0.15・出$0.60（100万トークン）
     喋る gpt-4o-mini-tts 文字入$0.60（100万トークン）＋出た声 約$0.015/分            */
  const SPLIT={ stt:"gpt-4o-mini-transcribe", chat:"gpt-4o-mini", tts:"gpt-4o-mini-tts",
    price:{ sttPerMin:0.003, chatIn:0.15, chatOut:0.60, ttsTextIn:0.60, ttsPerMin:0.015 } };

  const ENGINES={
    split:{ label:"安い版（聞く・考える・喋るを分ける）", vendor:"split",
      short:"安い版", hint:"約2〜3円/分・すこし遅い" },
    mini:{ label:"速い版（リアルタイム mini）", vendor:"openai",
      short:"速い版", hint:"約15円/分・返事が即",
      models:["gpt-realtime-2.1-mini","gpt-realtime-mini"],
      price:{audioIn:10,audioCached:0.30,audioOut:20,textIn:0.60,textCached:0.06,textOut:2.40}},
    full:{ label:"リアルタイム本式（いちばん高い）", vendor:"openai",
      models:["gpt-realtime-2.1","gpt-realtime"],
      price:{audioIn:32,audioCached:0.40,audioOut:64,textIn:4.00,textCached:0.40,textOut:24.00}},
    grok:{ label:"xAI Grok（定額）", vendor:"xai",
      models:["grok-voice-latest"], perMin:0.08}
  };
  let engineKey=(()=>{ try{return localStorage.getItem("tamago_engine")||"split";}catch(e){return "split";} })();
  if(!ENGINES[engineKey]) engineKey="split";
  const isSplit=()=>ENGINES[engineKey].vendor==="split";

  /* 表に出す切り替え（安い版／速い版）。細かい4択は設定の中のまま残す。 */
  function paintMode(){
    const box=$("mode"); box.innerHTML="";
    [["split","安い版","2〜3円/分・少し待つ"],["mini","速い版","約15円/分・即返事"]].forEach(([k,t,h])=>{
      const l=document.createElement("label");
      if(k===engineKey) l.className="on";
      l.innerHTML=`<input type="radio" name="mode" value="${k}"${k===engineKey?" checked":""}>`
                 +`${t}<small>${h}</small>`;
      l.querySelector("input").addEventListener("change",()=>setEngine(k));
      box.appendChild(l);
    });
  }
  function setEngine(k){
    if(!ENGINES[k]) return;
    engineKey=k; try{localStorage.setItem("tamago_engine",k);}catch(_){}
    const r=document.querySelector(`#engines input[value="${k}"]`); if(r) r.checked=true;
    paintMode(); paintVoices(); showPriceNote(); paintMeter(); paintCostTable();
    if(!isSplit()) $("lag").textContent=""; else paintLag();
  }

  const eBox=$("engines");
  Object.entries(ENGINES).forEach(([k,e])=>{
    const l=document.createElement("label");
    l.innerHTML=`<input type="radio" name="eng" value="${k}"${k===engineKey?" checked":""}><span>${e.label}</span>`;
    l.querySelector("input").addEventListener("change",()=>setEngine(k));
    eBox.appendChild(l);
  });
  function showPriceNote(){
    const e=ENGINES[engineKey];
    $("engineNote").innerHTML = e.vendor==="split"
      ? `音声を文字にする $${SPLIT.price.sttPerMin}/分・考える $${SPLIT.price.chatIn}／$${SPLIT.price.chatOut}（100万トークン）・
         声にする 約$${SPLIT.price.ttsPerMin}/分（出た声の長さぶん）。<b>黙っている時間はタダ</b>。`
      : e.perMin
      ? `1分あたり $${e.perMin}（約${(e.perMin*YEN).toFixed(0)}円）の定額。つないだ時間ぶんだけ。`
      : `トークン課金。音声 入 $${e.price.audioIn}／出 $${e.price.audioOut}（100万トークンあたり）。
         分ではなく<b>喋った量</b>で決まります。`;
  }
  paintMode();
  showPriceNote();

  /* ══════════════ 棚 ══════════════ */
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
  let pool=[], poolLabel="", lastArgs=null;

  /* ★ ここが肝：
     ・気分の言葉（mood）は **アーティストの説明文だけ** に当てる。曲名には当てない。
       （曲名に当てると「うれしい」で Happy だらけになる。それを止めるための分離）
     ・曲名で探すのは、お客さんが曲名を言ったとき（song_title）だけ。            */
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
        // ゆるく当てすぎると「Nick Drake」で Drake が出る。名前は厳しく見る。
        if(name===q) sc+=120;
        else if(q.length>=4 && name.includes(q)) sc+=70;
        else if(alias.some(x=>x===q)) sc+=70;
      }
      for(const q of mo){                    // 気分は「人の説明」にだけ当てる
        if(about.includes(q)) sc+=25;
      }
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

    // ① 当たった人の曲を、丸ごと（＝「他は」で何度でもめくれる深さ）
    if(artScore.size){
      const top=[...artScore.entries()].sort((a,b)=>b[1]-a[1]).slice(0,20);
      const keep=new Map(top);
      const nums=[...new Set(top.map(([i])=>i%CAT.head.nb))].slice(0,24);
      const packs=await Promise.all(nums.map(n=>CAT.byArtist(n)));
      for(const rows of packs) for(const row of rows){
        const sc=keep.get(row[0]); if(sc) push(row,sc);
      }
    }
    // ② 曲名を言われたときだけ、曲名の棚を引く
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

  /* 音楽以外の棚を、気分の言葉で引く。
     正本§3：一度に4件、そこに音楽以外も混ざって見えること。 */
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

  /* 同じ人の曲で4枚が埋まらないように、1曲ずつ持ち回りにする。
     （そうしないと「うれしい」で Earth, Wind & Fire だけが4枚出る） */
  function spread(list){
    const byA=new Map();
    for(const s of list){ if(!byA.has(s.ai)) byA.set(s.ai,[]); byA.get(s.ai).push(s); }
    const order=[...byA.keys()].sort((a,b)=>byA.get(b)[0].sc-byA.get(a)[0].sc);
    const out=[];
    let left=true;
    while(left){
      left=false;
      for(const ai of order){
        const q=byA.get(ai);
        if(q.length){ out.push(q.shift()); left=true; }
      }
    }
    return out;
  }

  const artistName=s=>CAT.head.A[s.ai].n;
  const cardUrl=s=>CAT.head.base+"?artist="+encodeURIComponent(CAT.head.A[s.ai].i)
                   +"&song="+encodeURIComponent(s.sid);

  // 音楽の曲を「札」の形に
  const songCard=s=>({kind:"music",title:s.title,
    sub:artistName(s)+(s.year?("　"+s.year+"年"):""),
    thumb:"https://i.ytimg.com/vi/"+s.yt+"/mqdefault.jpg", yt:s.yt, url:cardUrl(s),
    key:"m:"+s.ai+"/"+s.sid});

  // 音楽以外の札（食・旅・踊り・ことば…）。正本§3「音楽しかない」と誤認させない
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
    tellModel("お客さんが「"+c.title+"」をこの画面で再生しました。いまは黙って待つこと。",true);
  }
  function closePlayer(back){
    frameEl.innerHTML=""; playerEl.classList.remove("on"); playing=null;
    if(back!==false){ setMic(true); setState(live()?"聞いています":"やめました"); }
  }
  $("pBig").addEventListener("click",()=>{ if(playing) window.open(playing.url,"_blank","noopener"); });
  $("pTalk").addEventListener("click",()=>closePlayer(true));
  $("pClose").addEventListener("click",()=>closePlayer(true));

  function drawCards(list){
    // ★正本(Issue #431)の .rec-card をひな形として複製するだけ。作り直さない。
    if(window.Seihon&&Seihon.drawCards){
      Seihon.drawCards(list,(c)=>{ c.yt?openPlayer(c):window.open(c.url,"_blank","noopener"); });
      return;
    }
    cardsEl.innerHTML="";
    if(!list.length){ emptyEl.style.display="block"; return; }
    emptyEl.style.display="none";
  }

  let page=0, lastDealAt=0, lastDealt=[];
  function dealFour(){
    const take=[];
    while(take.length<4 && pool.length){
      const c=pool.shift();
      if(shown.has(c.key)) continue;
      shown.add(c.key); take.push(c);
    }
    if(take.length) page++;
    lastDealAt=Date.now(); lastDealt=take;
    drawCards(take);
    moreEl.disabled = pool.length===0;
    $("trayTitle").textContent = take.length
      ? "— "+(poolLabel||"どうぞ")+"　"+page+"枚目 —"
      : "— この気分の棚は、ここで打ち止めです —";
    return take;
  }
  async function newSearch(args,label){
    lastArgs=args; page=0;
    await CAT.load();
    const music=(await findSongs(args)).map(songCard);
    const cats=args.categories||[];
    const onlyMusic = cats.length===1 && cats[0]==="music";
    const joy = onlyMusic ? [] : findJoy(args.mood||[], cats);
    // 正本§3：音楽しかない、と誤認させない。4枚のうち1〜2枚は音楽以外を入れる。
    if(joy.length && music.length){
      const mixed=[];
      let mi=0, ji=0;
      while(mi<music.length || ji<joy.length){
        for(let k=0;k<3 && mi<music.length;k++) mixed.push(music[mi++]);
        if(ji<joy.length) mixed.push(joy[ji++]);
      }
      pool=mixed;
    } else pool = music.length? music : joy;
    poolLabel=label||"";
    return dealFour();
  }
  moreEl.addEventListener("click",()=>{
    const got=dealFour();
    // ★道具を呼ばせない。ボタン側でもう4枚めくり終えている。呼ばせるとさらに4枚飛ぶ。
    tellModel(got.length
      ? "お客さんが「ほかのを見せて」を押しました。次の4枚はもう画面に出し終えています："
        +got.map(c=>`「${c.title}」`).join("、")
        +"。more_songs も search_songs も呼ばないこと。短く一言そえるだけにしてください。"
      : "もう在庫がありません。道具は呼ばずに、正直に「この気分の棚はここまで」と伝えて、別の気分を聞いてください。");
  });

  /* ══════════════ 顔 ══════════════ */
  const cv=$("face"), cx=cv.getContext("2d");
  let level=0,bright=0,speaking=false,blink=0,nextBlink=60,t=0,analyser=null;
  function draw(){
    const W=cv.width,H=cv.height; t++; cx.clearRect(0,0,W,H);
    const br=Math.sin(t/55)*6, cxp=W/2, cyp=H/2+br, rw=W*0.30, rh=H*0.36;
    cx.save(); cx.globalAlpha=.35; cx.fillStyle="#000";
    cx.beginPath(); cx.ellipse(cxp,cyp+rh+26,rw*0.8,16,0,0,7); cx.fill(); cx.restore();
    const g=cx.createLinearGradient(0,cyp-rh,0,cyp+rh);
    g.addColorStop(0,"#fdf7ea"); g.addColorStop(1,"#e8d9bd"); cx.fillStyle=g;
    cx.beginPath(); cx.moveTo(cxp,cyp-rh);
    cx.bezierCurveTo(cxp+rw*1.05,cyp-rh*0.75,cxp+rw,cyp+rh*0.62,cxp,cyp+rh);
    cx.bezierCurveTo(cxp-rw,cyp+rh*0.62,cxp-rw*1.05,cyp-rh*0.75,cxp,cyp-rh);
    cx.fill(); cx.strokeStyle="#cdbb99"; cx.lineWidth=3; cx.stroke();
    cx.fillStyle="rgba(214,120,102,.28)";
    cx.beginPath(); cx.ellipse(cxp-rw*0.52,cyp+rh*0.16,26,15,0,0,7); cx.fill();
    cx.beginPath(); cx.ellipse(cxp+rw*0.52,cyp+rh*0.16,26,15,0,0,7); cx.fill();
    if(--nextBlink<0){ blink=7; nextBlink=90+Math.random()*160; }
    const open=blink>0?(blink--,0.12):1;
    cx.fillStyle="#2a2622"; const ey=cyp-rh*0.12, ex=rw*0.36, er=15;
    [-1,1].forEach(s=>{ cx.beginPath(); cx.ellipse(cxp+s*ex,ey,er,er*open+1.5,0,0,7); cx.fill();
      if(open>0.5){ cx.fillStyle="#fff"; cx.beginPath(); cx.ellipse(cxp+s*ex-5,ey-5,4.5,4.5,0,0,7);
        cx.fill(); cx.fillStyle="#2a2622"; } });
    cx.strokeStyle="#7a6a52"; cx.lineWidth=5; cx.lineCap="round";
    const bry=ey-30-(speaking?6:0);
    [-1,1].forEach(s=>{ cx.beginPath(); cx.moveTo(cxp+s*ex-16,bry+4);
      cx.quadraticCurveTo(cxp+s*ex,bry-4,cxp+s*ex+16,bry+4); cx.stroke(); });
    const my=cyp+rh*0.34, openH=6+level*74, wideW=34+(1-bright)*16+level*26;
    cx.fillStyle="#7d3b34"; cx.beginPath();
    cx.ellipse(cxp,my,wideW*(0.55+bright*0.5),openH,0,0,7); cx.fill();
    cx.strokeStyle="#5e2c26"; cx.lineWidth=3; cx.stroke();
    if(openH>22){ cx.fillStyle="#d1736c"; cx.beginPath();
      cx.ellipse(cxp,my+openH*0.42,wideW*0.42,openH*0.3,0,0,7); cx.fill(); }
    cx.fillStyle="#c4483a"; const by=cyp+rh*0.82;
    cx.beginPath(); cx.moveTo(cxp,by); cx.lineTo(cxp-40,by-20); cx.lineTo(cxp-40,by+20); cx.closePath(); cx.fill();
    cx.beginPath(); cx.moveTo(cxp,by); cx.lineTo(cxp+40,by-20); cx.lineTo(cxp+40,by+20); cx.closePath(); cx.fill();
    cx.beginPath(); cx.ellipse(cxp,by,9,11,0,0,7); cx.fill();
    if(analyser){
      const n=analyser.frequencyBinCount, d=new Uint8Array(n);
      analyser.getByteFrequencyData(d);
      let lo=0,hi=0; const cut=Math.floor(n*0.12);
      for(let i=0;i<cut;i++) lo+=d[i];
      for(let i=cut;i<Math.floor(n*0.5);i++) hi+=d[i];
      lo/=cut*255; hi/=(Math.floor(n*0.5)-cut)*255;
      level+=(Math.min(1,lo*1.4+hi*1.0)-level)*0.35;
      if(level<0.03) level*=0.6;
      bright+=(hi/(lo+hi+0.0001)-bright)*0.2;
    } else level*=0.85;
    requestAnimationFrame(draw);
  }
  draw();

  /* ══════════════ 声 ══════════════ */
  const OA_VOICES=["marin","cedar","alloy","ash","ballad","coral","echo","sage","shimmer","verse"];
  const XA_VOICES=["iris","eve","carina","luna","ara","celeste","aurora","liora"];
  // 音声合成(gpt-4o-mini-tts)で使える声。日本語が素直な順に並べてある。
  const TTS_VOICES=["coral","sage","shimmer","alloy","ballad","nova","fable","echo","ash","verse"];
  let wanted=""; try{ wanted=new URLSearchParams(location.search).get("voice")||""; }catch(e){}
  function paintVoices(){
    const v=ENGINES[engineKey].vendor;
    const list = v==="xai"?XA_VOICES : v==="split"?TTS_VOICES : OA_VOICES;
    const box=$("voices"); box.innerHTML="";
    list.forEach((v,i)=>{
      const on=(wanted&&v===wanted)||(!wanted&&i===0);
      const l=document.createElement("label");
      l.innerHTML=`<input type="radio" name="v" value="${v}"${on?" checked":""}><span>${v}</span>`;
      box.appendChild(l);
    });
    if(!box.querySelector("input:checked")) box.querySelector("input").checked=true;
  }
  paintVoices();
  const currentVoice=()=>(document.querySelector('input[name=v]:checked')||{}).value
                         ||(ENGINES[engineKey].vendor==="xai"?"iris"
                           :ENGINES[engineKey].vendor==="split"?"coral":"marin");

  /* ══════════════ 案内人の仕込み ══════════════ */
  const INSTRUCTIONS=[
    "あなたは「ごきげん補給所」の案内人、アイリス。日本語で、短く、やわらかく。1回の返事は2文まで。",
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
    "■ search_songs の使い分け（ここが一番大事）",
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
    "「他は？」と言われたら more_songs を呼ぶ。search_songs を呼び直さない。",
    "在庫が尽きたと返ってきたら、正直に「この気分の棚はここまで」と言って別の気分を聞く。",
    "",
    "■ カードが出たあと",
    "4枚全部は読み上げない。1〜2枚だけ名前を出して短く一言。",
    "「押すとその場で鳴りますよ」と伝える。曲ページへ誘導しない（飛ぶかはお客さんが決める）。",
    "最初のひとことは「こんばんは。今日はどんな気分で来られました？」のように短く。"
  ].join("\n");

  const TOOLS=[
    { type:"function", name:"search_songs",
      description:"棚を実際に引く。ここが返した曲だけが口に出してよい曲。4枚のカードが画面に出て、押すとその場で鳴る。",
      parameters:{ type:"object", properties:{
        artists:{type:"array",items:{type:"string"},
          description:"その気分に似合う実在のアーティスト名を8〜15組。ここが結果の質を決める。"},
        mood:{type:"array",items:{type:"string"},
          description:"気分・ジャンル・年代の言葉。曲名は入れない。"},
        song_title:{type:"string",
          description:"お客さんが曲名を口に出したときだけ。気分のときは空にする。"},
        categories:{type:"array",items:{type:"string"},
          description:"出す種類。music/food/travel/dance/joy から。省略すると音楽と音楽以外が混ざる。「音楽だけ」と言われたときだけ [\"music\"] にする。"},
        label:{type:"string",description:"この棚につける短い見出し。例：うれしい夜に"}
      }, required:["artists"] } },
    { type:"function", name:"more_songs",
      description:"同じ気分のまま次の4枚。「他は？」と言われたらこれ。",
      parameters:{ type:"object", properties:{} } }
  ];
  // 安い版は Chat Completions なので道具の入れ物の形がちがう（中身は同じ）
  const CHAT_TOOLS=TOOLS.map(t=>({type:"function",
    function:{name:t.name,description:t.description,parameters:t.parameters}}));
  const SPLIT_INSTRUCTIONS=INSTRUCTIONS+"\n\n"+[
    "■ この版だけの約束（声にして読み上げるため）",
    "返事は必ず短く。1〜2文、合わせて60字以内。長いと待たせるし高くつく。",
    "箇条書き・記号・絵文字・URLを書かない。耳で聞いて分かる文だけ。",
    "数字は読み上げる形で書く（1972年 → 千九百七十二年 とはせず「1972年」でよい）。"
  ].join("\n");

  const sessionConfig=voice=>({ type:"realtime",
    instructions:INSTRUCTIONS, tools:TOOLS, tool_choice:"auto",
    audio:{ input:{ turn_detection:{type:"server_vad",threshold:0.5,prefix_padding_ms:300,
                      silence_duration_ms:600,create_response:true,interrupt_response:true},
                    transcription:{model:"whisper-1"} },
            output:{voice} } });

  /* ══════════════ 実測メーター ══════════════ */
  const USE={audioIn:0,audioCached:0,audioOut:0,textIn:0,textCached:0,textOut:0,usd:0,turns:0};
  // 安い版の実測入れもの。sttSec＝実際に送った音声の秒数、ttsSec＝実際に返ってきた声の秒数。
  const SPUSE={sttSec:0,chatIn:0,chatOut:0,ttsChars:0,ttsSec:0,usd:0,turns:0};
  function spCost(){
    const p=SPLIT.price;
    SPUSE.usd = SPUSE.sttSec/60*p.sttPerMin
              + (SPUSE.chatIn*p.chatIn + SPUSE.chatOut*p.chatOut)/1e6
              + (SPUSE.ttsChars*p.ttsTextIn)/1e6
              + SPUSE.ttsSec/60*p.ttsPerMin;
  }
  // 返事の遅れ（実測）。t0＝喋り終わりを拾った瞬間
  let LAG={t0:0,tStt:0,tThink:0,tFirst:0,voice:false}, LAGS=[];
  function paintLag(){
    if(!isSplit()&&!LAGS.length){ lagEl.textContent=""; return; }
    if(!LAG.voice) return;                       // 声で話しかけた分だけ測る
    if(!LAG.tFirst){ lagEl.textContent = LAG.t0? "返事をつくっています…" : ""; return; }
    const tot=(LAG.tFirst-LAG.t0)/1000;
    const a=(LAG.tStt-LAG.t0)/1000, b=(LAG.tThink-LAG.tStt)/1000, c=(LAG.tFirst-LAG.tThink)/1000;
    const avg=LAGS.length?LAGS.reduce((x,y)=>x+y,0)/LAGS.length/1000:tot;
    lagEl.innerHTML=`返事の遅れ <b>${tot.toFixed(1)}秒</b>`
      +`（聞き取り${a.toFixed(1)}／考える${b.toFixed(1)}／声${c.toFixed(1)}）`
      +(LAGS.length>1?`　平均${avg.toFixed(1)}秒`:"");
  }
  let startedAt=0, meterTimer=0;

  /* ── 財布（1日いくらまで喋れるか）────────────────────────────────
     なぜ要るか（2026-09-19・たまごさんの言葉）:
       「あれで本当に金がかかるなら全然実用的じゃない。多分、俺の金がどんどん溶けていく。」
     OpenAI側の上限設定とは**別に、こちら側で止める**。
     数え方は見積もりではなく、このページが既に出している実測
     （APIが返したトークン数 × 公式単価／送った音声の秒数）をそのまま日ぐりで積む。
     ★財布が空になったら「つなげない」「喋っている途中なら切る」。 */
  const SAIFU={
    capDefault:100,                      // 1日100円。設定で変えられる。
    day(){ const d=new Date(Date.now()+9*3600e3); return d.toISOString().slice(0,10); },
    kDay(){ return "tamago_voice_yen_"+this.day(); },
    cap(){ try{ const v=parseFloat(localStorage.getItem("tamago_voice_cap_yen"));
                return (isFinite(v)&&v>0)?v:this.capDefault; }catch(_){ return this.capDefault; } },
    setCap(v){ try{ localStorage.setItem("tamago_voice_cap_yen",String(v)); }catch(_){}
               paintMeter(); },
    today(){ try{ const v=parseFloat(localStorage.getItem(this.kDay())); return isFinite(v)?v:0; }
             catch(_){ return 0; } },
    put(v){ try{ localStorage.setItem(this.kDay(),String(Math.max(0,v))); }catch(_){} },
    base:0,                              // つないだ時点での「今日ここまで」
    stopped:false,
    hajime(){ this.base=this.today(); this.stopped=false; },
    nokori(){ return this.cap()-this.today(); }
  };
  function saifuKire(){                  // 財布が空。喋っているなら切る。
    if(SAIFU.stopped) return;
    SAIFU.stopped=true;
    try{ closeAll(); }catch(_){}
    try{ closePlayer(false); }catch(_){}
    goEl.disabled=false;
    setState("今日のぶんは使い切りました");
    say("sys","今日の上限（"+SAIFU.cap().toFixed(0)+"円）に達したので切りました。"
      +"続けるなら設定で上限を上げてください。（OpenAI側の上限とは別に、この画面で止めています）");
  }

  function addUsage(u){
    if(!u) return;
    const i=u.input_token_details||{}, o=u.output_token_details||{}, c=i.cached_tokens_details||{};
    const aIn=i.audio_tokens||0, aC=c.audio_tokens||0, tIn=i.text_tokens||0, tC=c.text_tokens||0;
    USE.audioCached+=aC; USE.audioIn+=Math.max(0,aIn-aC);
    USE.textCached +=tC; USE.textIn +=Math.max(0,tIn-tC);
    USE.audioOut+=o.audio_tokens||0; USE.textOut+=o.text_tokens||0; USE.turns++;
    const p=ENGINES[engineKey].price;
    if(p) USE.usd=(USE.audioIn*p.audioIn+USE.audioCached*p.audioCached+USE.audioOut*p.audioOut
                  +USE.textIn*p.textIn+USE.textCached*p.textCached+USE.textOut*p.textOut)/1e6;
    paintMeter(); paintCostTable();
  }
  function paintMeter(){
    const sec=startedAt?(Date.now()-startedAt)/1000:0;
    const e=ENGINES[engineKey];
    let yen,how;
    if(e.vendor==="split"){ spCost(); yen=SPUSE.usd*YEN;
      how=SPUSE.usd>0?"実測（送った音声の秒数・APIが返したトークン数・返ってきた声の秒数）":"まだ喋っていません"; }
    else if(e.perMin){ yen=sec/60*e.perMin*YEN; how="定額（つないだ時間）"; }
    else{ yen=USE.usd*YEN; how=USE.turns?"実測（APIが返したトークン数）":"まだ喋っていません"; }
    const perMin=sec>5?(yen/(sec/60)):0;
    // ★このセッションぶんを「今日の合計」に積む（1秒ごとに書くので、落ちても消えない）
    if(startedAt) SAIFU.put(SAIFU.base+yen);
    const kyou=SAIFU.today(), cap=SAIFU.cap();
    const nokori=Math.max(0,cap-kyou);
    meterEl.innerHTML=`${Math.floor(sec/60)}分${String(Math.floor(sec%60)).padStart(2,"0")}秒 ／ `
      +`<b>${yen.toFixed(1)}円</b>`+(perMin?`（このペースで1分 約${perMin.toFixed(1)}円）`:"")
      +`<br>今日ここまで <b>${kyou.toFixed(1)}円</b> ／ 上限 ${cap.toFixed(0)}円`
      +`（あと ${nokori.toFixed(1)}円）`
      +`<br><span style="opacity:.7">${how}</span>`;
    if(startedAt && kyou>=cap) saifuKire();
  }
  function paintCostTable(){
    if(isSplit()){
      spCost();
      const p=SPLIT.price, y=v=>v*YEN;
      const rows=[
        ["① 聞く（送った音声）", SPUSE.sttSec.toFixed(1)+"秒", y(SPUSE.sttSec/60*p.sttPerMin)],
        ["② 考える 入", SPUSE.chatIn.toLocaleString()+" トークン", y(SPUSE.chatIn*p.chatIn/1e6)],
        ["② 考える 出", SPUSE.chatOut.toLocaleString()+" トークン", y(SPUSE.chatOut*p.chatOut/1e6)],
        ["③ 喋る 文字", SPUSE.ttsChars.toLocaleString()+" 文字", y(SPUSE.ttsChars*p.ttsTextIn/1e6)],
        ["③ 喋る 出た声", SPUSE.ttsSec.toFixed(1)+"秒", y(SPUSE.ttsSec/60*p.ttsPerMin)]
      ];
      $("costTable").innerHTML=rows.map(([k,v,c])=>
        `<tr><td>${k}</td><td>${v}　${c.toFixed(2)}円</td></tr>`).join("")
        +`<tr><td><b>合計</b></td><td><b>$${SPUSE.usd.toFixed(5)}（${(SPUSE.usd*YEN).toFixed(2)}円）</b></td></tr>`;
      return;
    }
    const p=ENGINES[engineKey].price;
    const rows=[["音声 入（新しい分）",USE.audioIn],["音声 入（キャッシュ）",USE.audioCached],
      ["音声 出",USE.audioOut],["文字 入",USE.textIn+USE.textCached],["文字 出",USE.textOut]];
    $("costTable").innerHTML=rows.map(([k,v])=>
      `<tr><td>${k}</td><td>${v.toLocaleString()} トークン</td></tr>`).join("")
      +(p?`<tr><td><b>合計</b></td><td><b>$${USE.usd.toFixed(4)}（${(USE.usd*YEN).toFixed(1)}円）</b></td></tr>`
         :`<tr><td><b>合計</b></td><td><b>定額なので時間で決まります</b></td></tr>`);
  }
  paintCostTable();
  // 裏口（客には「・」にしか見えない）。押すと設定が開く。
  $("devLink").addEventListener("click",e=>{ e.preventDefault();
    const d=$("settings"); d.hidden=false; d.open=true; });

  /* ══════════════ つなぐ ══════════════ */
  let pc=null,dc=null,mic=null,audioEl=null,ac=null;
  let ws=null,wsCtx=null,wsAt=0,wsNode=null,wsSrc=null,micOn=true;
  const itemIds=[]; const KEEP=8;
  const live=()=>(dc&&dc.readyState==="open")||(ws&&ws.readyState===1)||spOn;
  const say=(cls,txt)=>{ if(window.Seihon&&Seihon.say) return Seihon.say(cls,txt);
    const d=document.createElement("div"); d.className="line "+cls;
    d.textContent=txt; logEl.appendChild(d); logEl.scrollTop=logEl.scrollHeight; };
  const setState=s=>{stateEl.textContent=s;};
  function setMic(on){ micOn=on; if(mic) mic.getAudioTracks().forEach(t=>t.enabled=on); }
  function send(o){ const s=JSON.stringify(o);
    if(dc&&dc.readyState==="open") dc.send(s); else if(ws&&ws.readyState===1) ws.send(s); }
  function tellModel(text,quiet){
    if(!live()) return;
    if(spOn){ spTell(text,quiet); return; }
    send({type:"conversation.item.create",
      item:{type:"message",role:"system",content:[{type:"input_text",text}]}});
    if(!quiet && !playing) send({type:"response.create"});
  }
  // 古い発話を捨てる。これをしないと毎回の返事に会話全部の音声がぶら下がり、値段が雪だるまになる
  function prune(){ while(itemIds.length>KEEP) send({type:"conversation.item.delete",item_id:itemIds.shift()}); }

  /* ══════════════ 安い版：聞く → 考える → 喋る を分けてつなぐ ══════════════
     リアルタイムAPIは「黙っている時間」にも音声トークンが流れるので高い。
     ここでは①喋り終わりを画面側で見つけて、その分だけ文字起こしに送り、
     ②文字だけで考えさせ、③返事を文の切れ目ごとに音声合成して、順に鳴らす。
     黙っている時間はタダになる。そのかわり返事は一拍遅れる（画面に実測で出す）。 */
  let spOn=false, spKey="", spVoice="coral", spCtx=null, spNode=null, spSrc=null;
  let spHist=[], spBusy=false, spSpeak=false, spAt=0, spQ=null, spEndTimer=0, spSr=24000;

  // 送る前に16kHzへ落とす。文字起こしは16kHzで足りるので、上りが軽くなる＝返事が早くなる。
  function to16k(chunks,sr){
    let n=0; for(const c of chunks) n+=c.length;
    const src=new Float32Array(n); let o=0;
    for(const c of chunks){ src.set(c,o); o+=c.length; }
    if(sr<=16000) return {data:src,sr:sr};
    const m=Math.round(n*16000/sr), out=new Float32Array(m), step=n/m;
    for(let i=0;i<m;i++){
      const x=i*step, i0=Math.floor(x), i1=Math.min(n-1,i0+1), f=x-i0;
      out[i]=src[i0]*(1-f)+src[i1]*f;
    }
    return {data:out,sr:16000};
  }
  function wavBlob(chunks,sr){
    const r=to16k(chunks,sr); chunks=[r.data]; sr=r.sr;
    let n=0; for(const c of chunks) n+=c.length;
    const buf=new ArrayBuffer(44+n*2), v=new DataView(buf);
    const w=(o,s)=>{ for(let i=0;i<s.length;i++) v.setUint8(o+i,s.charCodeAt(i)); };
    w(0,"RIFF"); v.setUint32(4,36+n*2,true); w(8,"WAVEfmt ");
    v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
    v.setUint32(24,sr,true); v.setUint32(28,sr*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true);
    w(36,"data"); v.setUint32(40,n*2,true);
    let o=44;
    for(const c of chunks) for(let i=0;i<c.length;i++){
      const x=Math.max(-1,Math.min(1,c[i])); v.setInt16(o,x<0?x*0x8000:x*0x7FFF,true); o+=2; }
    return new Blob([buf],{type:"audio/wav"});
  }
  function spAnalyser(){
    if(!analyser){ analyser=spCtx.createAnalyser(); analyser.fftSize=512;
      analyser.smoothingTimeConstant=0.4; analyser.connect(spCtx.destination); }
    return analyser;
  }

  async function connectSplit(voice){
    spKey=keyEl.value.trim();
    if(!spKey) throw new Error("OpenAIの鍵が空です（設定の中に入れてください）");
    try{ localStorage.setItem("tamago_openai_key",spKey); }catch(_){}
    spVoice=voice; spHist=[]; spBusy=false; spSpeak=false; spAt=0;
    spQ=Promise.resolve(); LAG={t0:0,tStt:0,tThink:0,tFirst:0,voice:false}; LAGS=[]; lagEl.textContent="";
    Object.keys(SPUSE).forEach(k=>SPUSE[k]=0);
    try{ spCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:24000}); }
    catch(_){ spCtx=new (window.AudioContext||window.webkitAudioContext)(); }
    if(spCtx.state==="suspended") await spCtx.resume();
    spSr=spCtx.sampleRate;
    mic=await navigator.mediaDevices.getUserMedia(
      {audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    spSrc=spCtx.createMediaStreamSource(mic);
    spNode=spCtx.createScriptProcessor(2048,1,1);

    let floor=0.004, pre=[], rec=null, voiced=0, silent=0;
    const FR=2048/spSr;                       // 1こまの長さ（秒）
    const PRE=Math.ceil(0.30/FR);             // 頭を切らないための先読み
    spNode.onaudioprocess=ev=>{
      if(!spOn) return;
      const f=ev.inputBuffer.getChannelData(0), c=new Float32Array(f);
      let s=0; for(let i=0;i<c.length;i++) s+=c[i]*c[i];
      const rms=Math.sqrt(s/c.length);
      if(!micOn||spBusy||spSpeak||playing){ rec=null; voiced=0; silent=0; pre.length=0; return; }
      const ON=Math.max(0.018,floor*3.2), OFF=Math.max(0.010,floor*1.8);
      if(!rec){
        floor=floor*0.97+rms*0.03;
        pre.push(c); if(pre.length>PRE) pre.shift();
        if(rms>ON){ if(++voiced>=2){ rec=pre.slice(); pre=[]; silent=0;
                      setState("聞いています…"); } }
        else voiced=0;
      }else{
        rec.push(c);
        if(rms<OFF) silent++; else silent=0;
        const dur=rec.length*FR;
        if((silent*FR>=0.55 && dur>0.5) || dur>15){
          const take=rec; rec=null; voiced=0; silent=0; pre=[];
          if(dur>=0.5) spHeard(take,dur-silent*FR*0.5);
        }
      }
    };
    spSrc.connect(spNode); spNode.connect(spCtx.destination);
    spOn=true; micOn=true;
    setState("聞いています。話しかけてください");
    spTell("お客さんが画面を開きました。短く挨拶して、今日どんな気分か聞いてください。");
  }

  /* ① 聞く：喋り終わりを拾ったので、その塊だけ文字起こしに送る */
  async function spHeard(chunks,dur){
    if(spBusy) return;
    spBusy=true; LAG={t0:performance.now(),tStt:0,tThink:0,tFirst:0,voice:true}; paintLag();
    setState("聞き取っています…");
    let text="";
    try{
      const fd=new FormData();
      fd.append("file",wavBlob(chunks,spSr),"a.wav");
      fd.append("model",SPLIT.stt);
      fd.append("language","ja");
      fd.append("response_format","json");
      const r=await fetch("https://api.openai.com/v1/audio/transcriptions",
        {method:"POST",headers:{Authorization:"Bearer "+spKey},body:fd});
      if(!r.ok) throw new Error(r.status+" "+(await r.text()).slice(0,140));
      const j=await r.json();
      text=String(j.text||"").trim();
      SPUSE.sttSec+=dur;                       // 実測：実際に送った音声の秒数
      LAG.tStt=performance.now();
    }catch(e){ say("sys","聞き取れませんでした："+e.message);
      spBusy=false; setState("聞いています"); paintMeter(); paintCostTable(); return; }
    // 無音を拾ったときの空うちを捨てる（ここで捨てれば以降はタダ）
    if(!text || text.length<2 || /^[。、．，…\s]*$/.test(text)){
      spBusy=false; setState("聞いています"); paintMeter(); paintCostTable(); return; }
    say("me",text);
    spHist.push({role:"user",content:text}); spPrune();
    try{ await spTurn(); }catch(e){ say("sys","返事が作れませんでした："+e.message); }
    SPUSE.turns++; spBusy=false;
    paintMeter(); paintCostTable();
  }

  /* ②③ 考える → 喋る。道具を呼んだら棚を引いて、もう一周する */
  async function spTurn(){
    for(let round=0; round<3; round++){
      const calls=await spChat();
      if(!calls.length) return;
      spHist.push({role:"assistant",content:null,
        tool_calls:calls.map(c=>({id:c.id,type:"function",
          function:{name:c.name,arguments:c.args||"{}"}}))});
      for(const c of calls){
        setState("棚を見ています…");
        const payload=await toolRun(c.name,c.args);
        spHist.push({role:"tool",tool_call_id:c.id,content:JSON.stringify(payload)});
      }
    }
  }

  /* ② 考える：ストリームで受けて、文の切れ目が来た端から③へ流す */
  async function spChat(){
    const body={ model:SPLIT.chat, temperature:0.8, max_tokens:200,
      messages:[{role:"system",content:SPLIT_INSTRUCTIONS}].concat(spHist),
      tools:CHAT_TOOLS, tool_choice:"auto",
      stream:true, stream_options:{include_usage:true} };
    const r=await fetch("https://api.openai.com/v1/chat/completions",{method:"POST",
      headers:{Authorization:"Bearer "+spKey,"Content-Type":"application/json"},
      body:JSON.stringify(body)});
    if(!r.ok) throw new Error(r.status+" "+(await r.text()).slice(0,140));
    const rd=r.body.getReader(), dec=new TextDecoder();
    let sb="", content="", pend="", calls=[];
    for(;;){
      const {value,done}=await rd.read(); if(done) break;
      sb+=dec.decode(value,{stream:true});
      let p;
      while((p=sb.indexOf("\n"))>=0){
        const line=sb.slice(0,p).trim(); sb=sb.slice(p+1);
        if(!line.startsWith("data:")) continue;
        const d=line.slice(5).trim(); if(!d||d==="[DONE]") continue;
        let j; try{ j=JSON.parse(d); }catch(_){ continue; }
        if(j.usage){ SPUSE.chatIn+=j.usage.prompt_tokens||0;
                     SPUSE.chatOut+=j.usage.completion_tokens||0; paintMeter(); }
        const ch=j.choices&&j.choices[0]; if(!ch) continue;
        const dl=ch.delta||{};
        if(dl.tool_calls) for(const tc of dl.tool_calls){
          const i=tc.index||0;
          calls[i]=calls[i]||{id:"",name:"",args:""};
          if(tc.id) calls[i].id=tc.id;
          if(tc.function&&tc.function.name) calls[i].name+=tc.function.name;
          if(tc.function&&tc.function.arguments) calls[i].args+=tc.function.arguments;
        }
        if(dl.content){
          if(!LAG.tThink){ LAG.tThink=performance.now(); }
          content+=dl.content; pend+=dl.content;
          const m=/^([\s\S]*?[。！？!?\n])/.exec(pend);
          if(m && m[1].replace(/\s/g,"").length>=8){ spSay(m[1].trim()); pend=pend.slice(m[1].length); }
        }
      }
    }
    if(pend.trim()) spSay(pend.trim());
    if(content.trim()) say("her",content.trim());
    return calls.filter(Boolean);
  }

  /* ③ 喋る：文ごとに音声合成して、順番に鳴らす。口の動きはこの音に合わせる */
  function spSay(text){
    if(!text) return;
    SPUSE.ttsChars+=text.length;
    spSpeak=true;
    spQ=spQ.then(()=>spTts(text)).catch(e=>say("sys","声が出せませんでした："+e.message));
  }
  async function spTts(text){
    if(!spOn) return;
    const r=await fetch("https://api.openai.com/v1/audio/speech",{method:"POST",
      headers:{Authorization:"Bearer "+spKey,"Content-Type":"application/json"},
      body:JSON.stringify({model:SPLIT.tts,voice:spVoice,input:text,response_format:"wav",
        speed:1.05,
        instructions:"やわらかく落ち着いた日本語で、親しみをこめて。少しだけ早口に。"})});
    if(!r.ok) throw new Error(r.status+" "+(await r.text()).slice(0,120));
    const ab=await r.arrayBuffer();
    if(!spOn) return;
    const buf=await new Promise((ok,ng)=>{ try{ const p=spCtx.decodeAudioData(ab,ok,ng);
      if(p&&p.then) p.then(ok,ng); }catch(e){ ng(e); } });
    SPUSE.ttsSec+=buf.duration;                 // 実測：返ってきた声の長さ
    const now=spCtx.currentTime;
    if(spAt<now+0.06) spAt=now+0.06;
    const src=spCtx.createBufferSource(); src.buffer=buf; src.connect(spAnalyser());
    src.start(spAt); spAt+=buf.duration;
    speaking=true; if(!playing) setState("話しています");
    if(!LAG.tFirst && LAG.t0){ LAG.tFirst=performance.now();
      if(LAG.voice){ LAGS.push(LAG.tFirst-LAG.t0); if(LAGS.length>20) LAGS.shift(); }
      paintLag(); }
    clearTimeout(spEndTimer);
    spEndTimer=setTimeout(spSaidAll,(spAt-spCtx.currentTime)*1000+260);
    paintMeter(); paintCostTable();
  }
  function spSaidAll(){
    speaking=false; spSpeak=false;
    if(spOn && !playing) setState("聞いています");
  }

  // 画面側の出来事（札を押した・ほかのを見せて）を、安い版にも同じように伝える
  function spTell(text,quiet){
    spHist.push({role:"system",content:text}); spPrune();
    if(quiet||playing||spBusy||!spOn) return;
    spBusy=true; LAG={t0:performance.now(),tStt:0,tThink:0,tFirst:0,voice:false};
    LAG.tStt=LAG.t0;
    spTurn().catch(e=>say("sys","返事が作れませんでした："+e.message))
      .then(()=>{ spBusy=false; paintMeter(); paintCostTable(); });
  }
  // 会話が伸びるほど毎回の「考える 入」が増える。直近5往復だけ残す。
  function spPrune(){
    if(spHist.length<=18) return;
    let seen=0;
    for(let i=spHist.length-1;i>=0;i--){
      if(spHist[i].role==="user" && ++seen===5){ spHist=spHist.slice(i); return; }
    }
  }
  function spClose(){
    spOn=false; spSpeak=false; spBusy=false; clearTimeout(spEndTimer);
    try{ spNode&&(spNode.onaudioprocess=null); spNode&&spNode.disconnect(); spSrc&&spSrc.disconnect(); }catch(_){}
    try{ spCtx&&spCtx.close(); }catch(_){}
    spNode=spSrc=spCtx=null; spKey=""; spAt=0;
  }

  async function connect(){
    const e=ENGINES[engineKey], voice=currentVoice();
    // ★財布が空なら、つながせない（OpenAI側の上限とは別の、こちら側の栓）
    if(SAIFU.nokori()<=0){
      say("sys","今日の上限（"+SAIFU.cap().toFixed(0)+"円）を使い切っています。"
        +"明日また使えます。今すぐ続けるなら設定で上限を上げてください。");
      setState("今日のぶんは使い切りました"); paintMeter(); return;
    }
    SAIFU.hajime();
    goEl.disabled=true; logEl.innerHTML="";
    shown.clear(); pool=[]; page=0; drawCards([]); moreEl.disabled=true; closePlayer(false);
    Object.keys(USE).forEach(k=>USE[k]=0);
    Object.keys(SPUSE).forEach(k=>SPUSE[k]=0);
    LAGS=[]; LAG={t0:0,tStt:0,tThink:0,tFirst:0,voice:false}; lagEl.textContent="";
    CAT.load().catch(()=>{});
    setState("つないでいます…"); startedAt=Date.now();
    clearInterval(meterTimer); meterTimer=setInterval(paintMeter,1000);
    try{
      if(e.vendor==="xai") await connectGrok(voice);
      else if(e.vendor==="split") await connectSplit(voice);
      else await connectOpenAI(voice,e);
    }
    catch(err){ say("sys","つながりませんでした → "+err.message);
      setState("失敗しました"); goEl.disabled=false; closeAll(); }
  }

  async function connectOpenAI(voice,e){
    const sk=keyEl.value.trim();
    if(!sk) throw new Error("OpenAIの鍵が空です（設定の中に入れてください）");
    try{ localStorage.setItem("tamago_openai_key",sk); }catch(_){}
    let token=sk,model=e.models[0],viaEk=false,lastErr="";
    for(const m of e.models){
      try{
        const cfg=sessionConfig(voice); cfg.model=m;
        const r=await fetch("https://api.openai.com/v1/realtime/client_secrets",{
          method:"POST",headers:{Authorization:"Bearer "+sk,"Content-Type":"application/json"},
          body:JSON.stringify({session:cfg})});
        if(!r.ok){ lastErr=r.status+" "+(await r.text()).slice(0,160); continue; }
        const j=await r.json();
        token=j.value||(j.client_secret&&j.client_secret.value); model=m; viaEk=true; break;
      }catch(err){ lastErr=err.message; }
    }
    if(!viaEk) say("sys","使い捨て鍵は取れませんでした（"+lastErr+"）。鍵で直接つなぎます。");
    pc=new RTCPeerConnection();
    audioEl=document.createElement("audio"); audioEl.autoplay=true;
    audioEl.style.display="none"; document.body.appendChild(audioEl);
    pc.ontrack=ev=>{ if(!ev.streams[0]) return; audioEl.srcObject=ev.streams[0];
      try{ ac=ac||new (window.AudioContext||window.webkitAudioContext)();
        analyser=ac.createAnalyser(); analyser.fftSize=512; analyser.smoothingTimeConstant=0.4;
        ac.createMediaStreamSource(ev.streams[0]).connect(analyser);
        if(ac.state==="suspended") ac.resume(); }catch(_){} };
    mic=await navigator.mediaDevices.getUserMedia(
      {audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    pc.addTrack(mic.getAudioTracks()[0],mic);
    dc=pc.createDataChannel("oai-events");
    dc.addEventListener("open",()=>{ setState("聞いています。話しかけてください");
      send({type:"session.update",session:sessionConfig(voice)});
      setTimeout(()=>send({type:"response.create"}),350); });
    dc.addEventListener("close",()=>{ setState("切れました"); clearInterval(meterTimer); });
    dc.addEventListener("message",ev=>onEvent(ev.data));
    const offer=await pc.createOffer(); await pc.setLocalDescription(offer);
    let answer=null,err="";
    for(const m of (viaEk?[model]:e.models)){
      const r=await fetch("https://api.openai.com/v1/realtime/calls?model="+encodeURIComponent(m),{
        method:"POST",body:offer.sdp,
        headers:{Authorization:"Bearer "+token,"Content-Type":"application/sdp"}});
      if(r.ok){ answer=await r.text(); break; }
      err="calls "+r.status+"（"+m+"）: "+(await r.text()).slice(0,200);
      if(r.status===401||r.status===403) break;
    }
    if(!answer) throw new Error(err||"つながりませんでした");
    await pc.setRemoteDescription({type:"answer",sdp:answer});
  }

  async function connectGrok(voice){
    const sk=xkeyEl.value.trim();
    if(!sk) throw new Error("xAIの鍵が空です（設定の中に入れてください）");
    try{ localStorage.setItem("tamago_xai_key",sk); }catch(_){}
    const r=await fetch("https://api.x.ai/v1/realtime/client_secrets",{
      method:"POST",headers:{Authorization:"Bearer "+sk,"Content-Type":"application/json"},
      body:JSON.stringify({session:{type:"realtime",model:"grok-voice-latest"}})});
    if(!r.ok) throw new Error("使い捨て鍵が取れません "+r.status+" "+(await r.text()).slice(0,160));
    const j=await r.json();
    const token=j.value||(j.client_secret&&j.client_secret.value)||j.secret;
    if(!token) throw new Error("使い捨て鍵が返りませんでした");
    ws=new WebSocket("wss://api.x.ai/v1/realtime?model=grok-voice-latest",["xai-client-secret."+token]);
    ws.onopen=async()=>{
      setState("聞いています。話しかけてください");
      send({type:"session.update",session:{voice,instructions:INSTRUCTIONS,tools:TOOLS,tool_choice:"auto",
        input_audio_format:"pcm16",output_audio_format:"pcm16",
        input_audio_transcription:{model:"whisper-1"},
        turn_detection:{type:"server_vad",threshold:0.5,prefix_padding_ms:300,silence_duration_ms:600}}});
      send({type:"response.create"});
      await startMicPump();
    };
    ws.onmessage=ev=>onEvent(ev.data);
    ws.onclose=ev=>{ setState("切れました"); clearInterval(meterTimer);
      if(ev.code!==1000&&ev.code!==1005) say("sys","切れました（code "+ev.code+" "+(ev.reason||"")+"）"); };
    ws.onerror=()=>say("sys","Grokとのつなぎ目で切れました。鍵を見てください。");
  }

  async function startMicPump(){
    mic=await navigator.mediaDevices.getUserMedia(
      {audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    wsCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:24000});
    if(wsCtx.state==="suspended") await wsCtx.resume();
    wsSrc=wsCtx.createMediaStreamSource(mic);
    wsNode=wsCtx.createScriptProcessor(2048,1,1);
    wsNode.onaudioprocess=ev=>{
      if(!ws||ws.readyState!==1||!micOn) return;
      const f=ev.inputBuffer.getChannelData(0);
      const buf=new ArrayBuffer(f.length*2), view=new DataView(buf);
      for(let i=0;i<f.length;i++){ const v=Math.max(-1,Math.min(1,f[i]));
        view.setInt16(i*2, v<0?v*0x8000:v*0x7FFF, true); }
      let bin=""; const b=new Uint8Array(buf);
      for(let i=0;i<b.length;i+=8192) bin+=String.fromCharCode.apply(null,b.subarray(i,i+8192));
      send({type:"input_audio_buffer.append",audio:btoa(bin)});
    };
    wsSrc.connect(wsNode); wsNode.connect(wsCtx.destination);
  }
  function playPcm(b64){
    if(!wsCtx) wsCtx=new (window.AudioContext||window.webkitAudioContext)({sampleRate:24000});
    const bin=atob(b64), n=bin.length>>1;
    const buf=wsCtx.createBuffer(1,n,24000), ch=buf.getChannelData(0);
    for(let i=0;i<n;i++){ let v=(bin.charCodeAt(i*2+1)<<8)|bin.charCodeAt(i*2);
      if(v>=0x8000) v-=0x10000; ch[i]=v/32768; }
    const src=wsCtx.createBufferSource(); src.buffer=buf;
    if(!analyser){ analyser=wsCtx.createAnalyser(); analyser.fftSize=512;
      analyser.smoothingTimeConstant=0.4; analyser.connect(wsCtx.destination); }
    src.connect(analyser);
    const now=wsCtx.currentTime; if(wsAt<now+0.06) wsAt=now+0.06;
    src.start(wsAt); wsAt+=buf.duration;
  }

  const handled=new Set();
  // 棚を実際に引く。速い版・安い版の両方から呼ぶ共通部分。
  async function toolRun(name,argsRaw){
    let args={}; try{ args=JSON.parse(argsRaw||"{}"); }catch(_){}
    let got=[];
    try{
      if(name==="search_songs") got=await newSearch(
        {artists:args.artists||[],mood:args.mood||[],song_title:args.song_title||"",
         categories:args.categories||[]}, args.label||"");
      // ボタンでめくった直後に案内人まで more_songs を呼ぶと、4枚すっ飛ばしてしまう。
      // 2.5秒以内の呼び直しは、いま出ている4枚をそのまま返して二重めくりを止める。
      else if(name==="more_songs") got=(Date.now()-lastDealAt<2500)?lastDealt:dealFour();
    }catch(err){ say("sys","棚を引けませんでした："+err.message); }
    const payload=got.length?{ok:true,count:got.length,rest:pool.length,
      songs:got.map(c=>({title:c.title,by:c.sub,kind:c.kind})),
      note:"この曲だけが実在する。ここに無い曲名を口に出さないこと。カードは画面に出し終えた。押せばその場で鳴る。"}
      :{ok:false,count:0,rest:0,
      note:"棚に見つからなかった。artists にもっと多くのアーティスト名を入れて呼び直すこと。曲名を作らないこと。"};
    if(got.length) say("sys","棚から "+got.length+"枚："+got.map(s=>s.title).join(" / "));
    return payload;
  }
  async function runTool(name,argsRaw,callId){
    const payload=await toolRun(name,argsRaw);
    send({type:"conversation.item.create",
      item:{type:"function_call_output",call_id:callId,output:JSON.stringify(payload)}});
    send({type:"response.create"});
  }

  let buf="";
  function onEvent(raw){
    let ev; try{ ev=JSON.parse(raw);}catch(_){return}
    switch(ev.type){
      case "error": say("sys","エラー："+((ev.error&&ev.error.message)||JSON.stringify(ev).slice(0,160))); break;
      case "conversation.item.created":
        if(ev.item&&ev.item.id&&ev.item.type==="message"){ itemIds.push(ev.item.id); prune(); } break;
      case "input_audio_buffer.speech_started": speaking=false; setState("聞いています"); break;
      case "output_audio_buffer.started":
      case "response.output_audio.delta":
      case "response.audio.delta":
        speaking=true; setState("話しています");
        if(ws&&ev.delta) playPcm(ev.delta); break;
      case "response.output_audio_transcript.delta":
      case "response.audio_transcript.delta": buf+=(ev.delta||""); break;
      case "response.output_audio_transcript.done":
      case "response.audio_transcript.done": say("her",ev.transcript||buf); buf=""; break;
      case "conversation.item.input_audio_transcription.completed":
        if(ev.transcript) say("me",ev.transcript); break;
      case "response.function_call_arguments.done":
        if(ev.call_id&&!handled.has(ev.call_id)){ handled.add(ev.call_id);
          runTool(ev.name,ev.arguments,ev.call_id); } break;
      case "response.output_item.done":
        if(ev.item&&ev.item.type==="function_call"&&ev.item.call_id&&!handled.has(ev.item.call_id)){
          handled.add(ev.item.call_id); runTool(ev.item.name,ev.item.arguments,ev.item.call_id); } break;
      case "response.done":
        speaking=false;
        if(ev.response&&ev.response.usage) addUsage(ev.response.usage);
        setState(playing?"聴いています":"聞いています"); break;
    }
  }

  function closeAll(){
    spClose();
    try{dc&&dc.close()}catch(_){}
    try{pc&&pc.close()}catch(_){}
    try{ws&&ws.close()}catch(_){}
    try{wsNode&&wsNode.disconnect(); wsSrc&&wsSrc.disconnect();}catch(_){}
    if(mic) mic.getTracks().forEach(t=>t.stop());
    if(audioEl) audioEl.remove();
    dc=pc=mic=audioEl=ws=wsNode=wsSrc=null; analyser=null; speaking=false;
    itemIds.length=0; handled.clear(); clearInterval(meterTimer);
    paintMeter();            // ★最後にもう一度だけ今日の合計へ積む
    startedAt=0;             // ★止めた後は時間を数えない（二重に積まないため）
  }
  /* ★1日の上限を変える口。客前に出す（怖いのは「いくらまで」が見えないこと）。 */
  (function(){
    try{
      const box=document.createElement("p");
      box.style.cssText="text-align:center;color:#9d947f;font-size:.74rem;margin:6px 0 0";
      box.innerHTML='1日の上限 <input id="capIn" type="number" min="10" step="10" '
        +'style="width:5.5em;background:#1a1712;color:#e8e2d4;border:1px solid #3a352c;'
        +'border-radius:6px;padding:2px 4px;text-align:right"> 円 '
        +'<button id="capSet" style="background:#2a2622;color:#e8e2d4;border:1px solid #3a352c;'
        +'border-radius:6px;padding:2px 8px;cursor:pointer">決める</button>';
      meterEl.parentNode.insertBefore(box,meterEl.nextSibling);
      const inp=box.querySelector("#capIn"); inp.value=SAIFU.cap();
      box.querySelector("#capSet").addEventListener("click",()=>{
        const v=parseFloat(inp.value); if(isFinite(v)&&v>0) SAIFU.setCap(v);
      });
    }catch(_){}
    paintMeter();
  })();
  goEl.addEventListener("click",connect);
  stopEl.addEventListener("click",()=>{ closeAll(); closePlayer(false);
    setState("やめました"); goEl.disabled=false; });

  /* ★正本の器（bridge.js）に、動いているものをそのまま渡す。作り直さない。 */
  if(window.Seihon){
    window.Seihon.engine={
      newSearch:newSearch, dealFour:dealFour, live:live,
      hasPool:function(){ return !!(pool && pool.length); }
    };
  }
})();
