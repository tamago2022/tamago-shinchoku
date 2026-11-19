/* 958番（Google版・実際に話せた方）を、431番の正本（02 / 08 の HTML・CSS）の上で動かす配線だけ。
 *
 * ★この台本は「絵を描く」ことを一切しない。
 *   ・正本のDOMは作らない。既にあるものを ひな形として複製する だけ。
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

  /* ── 2. 958番が名前で呼ぶ部品に、正本の器を割り当てる ─────────── */
  if (grid) grid.id = "cards";
  if (conv) conv.id = "log";
  if (moreBtn) moreBtn.id = "more";

  /* ── 3. 正本に無い部品は、正本の外に足す（隠す） ──────────────── */
  var css = document.createElement("style");
  css.textContent = [
    ".tmg958-ura{display:none}",
    ".tmg958-ura.dev{display:block;max-width:900px;margin:40px auto 60px;padding:0 24px;",
    "  font:12px/1.9 system-ui,sans-serif;color:#8b8375}",
    ".tmg958-ura input{width:100%;padding:8px 10px;margin:4px 0;border:1px solid #ddd6c6;border-radius:6px}",
    ".tmg958-ura label{display:inline-block;margin:2px 8px 2px 0}",
    ".tmg958-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}",
    ".tmg958-player{position:fixed;inset:auto 0 0 0;z-index:9999;display:none;",
    "  background:rgba(22,19,15,.96);color:#f3ece0;padding:14px;",
    "  box-shadow:0 -12px 40px rgba(0,0,0,.35)}",
    ".tmg958-player.on{display:block}",
    ".tmg958-player .in{max-width:780px;margin:0 auto}",
    ".tmg958-player .frame{position:relative;width:100%;aspect-ratio:16/9;background:#000;border-radius:8px;overflow:hidden}",
    ".tmg958-player .frame iframe{position:absolute;inset:0;width:100%;height:100%;border:0}",
    ".tmg958-player .pt{margin:10px 0 0;font:600 15px/1.5 system-ui,sans-serif}",
    ".tmg958-player .pa{margin:2px 0 0;font:12px/1.6 system-ui,sans-serif;opacity:.7}",
    ".tmg958-player .ask{margin:10px 0 8px;font:12px/1.7 system-ui,sans-serif;opacity:.85}",
    ".tmg958-player button{font:12px system-ui,sans-serif;margin-right:8px;padding:9px 14px;",
    "  border-radius:999px;border:1px solid rgba(243,236,224,.35);background:transparent;color:#f3ece0;cursor:pointer}",
    ".tmg958-player button.b-big{background:#f3ece0;color:#1b1713;border-color:#f3ece0}",
    /* 口が動く顔。正本の似顔絵と同じ枠にぴったり重ねる。話していないときは出ない */
    '[data-slot="concierge-avatar"]{position:relative}',
    "#tamako{position:absolute;inset:0;width:100%;height:100%;opacity:0;",
    "  transition:opacity .45s ease;pointer-events:none;display:flex;align-items:flex-end;justify-content:center}",
    "#tamako svg{width:100%;height:100%;overflow:visible}",
    "body.tmg958-talking #tamako{opacity:1}",
    "body.tmg958-talking [data-slot=\"concierge-avatar\"] img{opacity:0;transition:opacity .45s ease}",
    /* ★970：会話は1発言1行。名前は本文の横に小さく、縦は詰める。
       （正本の「左＝だれ／右＝ことば」はそのまま。余白と字の大きさだけ寄せた） */
    ".conversation-row{padding:12px 18px;gap:12px;align-items:baseline}",
    ".conversation-row .say{line-height:1.7}",
    ".conversation-row[data-sys=\"1\"] .who{opacity:.55;font-weight:600}",
    ".conversation-row[data-sys=\"1\"] .say{opacity:.62;font-size:12px}",
    "@media (max-width:780px){",
    "  .conversation-row{grid-template-columns:54px 1fr;gap:8px;padding:7px 12px}",
    "  .conversation-row + .conversation-row{border-top:1px solid rgba(80,68,53,.10)}",
    "  .conversation-row .say{font-size:12.5px;line-height:1.55;letter-spacing:.01em}",
    "  .conversation-row .who{font-size:9px;line-height:1.55;white-space:nowrap}",
    "  .conversation-row[data-sys=\"1\"] .say{font-size:11px}",
    "}",
  ].join("\n");
  document.head.appendChild(css);

  function mk(tag, attrs, parent) {
    var e = document.createElement(tag);
    for (var k in attrs) if (k === "text") e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]);
    (parent || document.body).appendChild(e);
    return e;
  }

  /* 隠し部品（958番が textContent を書き込むだけのもの） */
  var hid = mk("div", { "class": "tmg958-hidden" });
  ["state", "meter", "empty", "trayTitle"].forEach(function (id) { mk("div", { id: id }, hid); });
  var goEl = mk("button", { id: "go", type: "button" }, hid);
  var stopEl = mk("button", { id: "stop", type: "button" }, hid);
  mk("a", { id: "devLink", href: "#" }, hid);

  /* 再生窓 */
  var pl = mk("div", { id: "player", "class": "tmg958-player" });
  pl.innerHTML =
    '<div class="in"><div class="frame" id="frame"></div>' +
    '<p class="pt" id="pTitle"></p><p class="pa" id="pArtist"></p>' +
    '<p class="ask">大きい画面で見ますか？　押さなければ、ここで聴いたままで大丈夫です。</p>' +
    '<div class="prow"><button class="b-big" id="pBig" type="button">大きい画面で見る</button>' +
    '<button class="b-talk" id="pTalk" type="button">止めて案内人と話す</button>' +
    '<button class="b-close" id="pClose" type="button">閉じる</button></div></div>';

  /* 裏口（鍵・声・実測）。?dev=1 以外では CSS で殺してある */
  var ura = mk("details", { id: "settings", "class": "tmg958-ura" + (DEV ? " dev" : "") });
  ura.innerHTML =
    "<summary>お店の人の設定（お客さんは触らなくて大丈夫です）</summary>" +
    '<input id="gkey" type="password" placeholder="AIza…（Google AI Studio）" autocomplete="off" spellcheck="false">' +
    '<div class="chips" id="models"></div><div class="chips" id="voices"></div>' +
    '<table class="cost" id="costTable"></table>';

  /* 口が動く顔（958番と同じ立ち絵を、正本の似顔絵の枠に重ねる） */
  if (avatar) mk("div", { id: "tamako" }, avatar);
  else mk("div", { id: "tamako" }, hid);

  /* ── 4. 正本の「押すところ」を、隠しボタンにつなぐ ─────────────── */
  var trigger = talkBtn || avatar;
  if (trigger) {
    if (trigger === avatar) trigger.style.cursor = "pointer";
    trigger.addEventListener("click", function (e) {
      e.preventDefault();
      if (goEl.disabled) stopEl.click(); else goEl.click();
    });
  }

  /* ── 5. 画面への出し方（ここだけが「見せ方」を持つ） ─────────────── */
  var EN = { music: "MUSIC", video: "VISUAL", food: "LIFESTYLE", animal: "CREATURES",
             travel: "JOURNEY", word: "ARTICLE", laugh: "COMEDY" };
  var JA = { music: "音楽", video: "動画", food: "食べもの", animal: "動物",
             travel: "旅", word: "ことば", laugh: "笑い" };
  var THUMB = { music: "thumb-piano", video: "thumb-leaves", food: "thumb-cup",
                animal: "thumb-cat", travel: "thumb-travel", word: "thumb-sky",
                laugh: "thumb-plant" };

  /* ★970：1回の発言＝1行。
     喋りながら届く切れ端を、そのたびに新しい行にしていたので、ひとつの台詞が
     「どんな」「ことでもお話し」「くださいね。」と3行に割れ、名前も3回出ていた。
     いまは、同じ人が喋っている間は同じ行の中で文字が増えていく（LINEと同じ）。 */
  var akiRow = null, akiCls = null;

  function yoseru(row) {
    try {
      var r = row.getBoundingClientRect();
      if (r.bottom > (window.innerHeight || 0)) row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } catch (e) {}
  }

  var Seihon = {
    say: function (cls, txt, tsuzuki) {
      if (!conv || !rowHer) return;
      txt = (txt == null ? "" : String(txt));

      /* 中身が空なら行を作らない（「---」だけの行が出ていた） */
      if (!txt.replace(/[\s　]/g, "")) return;

      /* 喋っている途中の続き＝同じ行に足す。行も名前も増やさない。 */
      if (tsuzuki && akiRow && akiCls === cls && conv.contains(akiRow)) {
        var ap = akiRow.querySelector(".say");
        if (ap) {
          var mae = ap.textContent || "";
          /* 同じ切れ端が二重に届くことがあるので、そのときは足さない */
          if (!(txt && mae.slice(-txt.length) === txt)) ap.textContent = mae + txt;
          yoseru(akiRow);
          return;
        }
      }

      /* ★969：同じお知らせを続けて2回並べない。 */
      if (cls === "sys") {
        var last = conv.lastElementChild;
        if (last && last.getAttribute("data-sys") === "1") {
          var lp = last.querySelector(".say");
          if (lp && lp.textContent === txt) return;
        }
      }

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
      akiRow = tsuzuki ? row : null;
      akiCls = tsuzuki ? cls : null;
      yoseru(row);
    },

    /* 話し終わり。次の台詞は新しい行から始める。 */
    seal: function () { akiRow = null; akiCls = null; },
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
          var box = el.querySelector(".cover") || el.querySelector(".rec-media");
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

  /* 話している間だけ、顔に切り替える（「やめる」が押せる＝話している） */
  setInterval(function () {
    document.body.classList.toggle("tmg958-talking", !!goEl.disabled);
  }, 500);
})(window);
