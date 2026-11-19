/* 431番 — 正本（Issue #431 の 02 / 08 の HTML・CSS）と、947番で動いている案内人をつなぐ配線だけ。
 *
 * ★この台本は「絵を描く」ことを一切しない。
 *   ・正本のDOMは作らない。既にあるものを **ひな形として複製する** だけ。
 *   ・正本のクラス名・並び・余白・文字・色・比率に触れない。
 *   ・足りない部品（鍵・声・実測・再生窓）は、正本の外側に置く。鍵は客前に出さない。
 */
(function (global) {
  "use strict";
  var DEV = /[?&]dev=1/.test(location.search);
  var shell = document.querySelector(".prototype-shell");
  if (!shell) return;

  /* ── 1. 正本からひな形を採る（触る前に採る） ───────────────── */
  var grid = shell.querySelector('[data-slot="recommendation-grid"]');
  var conv = shell.querySelector('[data-slot="conversation"]');
  var moreBtn = shell.querySelector('[data-action="more"]');
  var talkBtn = shell.querySelector('[data-action="talk"]');
  var avatar = shell.querySelector('[data-slot="concierge-avatar"]');

  var cardTpl = grid ? grid.querySelector('[data-slot="recommendation-card"]') : null;
  cardTpl = cardTpl ? cardTpl.cloneNode(true) : null;

  var rowHer = null, rowMe = null;
  if (conv) {
    var rows = conv.querySelectorAll(".conversation-row");
    for (var i = 0; i < rows.length; i++) {
      var who = rows[i].querySelector(".who");
      var isMe = who && who.classList.contains("user");
      if (isMe && !rowMe) rowMe = rows[i].cloneNode(true);
      if (!isMe && !rowHer) rowHer = rows[i].cloneNode(true);
    }
  }
  if (!rowHer && rowMe) rowHer = rowMe.cloneNode(true);

  /* ── 2. 947番が名前で呼ぶ部品に、正本の器を割り当てる ─────────── */
  if (grid) grid.id = "cards";
  if (conv) conv.id = "log";
  if (moreBtn) moreBtn.id = "more";

  /* ── 3. 正本に無い部品は、正本の外に足す（隠す） ──────────────── */
  var css = document.createElement("style");
  css.textContent = [
    /* 裏口。鍵・声・実測はここ。?dev=1 のときしか出さない（947側が hidden を外しても出ない） */
    ".tmg431-ura{display:none}",
    ".tmg431-ura.dev{display:block;max-width:900px;margin:40px auto 60px;padding:0 24px;",
    "  font:12px/1.9 system-ui,sans-serif;color:#8b8375}",
    ".tmg431-ura input{width:100%;padding:8px 10px;margin:4px 0;border:1px solid #ddd6c6;border-radius:6px}",
    ".tmg431-ura label{display:inline-block;margin:2px 8px 2px 0}",
    ".tmg431-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    /* その場の再生窓。ページの組版の上に浮かせる＝誌面の余白や比率に触らない */
    ".tmg431-player{position:fixed;inset:auto 0 0 0;z-index:9999;display:none;",
    "  background:rgba(22,19,15,.96);color:#f3ece0;padding:14px;",
    "  box-shadow:0 -12px 40px rgba(0,0,0,.35)}",
    ".tmg431-player.on{display:block}",
    ".tmg431-player .in{max-width:780px;margin:0 auto}",
    ".tmg431-player .frame{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:8px;overflow:hidden}",
    ".tmg431-player .frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}",
    ".tmg431-player .pt{margin:10px 0 0;font:600 15px/1.5 system-ui,sans-serif}",
    ".tmg431-player .pa{margin:2px 0 0;font:12px/1.6 system-ui,sans-serif;opacity:.7}",
    ".tmg431-player .ask{margin:10px 0 8px;font:12px/1.7 system-ui,sans-serif;opacity:.85}",
    ".tmg431-player button{font:12px system-ui,sans-serif;margin-right:8px;padding:9px 14px;",
    "  border-radius:999px;border:1px solid rgba(243,236,224,.35);background:transparent;color:#f3ece0;cursor:pointer}",
    ".tmg431-player button.b-big{background:#f3ece0;color:#1b1713;border-color:#f3ece0}",
    /* 口が動く顔。正本の似顔絵と同じ枠にぴったり重ねる。話していないときは出ない */
    '[data-slot="concierge-avatar"]{position:relative}',
    ".tmg431-face{position:absolute;inset:0;width:100%;height:100%;opacity:0;",
    "  transition:opacity .45s ease;pointer-events:none}",
    "body.tmg431-talking .tmg431-face{opacity:1}",
    "body.tmg431-talking [data-slot=\"concierge-avatar\"] img{opacity:0;transition:opacity .45s ease}",
  ].join("\n");
  document.head.appendChild(css);

  function mk(tag, attrs, parent) {
    var e = document.createElement(tag);
    for (var k in attrs) if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]);
    (parent || document.body).appendChild(e);
    return e;
  }

  /* 隠し部品（947番が textContent を書き込むだけのもの） */
  var hid = mk("div", { "class": "tmg431-hidden" });
  ["state", "meter", "lag", "empty", "trayTitle", "catStat"].forEach(function (id) { mk("div", { id: id }, hid); });
  var goEl = mk("button", { id: "go", type: "button" }, hid);
  var stopEl = mk("button", { id: "stop", type: "button" }, hid);
  mk("a", { id: "devLink", href: "#" }, hid);

  /* 再生窓（押すとその場で鳴る／大きい画面で見ますか） */
  var pl = mk("div", { id: "player", "class": "tmg431-player" });
  pl.innerHTML =
    '<div class="in"><div class="frame" id="frame"></div>' +
    '<p class="pt" id="pTitle"></p><p class="pa" id="pArtist"></p>' +
    '<p class="ask">大きい画面で見ますか？　押さなければ、ここで聴いたままで大丈夫です。</p>' +
    '<div class="prow"><button class="b-big" id="pBig" type="button">大きい画面で見る</button>' +
    '<button class="b-talk" id="pTalk" type="button">止めて案内人と話す</button>' +
    '<button class="b-close" id="pClose" type="button">閉じる</button></div></div>';
  /* 947側は classList.add("on") で開ける。CSSはこちらで持っている */

  /* 裏口（鍵・声・engine・実測）。?dev=1 以外では CSS で殺してある */
  var ura = mk("details", { id: "settings", "class": "tmg431-ura" + (DEV ? " dev" : "") });
  ura.innerHTML =
    "<summary>お店の人の設定（お客さんは触らなくて大丈夫です）</summary>" +
    '<div class="mode" id="mode"></div><div class="chips" id="engines"></div>' +
    '<div id="engineNote"></div><div class="chips" id="voices"></div>' +
    '<input id="key" type="password" placeholder="sk-…（OpenAI）" autocomplete="off" spellcheck="false">' +
    '<input id="xkey" type="password" placeholder="xai-…（xAI）" autocomplete="off" spellcheck="false">' +
    '<table class="cost" id="costTable"></table>';

  /* 口が動く顔（947番と同じ canvas を、正本の似顔絵の枠に重ねる） */
  if (avatar) {
    var cv = document.createElement("canvas");
    cv.id = "face"; cv.width = 680; cv.height = 680; cv.className = "tmg431-face";
    avatar.appendChild(cv);
  } else {
    mk("canvas", { id: "face", width: "680", height: "680", "class": "tmg431-hidden" }, hid);
  }

  /* ── 4. 正本の「押すところ」を、隠しボタンにつなぐ ─────────────── */
  var trigger = talkBtn || avatar;           /* 02番には data-action="talk" が無いので似顔絵で受ける */
  if (trigger) {
    if (trigger === avatar) trigger.style.cursor = "pointer";
    trigger.addEventListener("click", function (e) {
      e.preventDefault();
      if (Seihon.engine && Seihon.engine.live && Seihon.engine.live()) stopEl.click();
      else goEl.click();
    });
  }

  /* 「他を見せて」は、声をかける前でも棚を見せる（先に棚を覗く） */
  if (moreBtn) {
    moreBtn.addEventListener("click", function () {
      var e = Seihon.engine;
      if (!e || !e.newSearch) return;
      if (e.live && e.live()) return;                 /* 話している間は947側にまかせる */
      if (e.hasPool && e.hasPool()) return;
      e.newSearch({ mood: ["ごきげん", "ほっこり", "夜", "動物", "カレー", "旅", "笑い"] }, "今日の棚から");
    }, true);
  }

  /* ── 5. 画面への出し方（ここだけが「見せ方」を持つ） ─────────────── */
  var EN = { music: "MUSIC", video: "VISUAL", food: "LIFESTYLE", animal: "CREATURES",
             travel: "JOURNEY", word: "ARTICLE", laugh: "COMEDY" };
  var JA = { music: "音楽", video: "動画", food: "食べもの", animal: "動物",
             travel: "旅", word: "ことば", laugh: "笑い" };
  /* 写真が来なかったときの下地。正本のCSSに既にある .thumb-* しか使わない */
  var THUMB = { music: "thumb-piano", video: "thumb-leaves", food: "thumb-cup",
                animal: "thumb-cat", travel: "thumb-travel", word: "thumb-sky",
                laugh: "thumb-plant" };

  var Seihon = {
    engine: null,
    say: function (cls, txt) {
      if (!conv || !rowHer) return;
      var tpl = cls === "me" ? (rowMe || rowHer) : rowHer;
      var row = tpl.cloneNode(true);
      var p = row.querySelector(".say");
      if (p) p.textContent = txt;
      if (cls === "sys") {
        var w = row.querySelector(".who");
        if (w) w.textContent = "お知らせ";
        row.setAttribute("data-sys", "1");
      }
      conv.appendChild(row);
      /* 勝手にページを動かさない（誌面の見え方に手を出さない）。
         画面の外に出たときだけ、そっと寄せる。 */
      try {
        var r = row.getBoundingClientRect();
        if (r.bottom > (window.innerHeight || 0)) row.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } catch (e) {}
    },
    drawCards: function (list, onPick) {
      if (!grid || !cardTpl) return;
      grid.innerHTML = "";
      for (var i = 0; i < list.length; i++) {
        (function (c, n) {
          var el = cardTpl.cloneNode(true);
          var kind = c.kind || "music";
          el.setAttribute("data-category", kind);
          if (c.url) el.setAttribute("href", c.url);
          var no = el.querySelector(".rec-no");
          if (no) no.textContent = ("0" + (n + 1)).slice(-2) + " / " + (EN[kind] || "PICK");
          var t = el.querySelector(".rec-title");
          if (t) t.textContent = c.title || "";
          var copy = el.querySelector(".rec-copy");
          if (copy) copy.textContent = c.sub || "";
          /* 写真は、正本が決めた枠・比率の中に敷くだけ（枠には触らない） */
          var box = el.querySelector(".cover") || el.querySelector(".rec-media");
          /* 下地は正本のCSSが持っている .thumb-* から選ぶだけ（新しい色を作らない） */
          if (box && THUMB[kind]) {
            box.className = box.className.replace(/\bthumb-[a-z]+\b/g, "").trim() + " " + THUMB[kind];
          }
          if (box && c.thumb) {
            box.style.backgroundImage = "url('" + c.thumb + "')";
            box.style.backgroundSize = "cover";
            box.style.backgroundPosition = "center";
          }
          var meta = el.querySelector(".rec-meta");
          if (meta) {
            var sp = meta.querySelectorAll("span");
            if (sp[0]) sp[0].textContent = JA[kind] || "";
            if (sp[1]) sp[1].textContent = c.yt ? "ここで聴ける" : "ひらく";
          }
          el.addEventListener("click", function (ev) { ev.preventDefault(); onPick(c); });
          grid.appendChild(el);
        })(list[i], i);
      }
    },
  };
  global.Seihon = Seihon;

  /* 話している間だけ、顔に切り替える */
  var obs = new MutationObserver(function () {
    var live = Seihon.engine && Seihon.engine.live && Seihon.engine.live();
    document.body.classList.toggle("tmg431-talking", !!live);
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });
  setInterval(function () {
    var live = Seihon.engine && Seihon.engine.live && Seihon.engine.live();
    document.body.classList.toggle("tmg431-talking", !!live);
  }, 700);
})(window);
