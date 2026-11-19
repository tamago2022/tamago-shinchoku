/* 955番 — 案内所コンシェルジュ 共通エンジン（No.02 / No.08 で同じものを使う）
 *
 * 正本: status/952_seihon/concierge-concept-02-08.md（joy-relief-station Issue #431）
 *  - 一度に4件 →「他を見せて」で次の4件
 *  - 音楽だけに見せない（食・動物・旅・ことば・笑い・動画も同じ器に載る）
 *  - カテゴリは小さなモチーフで直感的に分かる（アイコンだらけにはしない）
 *  - APIキー・モデル・接続状態は客前に出さない（店の裏＝開発用の抽斗へ）
 *  - GPT Live（OpenAI Realtime / WebRTC）の既存機能は壊さない
 *
 * 見た目（色・組版・ヒーロー）はページ側のCSSが持つ。ここは中身だけ。
 */
(function (global) {
  "use strict";

  const $ = (id) => document.getElementById(id);

  /* ══════════════════════════════════════════════════════════════
     1. 棚 — 実在するものしか出さない
     ══════════════════════════════════════════════════════════════ */

  // 曲の索引（34,240件・tools/_953_build_song_index.py が作ったもの）
  const SONG = "assets/953-songs/";
  // 音楽以外の種（実在する部屋のカードから作った・tools/_955_build_seeds.py）
  const SEEDS = "assets/955-concierge/seeds.json";

  const CAT_LABEL = {
    music: "音楽", video: "動画", food: "食べもの",
    animal: "動物", travel: "旅", word: "ことば", laugh: "笑い",
  };

  const shelf = {
    head: null, picks: null, bucket: {}, seeds: null, loading: null,
    async load() {
      if (this.head) return;
      if (this.loading) return this.loading;
      this.loading = (async () => {
        const [h, p, s] = await Promise.all([
          fetch(SONG + "head.json").then((r) => r.json()),
          fetch(SONG + "picks.json").then((r) => r.json()),
          fetch(SEEDS).then((r) => r.json()).catch(() => ({ cards: [] })),
        ]);
        this.head = h; this.picks = p; this.seeds = s.cards || [];
      })();
      return this.loading;
    },
    async bucketOf(n) {
      if (this.bucket[n]) return this.bucket[n];
      try {
        this.bucket[n] = await fetch(SONG + "t/" + n + ".json").then((r) => (r.ok ? r.json() : []));
      } catch (e) { this.bucket[n] = []; }
      return this.bucket[n];
    },
  };

  // 索引を作った python と一字一句そろえること
  function norm(s) {
    return String(s).normalize("NFKC").toLowerCase()
      .replace(/[\s'’`\-_.,!?/()（）「」『』・:;"]+/g, " ").trim();
  }
  function prefixes(s) {
    const out = new Set();
    for (const w of norm(s).split(" ")) if (w) out.add(w.slice(0, 2));
    return [...out];
  }
  function bucketNo(pre) {
    const NB = shelf.head ? shelf.head.nb : 128;
    const h = pre.charCodeAt(0) * 131 + (pre.length > 1 ? pre.charCodeAt(1) : 0);
    return h % NB;
  }

  // 見出しが「まとめ動画」臭いものは沈める（消しはしない）
  function tidy(title) {
    let p = 0;
    if (title.length > 45) p -= 60; else if (title.length > 30) p -= 20;
    if (/[|｜]/.test(title)) p -= 50;
    if (/[【】]/.test(title)) p -= 25;
    if (/[☀-⟿✨🎵🔥]/u.test(title)) p -= 30;
    return p;
  }

  const shown = new Set();
  let pool = [], poolLabel = "";

  function artistText(a) {
    return norm([a.n, (a.al || []).join(" "), (a.g || []).join(" "),
      (a.e || []).join(" "), a.ab || ""].join(" "));
  }

  /** 音楽以外の種を引く。タグ・題・一行コピーのどれかに当たればよい。 */
  function findSeeds(qs) {
    const out = [];
    for (const c of shelf.seeds || []) {
      const hay = norm([c.title, c.copy, (c.tags || []).join(" "), CAT_LABEL[c.cat] || ""].join(" "));
      let sc = 0;
      for (const q of qs) {
        if (!q) continue;
        if ((c.tags || []).some((t) => norm(t) === q)) sc += 70;
        else if (hay.includes(q)) sc += q.length >= 3 ? 34 : 14;
      }
      if (sc) out.push({ kind: "seed", cat: c.cat, title: c.title, sub: c.copy,
                         yt: c.yt, url: c.url, key: "s:" + c.id, sc: sc });
    }
    return out;
  }

  /** 曲の棚を引く。ここが返したものだけが、案内人が口に出してよい曲。 */
  async function findSongs(qs) {
    const A = shelf.head.A;
    const artScore = new Map();
    A.forEach((a, i) => {
      const hay = artistText(a);
      let sc = 0;
      for (const q of qs) {
        if (!q) continue;
        if (norm(a.n) === q) sc += 100;
        else if (hay.includes(q)) sc += q.length >= 3 ? 40 : 12;
      }
      if (sc) artScore.set(i, sc);
    });

    const out = [], seen = new Set();
    const push = (row, sc) => {
      const key = "m:" + row[0] + "/" + row[1];
      if (seen.has(key)) return;
      seen.add(key);
      const a = A[row[0]];
      out.push({
        kind: "song", cat: "music", title: row[2], sub: a.n + (row[3] ? "　" + row[3] + "年" : ""),
        yt: row[4] || "", key: key,
        url: shelf.head.base + "?artist=" + encodeURIComponent(a.i) + "&song=" + encodeURIComponent(row[1]),
        sc: sc + tidy(row[2]) + (row[3] ? 10 : 0),
      });
    };

    if (artScore.size) {
      for (const row of shelf.picks) {
        const sc = artScore.get(row[0]);
        if (sc) push(row, sc + 20);
      }
    }
    const pres = new Set();
    for (const q of qs) for (const p of prefixes(q)) pres.add(p);
    const nums = [...new Set([...pres].map(bucketNo))].slice(0, 6);
    const shelves = await Promise.all(nums.map((n) => shelf.bucketOf(n)));
    for (const rows of shelves) {
      for (const row of rows) {
        const t = norm(row[2]);
        let sc = 0;
        for (const q of qs) {
          if (q.length < 2 && !/[^\x00-\x7F]/.test(q)) continue;
          if (t === q) sc += 90; else if (t.includes(q)) sc += 30;
        }
        if (sc) push(row, sc + (artScore.get(row[0]) || 0));
      }
    }
    return out;
  }

  /**
   * 言われた言葉を、実在するカードの列に変える。
   * ★音楽に寄りすぎないよう、音楽以外の種を必ず上の方に混ぜる。
   *   「音楽しかない」と誤認させないこと、が正本の一番の目的。
   */
  async function search(queries, wantCats) {
    await shelf.load();
    const qs = (queries || []).map(norm).filter((q) => q.length >= 1);
    if (!qs.length) return [];

    let seeds = findSeeds(qs);
    let songs = await findSongs(qs);

    // カテゴリの指定があれば絞る
    if (wantCats && wantCats.length) {
      const want = new Set(wantCats);
      seeds = seeds.filter((s) => want.has(s.cat));
      if (!want.has("music")) songs = [];
    }
    seeds.sort((a, b) => b.sc - a.sc);
    songs.sort((a, b) => b.sc - a.sc);

    // 何も当たらなかったときは、棚の顔ぶれをそのまま見せる（音楽以外も必ず入る）
    if (!seeds.length && !songs.length) {
      seeds = (shelf.seeds || []).slice().sort(() => Math.random() - 0.5)
        .map((c) => ({ kind: "seed", cat: c.cat, title: c.title, sub: c.copy,
                       yt: c.yt, url: c.url, key: "s:" + c.id, sc: 1 }));
    }

    // 交互に編む：種 → 曲 → 種 → 曲 …（音楽が列を独占しない）
    const out = [];
    const perCat = {};
    let i = 0, j = 0;
    while (out.length < 40 && (i < seeds.length || j < songs.length)) {
      if (i < seeds.length) {
        const s = seeds[i++];
        if ((perCat[s.cat] = (perCat[s.cat] || 0) + 1) <= 8) out.push(s);
      }
      if (j < songs.length) out.push(songs[j++]);
      if (i < seeds.length) {
        const s = seeds[i++];
        if ((perCat[s.cat] = (perCat[s.cat] || 0) + 1) <= 8) out.push(s);
      }
    }
    return out;
  }

  /* ══════════════════════════════════════════════════════════════
     2. 札（カード）— カテゴリが目で分かる
     ══════════════════════════════════════════════════════════════ */

  // 店内の物・紙ものとして置く。UIアイコンセットにはしない。
  const MOTIF = {
    music: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10.5" class="d"/><circle cx="12" cy="12" r="6.6" class="r"/><circle cx="12" cy="12" r="3.6" class="l"/><circle cx="12" cy="12" r="1" class="h"/></svg>',
    video: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1.5" y="4.5" width="21" height="15" rx="1.5" class="d"/><rect x="3.4" y="6.2" width="2" height="2" class="h"/><rect x="3.4" y="10.8" width="2" height="2" class="h"/><rect x="3.4" y="15.4" width="2" height="2" class="h"/><rect x="18.6" y="6.2" width="2" height="2" class="h"/><rect x="18.6" y="10.8" width="2" height="2" class="h"/><rect x="18.6" y="15.4" width="2" height="2" class="h"/><rect x="7" y="7" width="10" height="10" class="r"/></svg>',
    food: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 3.5h16v15l-2.7-1.6L14.6 18.5 12 16.9 9.4 18.5 6.7 16.9 4 18.5z" class="d"/><path d="M7.2 7.6h9.6M7.2 10.6h9.6M7.2 13.6h6" class="s"/></svg>',
    animal: '<svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="15.4" rx="5.2" ry="4.4" class="d"/><ellipse cx="5.6" cy="10.4" rx="2.5" ry="3.1" class="d"/><ellipse cx="18.4" cy="10.4" rx="2.5" ry="3.1" class="d"/><ellipse cx="9.4" cy="6.3" rx="2.4" ry="3" class="d"/><ellipse cx="15" cy="6.1" rx="2.4" ry="3" class="d"/></svg>',
    travel: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1.8" y="4.5" width="20.4" height="15" rx="1" class="d"/><rect x="15.4" y="6.6" width="4.8" height="4" class="r"/><path d="M3.8 15.6l4.4-4.6 3.2 3.1 2.6-2.4 4.2 3.9" class="s"/><path d="M3.8 18h7" class="s"/></svg>',
    word: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5.6C9.6 3.9 6.6 3.6 3.2 4.4v14.2c3.4-.8 6.4-.5 8.8 1.2 2.4-1.7 5.4-2 8.8-1.2V4.4C17.4 3.6 14.4 3.9 12 5.6z" class="d"/><path d="M12 5.6v14.2" class="s"/></svg>',
    laugh: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="1.5" y="4.5" width="21" height="15" rx="1.5" class="d"/><rect x="3.4" y="6.2" width="2" height="2" class="h"/><rect x="3.4" y="15.4" width="2" height="2" class="h"/><rect x="18.6" y="6.2" width="2" height="2" class="h"/><rect x="18.6" y="15.4" width="2" height="2" class="h"/><path d="M8.4 10.4c.9 3.4 6.3 3.4 7.2 0" class="s"/></svg>',
  };

  function card(c) {
    const a = document.createElement("a");
    a.className = "card cat-" + c.cat;
    a.href = c.url; a.target = "_blank"; a.rel = "noopener";
    a.setAttribute("data-cat", c.cat);

    const fig = document.createElement("div");
    fig.className = "thumb";
    if (c.yt) {
      const img = document.createElement("img");
      img.loading = "lazy"; img.alt = "";
      img.src = "https://i.ytimg.com/vi/" + c.yt + "/mqdefault.jpg";
      img.onerror = () => { img.remove(); fig.classList.add("noimg"); };
      fig.appendChild(img);
    } else { fig.classList.add("noimg"); }

    const mo = document.createElement("span");
    mo.className = "motif";
    mo.innerHTML = MOTIF[c.cat] || MOTIF.music;
    fig.appendChild(mo);

    const body = document.createElement("div");
    body.className = "body";
    const kind = document.createElement("p");
    kind.className = "kind"; kind.textContent = CAT_LABEL[c.cat] || "";
    const t = document.createElement("p");
    t.className = "t"; t.textContent = c.title;
    const s = document.createElement("p");
    s.className = "s"; s.textContent = c.sub || "";
    body.append(kind, t, s);
    a.append(fig, body);
    return a;
  }

  /* ══════════════════════════════════════════════════════════════
     3. 案内人（GPT Live / OpenAI Realtime・WebRTC）
     ══════════════════════════════════════════════════════════════ */

  const INSTRUCTIONS = [
    "あなたは「ごきげん補給所」の案内人です。名前はたまこ。",
    "ここは音楽だけの店ではありません。音楽・動画・食べもの・動物・旅・ことば・笑いを、",
    "同じ「ごきげんの種」として並べて置いてある、小さな店です。",
    "話し方：日本語。短く、やわらかく、間を大事に。1回の返事は2〜3文まで。",
    "相手を質問攻めにしない。まず気分を受け止めて、それから札をそっと差し出す。",
    "",
    "■ いちばん大事な約束（破ったら案内人失格）",
    "作品名・曲名・店名を口に出してよいのは、道具 search_songs が返してきたものだけです。",
    "あなたの記憶の中にある名前を、そのままお客さんに言ってはいけません。棚に無いかもしれないからです。",
    "年号・売上・「代表曲」のような断定は、道具が返していないかぎり言わない。",
    "",
    "■ 音楽に寄りすぎない",
    "お客さんが「音楽」と言っていないのに、音楽だけを4枚出さないこと。",
    "気分の相談には、食べもの・動物・旅・ことばなども混ぜて差し出す。",
    "「音楽」と言われたら4曲、「猫」と言われたら動物を、のように会話に合わせて揃えてよい。",
    "",
    "■ search_songs の使い方",
    "queries には、その気分に合う言葉を日本語と英語まぜて5〜10個入れる。",
    "cats を付けると、そのカテゴリだけに絞れる（music / video / food / animal / travel / word / laugh）。",
    "例：「お腹すいた」→ queries:[\"カレー\",\"パン\",\"甘い\",\"屋台\"], cats:[\"food\"]",
    "例：「なんか疲れた」→ queries:[\"ほっこり\",\"チル\",\"夜\",\"動物\",\"温泉\",\"lullaby\"]（catsは付けない）",
    "「他のは？」と言われたら more_songs を呼ぶ。search_songs を呼び直さない。",
    "",
    "■ 札が出たあとの喋り方",
    "4枚出したら全部を読み上げない。1〜2枚だけ名前を出して、短く一言そえる。",
    "最後に「気になるのがあったら、札を押してみてください」と、押せることを伝える。",
    "最初のひとことは短く迎える。「いらっしゃい。今日はどんな気分で来られました？」のように。",
  ].join("\n");

  const TOOLS = [
    { type: "function", name: "search_songs",
      description: "ごきげん補給所の棚を実際に引く。音楽だけでなく、動画・食べもの・動物・旅・ことば・笑いも入っている。ここが返したものだけが口に出してよいもの。4枚の札が画面にも出る。",
      parameters: { type: "object", properties: {
        queries: { type: "array", items: { type: "string" },
          description: "探す手がかり。名前・気分・ジャンル語を5〜10個。日本語と英語をまぜてよい。" },
        cats: { type: "array", items: { type: "string" },
          description: "絞りたいときだけ。music / video / food / animal / travel / word / laugh" },
        label: { type: "string", description: "この4枚につける短い見出し。例：しずかな夜に" },
      }, required: ["queries"] } },
    { type: "function", name: "more_songs",
      description: "さっきと同じ気分のまま、次の4枚を出す。「他のは？」と言われたらこれ。",
      parameters: { type: "object", properties: {} } },
  ];

  const MODELS = ["gpt-realtime-2.1", "gpt-realtime", "gpt-realtime-2.1-mini"];

  /* ══════════════════════════════════════════════════════════════
     4. 組み立て
     ══════════════════════════════════════════════════════════════ */

  function boot(opt) {
    const el = {
      cards: $("cards"), empty: $("empty"), more: $("more"), tray: $("trayTitle"),
      log: $("log"), state: $("state"), start: $("start"), stop: $("stop"),
      key: $("key"), voices: $("voices"), meter: $("meter"), stat: $("catStat"),
    };
    const SAVED = "tamago_openai_key";
    try { const k = localStorage.getItem(SAVED); if (k) el.key.value = k; } catch (e) {}

    const face = opt.face || { level() {}, speaking() {} };

    function say(cls, txt) {
      if (!el.log) return;
      const d = document.createElement("div");
      d.className = "line " + cls; d.textContent = txt;
      el.log.appendChild(d); el.log.scrollTop = el.log.scrollHeight;
    }
    function setState(s) { if (el.state) el.state.textContent = s; }

    /* 4枚ずつ配る。一度出した札は二度出さない。 */
    function dealFour() {
      const take = [];
      while (take.length < 4 && pool.length) {
        const c = pool.shift();
        if (shown.has(c.key)) continue;
        shown.add(c.key); take.push(c);
      }
      el.cards.innerHTML = "";
      if (take.length) {
        el.empty.style.display = "none";
        for (const c of take) el.cards.appendChild(card(c));
      } else {
        el.empty.style.display = "block";
      }
      el.more.disabled = pool.length === 0;
      if (el.tray) {
        el.tray.textContent = take.length
          ? (poolLabel || opt.trayDefault || "どうぞ")
          : "これで打ち止めです";
      }
      return take;
    }

    async function newSearch(queries, cats, label) {
      pool = await search(queries, cats);
      poolLabel = label || "";
      if (el.stat && shelf.head) {
        el.stat.textContent = "曲 " + shelf.head.n.toLocaleString() + "件 ＋ 音楽以外の種 "
          + (shelf.seeds || []).length + "件";
      }
      return dealFour();
    }

    el.more.addEventListener("click", () => {
      const got = dealFour();
      tell(got.length
        ? "お客さんが自分で「他を見せて」を押しました。いま出ている4枚はこれです："
          + got.map((c) => "「" + c.title + "」").join("、") + "。短く一言そえてください。"
        : "お客さんが「他を見せて」を押しましたが、もう在庫がありません。別の気分を聞いてみてください。");
    });

    // 声をかける前でも棚は見られる（会話の前に重いものは読まない＝索引だけ）
    if (el.empty) {
      const peek = document.createElement("button");
      peek.type = "button"; peek.className = "peek";
      peek.textContent = "先に棚を覗く";
      peek.addEventListener("click", () => newSearch(["ごきげん", "ほっこり", "夜", "動物", "カレー", "旅"], null, "今日の棚から"));
      el.empty.appendChild(peek);
    }

    /* ── つなぐ ───────────────────────────────── */
    let pc = null, dc = null, mic = null, audioEl = null, ac = null, analyser = null;
    let startedAt = 0, meterTimer = 0;
    const handled = new Set();

    function tell(text) {
      if (!dc || dc.readyState !== "open") return;
      dc.send(JSON.stringify({ type: "conversation.item.create",
        item: { type: "message", role: "system", content: [{ type: "input_text", text: text }] } }));
      dc.send(JSON.stringify({ type: "response.create" }));
    }

    function sessionConfig(voice) {
      return { type: "realtime", instructions: INSTRUCTIONS, tools: TOOLS, tool_choice: "auto",
        audio: { input: { turn_detection: { type: "server_vad", threshold: 0.5,
                    prefix_padding_ms: 300, silence_duration_ms: 600,
                    create_response: true, interrupt_response: true },
                  transcription: { model: "whisper-1" } },
                 output: { voice: voice } } };
    }

    async function mint(sk, voice, model) {
      const cfg = sessionConfig(voice); cfg.model = model;
      const r = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
        method: "POST",
        headers: { Authorization: "Bearer " + sk, "Content-Type": "application/json" },
        body: JSON.stringify({ session: cfg }),
      });
      if (!r.ok) throw new Error("client_secrets " + r.status + ": " + (await r.text()).slice(0, 160));
      const j = await r.json();
      return j.value || (j.client_secret && j.client_secret.value);
    }

    function startMeter() {
      startedAt = Date.now();
      clearInterval(meterTimer);
      meterTimer = setInterval(() => {
        if (!el.meter) return;
        const sec = (Date.now() - startedAt) / 1000;
        el.meter.textContent = "お話し中 " + Math.floor(sec / 60) + "分"
          + String(Math.floor(sec % 60)).padStart(2, "0") + "秒　（めやす 約"
          + (sec / 60 * 47).toFixed(0) + "円）";
      }, 1000);
    }

    async function runTool(name, argsRaw, callId) {
      let args = {}; try { args = JSON.parse(argsRaw || "{}"); } catch (e) {}
      let got = [];
      try {
        if (name === "search_songs") got = await newSearch(args.queries || [], args.cats || null, args.label || "");
        else if (name === "more_songs") got = dealFour();
      } catch (e) { got = []; say("sys", "棚を引けませんでした：" + e.message); }

      const payload = got.length ? {
        ok: true, count: got.length, rest: pool.length,
        cards: got.map((c) => ({ title: c.title, kind: CAT_LABEL[c.cat], note: c.sub, url: c.url })),
        note: "この札だけが実在する。ここに無い名前を口に出さないこと。札は画面に出し終えた。",
      } : {
        ok: false, count: 0, rest: 0,
        note: "棚に見つからなかった。別の手がかりで呼び直すか、正直に無いと伝えること。名前を作らないこと。",
      };
      dc.send(JSON.stringify({ type: "conversation.item.create",
        item: { type: "function_call_output", call_id: callId, output: JSON.stringify(payload) } }));
      dc.send(JSON.stringify({ type: "response.create" }));
    }

    let buf = "";
    function onEvent(raw) {
      let ev; try { ev = JSON.parse(raw); } catch (e) { return; }
      switch (ev.type) {
        case "error": say("sys", "エラー：" + ((ev.error && ev.error.message) || "不明")); break;
        case "input_audio_buffer.speech_started": face.speaking(false); setState(opt.stateListening); break;
        case "output_audio_buffer.started":
        case "response.output_audio.delta": face.speaking(true); setState(opt.stateTalking); break;
        case "response.output_audio_transcript.delta": buf += ev.delta || ""; break;
        case "response.output_audio_transcript.done": say("her", ev.transcript || buf); buf = ""; break;
        case "conversation.item.input_audio_transcription.completed":
          if (ev.transcript) say("me", ev.transcript); break;
        case "response.function_call_arguments.done":
          if (ev.call_id && !handled.has(ev.call_id)) { handled.add(ev.call_id); runTool(ev.name, ev.arguments, ev.call_id); }
          break;
        case "response.output_item.done":
          if (ev.item && ev.item.type === "function_call" && ev.item.call_id && !handled.has(ev.item.call_id)) {
            handled.add(ev.item.call_id);
            runTool(ev.item.name, ev.item.arguments, ev.item.call_id);
          }
          break;
        case "response.done": face.speaking(false); setState(opt.stateListening); break;
      }
    }

    function close() {
      try { dc && dc.close(); } catch (e) {}
      try { pc && pc.close(); } catch (e) {}
      if (mic) mic.getTracks().forEach((t) => t.stop());
      if (audioEl) audioEl.remove();
      dc = pc = mic = audioEl = null; analyser = null;
      face.speaking(false); face.attach(null);
      clearInterval(meterTimer);
      document.body.classList.remove("talking");
    }

    async function connect() {
      const sk = (el.key.value || "").trim();
      if (!sk) {
        say("sys", "まだ店の鍵が入っていません。いちばん下の「店の裏（開発用）」から入れてください。");
        setState(opt.stateNoKey || "準備ができていません");
        const d = document.querySelector("details.urakuchi");
        if (d) { d.open = true; el.key.focus(); }
        return;
      }
      try { localStorage.setItem(SAVED, sk); } catch (e) {}
      const vEl = document.querySelector("input[name=v]:checked");
      const voice = vEl ? vEl.value : "marin";

      el.start.disabled = true;
      setState(opt.stateConnecting);
      document.body.classList.add("talking");
      if (el.log) el.log.innerHTML = "";
      shown.clear(); pool = [];
      shelf.load().catch(() => {});

      let token = sk, viaEk = false, model = MODELS[0], lastErr = "";
      for (const m of MODELS) {
        try { token = await mint(sk, voice, m); viaEk = true; model = m; break; }
        catch (e) { lastErr = e.message; }
      }

      try {
        pc = new RTCPeerConnection();
        audioEl = document.createElement("audio");
        audioEl.autoplay = true; audioEl.style.display = "none";
        document.body.appendChild(audioEl);
        pc.ontrack = (ev) => {
          if (!ev.streams[0]) return;
          audioEl.srcObject = ev.streams[0];
          try {
            ac = ac || new (window.AudioContext || window.webkitAudioContext)();
            const src = ac.createMediaStreamSource(ev.streams[0]);
            analyser = ac.createAnalyser();
            analyser.fftSize = 512; analyser.smoothingTimeConstant = 0.4;
            src.connect(analyser);
            face.attach(analyser);
            if (ac.state === "suspended") ac.resume();
          } catch (e) {}
        };

        mic = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
        pc.addTrack(mic.getAudioTracks()[0], mic);

        dc = pc.createDataChannel("oai-events");
        dc.addEventListener("open", () => {
          setState(opt.stateListening);
          startMeter();
          dc.send(JSON.stringify({ type: "session.update", session: sessionConfig(voice) }));
          setTimeout(() => dc.send(JSON.stringify({ type: "response.create" })), 350);
        });
        dc.addEventListener("close", () => { setState(opt.stateClosed); clearInterval(meterTimer); });
        dc.addEventListener("message", (e) => onEvent(e.data));

        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);

        const tryModels = viaEk ? [model] : MODELS;
        let answer = null, err = "";
        for (const m of tryModels) {
          const r = await fetch("https://api.openai.com/v1/realtime/calls?model=" + encodeURIComponent(m), {
            method: "POST", body: offer.sdp,
            headers: { Authorization: "Bearer " + token, "Content-Type": "application/sdp" } });
          if (r.ok) { answer = await r.text(); model = m; break; }
          err = "calls " + r.status + "（" + m + "）: " + (await r.text()).slice(0, 200);
          if (r.status === 401 || r.status === 403) break;
        }
        if (!answer) throw new Error(err || lastErr || "つながりませんでした");
        await pc.setRemoteDescription({ type: "answer", sdp: answer });
      } catch (e) {
        say("sys", "つながりませんでした → " + e.message);
        setState(opt.stateFailed); el.start.disabled = false; close();
      }
    }

    el.start.addEventListener("click", connect);
    if (el.stop) el.stop.addEventListener("click", () => {
      close(); setState(opt.stateStopped); el.start.disabled = false;
    });

    // 声は店の裏に置く（客前に生のモデル名を出さない）
    const VOICES = [["marin", "marin"], ["cedar", "cedar"], ["alloy", "alloy"],
      ["ash", "ash"], ["ballad", "ballad"], ["coral", "coral"], ["echo", "echo"],
      ["sage", "sage"], ["shimmer", "shimmer"], ["verse", "verse"]];
    if (el.voices) {
      VOICES.forEach(([v, label], i) => {
        const l = document.createElement("label");
        l.innerHTML = '<input type="radio" name="v" value="' + v + '"' + (i === 0 ? " checked" : "")
          + '><span>' + label + "</span>";
        el.voices.appendChild(l);
      });
    }
  }

  global.Concierge = { boot: boot, CAT_LABEL: CAT_LABEL, MOTIF: MOTIF };
})(window);
