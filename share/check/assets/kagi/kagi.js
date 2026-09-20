/* ══════════════════════════════════════════════════════════════════
   たまごの鍵 — 全ページ共通の1本（969番）
   ------------------------------------------------------------------
   なぜ作ったか（2026-09-20 実測）
     たまごさんがスマホで 958番の「見た目の版」を開いて「話す」を押したら
     「Geminiの鍵が空です」だけが出て、鍵を入れる欄がどこにも出なかった。
     調べたら、鍵の欄は ?dev=1 を付けたときしか出ない作りだった。
     つまり「鍵が無い」のではなく「鍵を入れる場所が無い」のが本当の原因。

   この1本が引き受けること
     1. 保存名は KEY ただ1つ。ページ番号が増えても名前は増やさない。
     2. 昔の名前に鍵が残っていたら、黙って新しい名前へ引き継ぐ。
        （たまごさんに入れ直させない）
     3. 鍵が空のときだけ、入り口を出す。入っているときは何も出さない。
        （お客さんの前に鍵の欄を出さない、という約束を守るため）
     4. ページの中に #gkey があれば、そこへも同じ鍵を入れておく。
        だから既にあるページの中身は書き替えなくていい。

   新しい番号のページを作るときは、この1行を head に入れるだけでいい。
     <script src="assets/kagi/kagi.js"></script>
   （share/check の外に置くページなら ../ の数だけ直す）

   ★この台本は鍵の値を画面にもコンソールにも出さない。移すだけ。
   ══════════════════════════════════════════════════════════════════ */
(function (global) {
  "use strict";

  var KEY = "tamago_gemini_key";          /* ここが唯一の保存名 */

  /* 昔うっかり作られたかもしれない名前。見つけたら KEY へ移す。 */
  var OLD_NAMES = [
    "tamago_gemini_apikey", "tamago_gemini_API_KEY", "tamago_gkey",
    "tamagoGeminiKey", "tamago_google_key", "tamago_googleai_key",
    "gemini_key", "geminiKey", "GEMINI_API_KEY", "google_api_key",
    "tamago_gemini_key_958", "tamago_gemini_key_959", "tamago_gemini_key_966"
  ];

  function box() { try { return global.localStorage; } catch (e) { return null; } }

  function get() {
    var s = box(); if (!s) return "";
    try { return (s.getItem(KEY) || "").trim(); } catch (e) { return ""; }
  }

  function set(v) {
    var s = box(); if (!s) return false;
    try {
      v = String(v == null ? "" : v).trim();
      if (v) s.setItem(KEY, v); else s.removeItem(KEY);
      return true;
    } catch (e) { return false; }
  }

  /* ── 引き継ぎ。ここだけが古い置き場を触る ───────────────── */
  function hikitsugi() {
    if (get()) return;
    var s = box(); if (!s) return;

    for (var i = 0; i < OLD_NAMES.length; i++) {
      try {
        var v = (s.getItem(OLD_NAMES[i]) || "").trim();
        if (v) { s.setItem(KEY, v); return; }
      } catch (e) { /* 触れないものは飛ばす */ }
    }

    /* 名前を知らない置き忘れも拾う。
       Google の鍵は AIza で始まる決まった形をしている。
       その形のものが「ちょうど1つだけ」あるときに限って引き継ぐ。
       2つ以上あるときは、どれが本物か分からないので何もしない。 */
    try {
      var hit = null, n = 0;
      for (var j = 0; j < s.length; j++) {
        var k = s.key(j); if (!k || k === KEY) continue;
        var val = (s.getItem(k) || "").trim();
        if (/^AIza[A-Za-z0-9_\-]{20,}$/.test(val)) { hit = val; n++; }
      }
      if (n === 1 && hit) s.setItem(KEY, hit);
    } catch (e) { /* 何もしない */ }
  }
  hikitsugi();

  /* ── ページの中の #gkey へ同じ鍵を流し込む ───────────────── */
  function sync() {
    var el = document.getElementById("gkey");
    if (!el) return false;
    var k = get();
    if (k && el.value !== k) el.value = k;
    return true;
  }

  /* ── 入り口（鍵が空のときだけ出る） ─────────────────────── */
  var PANEL_ID = "tmg-kagi";
  var mounted = false;

  function style() {
    if (document.getElementById("tmg-kagi-css")) return;
    var s = document.createElement("style");
    s.id = "tmg-kagi-css";
    s.textContent = [
      "#" + PANEL_ID + "{position:fixed;inset:auto 0 0 0;z-index:100000;",
      "  background:#1b1713;color:#f3ece0;padding:16px 16px calc(16px + env(safe-area-inset-bottom));",
      "  box-shadow:0 -14px 44px rgba(0,0,0,.4);",
      "  font:14px/1.7 -apple-system,BlinkMacSystemFont,'Hiragino Sans',system-ui,sans-serif}",
      "#" + PANEL_ID + " .in{max-width:520px;margin:0 auto}",
      "#" + PANEL_ID + " p{margin:0 0 10px;font-size:13px;line-height:1.8;opacity:.9}",
      "#" + PANEL_ID + " input{width:100%;box-sizing:border-box;padding:14px 12px;font-size:16px;",
      "  border:1px solid rgba(243,236,224,.35);border-radius:10px;",
      "  background:rgba(243,236,224,.06);color:#f3ece0;-webkit-appearance:none}",
      "#" + PANEL_ID + " input::placeholder{color:rgba(243,236,224,.45)}",
      "#" + PANEL_ID + " .row{display:flex;gap:10px;margin-top:12px}",
      "#" + PANEL_ID + " button{flex:1;min-height:48px;font-size:15px;font-weight:600;",
      "  border-radius:999px;border:1px solid rgba(243,236,224,.35);",
      "  background:transparent;color:#f3ece0;cursor:pointer;-webkit-appearance:none}",
      "#" + PANEL_ID + " button.b-save{flex:2;background:#f3ece0;color:#1b1713;border-color:#f3ece0}",
      "#" + PANEL_ID + " .msg{margin:10px 0 0;font-size:12px;min-height:1.2em;color:#ffd7a8}",
      "@media (max-width:380px){#" + PANEL_ID + "{padding:13px 12px calc(13px + env(safe-area-inset-bottom))}",
      "  #" + PANEL_ID + " p{font-size:12px}}"
    ].join("\n");
    document.head.appendChild(s);
  }

  function mount() {
    if (mounted || document.getElementById(PANEL_ID)) return document.getElementById(PANEL_ID);
    style();
    var d = document.createElement("div");
    d.id = PANEL_ID;
    d.setAttribute("role", "dialog");
    d.setAttribute("aria-label", "Geminiの鍵");
    d.innerHTML =
      '<div class="in">' +
      '<p>話すのに Gemini の鍵が要ります。1回入れたら、この端末では次から聞きません。' +
      '番号のちがうページでも、もう入れ直さなくて大丈夫です。</p>' +
      '<input id="tmg-kagi-in" type="password" inputmode="text" autocomplete="off" ' +
      'autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="AIza… を貼る">' +
      '<div class="row">' +
      '<button type="button" class="b-save" id="tmg-kagi-save">入れて、話す</button>' +
      '<button type="button" class="b-close" id="tmg-kagi-close">あとで</button>' +
      '</div><p class="msg" id="tmg-kagi-msg"></p></div>';
    document.body.appendChild(d);
    mounted = true;

    var inp = d.querySelector("#tmg-kagi-in");
    var msg = d.querySelector("#tmg-kagi-msg");

    function save() {
      var v = (inp.value || "").trim();
      if (!v) { msg.textContent = "まだ空です。鍵を貼ってください。"; inp.focus(); return; }
      if (!/^AIza/.test(v)) { msg.textContent = "Google の鍵は AIza で始まります。貼り直してください。"; return; }
      if (!set(v)) { msg.textContent = "この端末は保存を断っています（プライベートモードかもしれません）。"; return; }
      inp.value = "";
      sync();
      hide();
      try {
        document.dispatchEvent(new CustomEvent("tamago-kagi-set"));
      } catch (e) { /* 古い端末は飛ばす */ }
      /* 入れた直後にそのまま話し始める。押して何も起きない、を作らない。 */
      var go = document.getElementById("go");
      if (go && !go.disabled) { try { go.click(); } catch (e) { } }
    }

    d.querySelector("#tmg-kagi-save").addEventListener("click", save);
    d.querySelector("#tmg-kagi-close").addEventListener("click", hide);
    inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); save(); } });
    return d;
  }

  function show() {
    var d = mount();
    if (!d) return;
    d.style.display = "block";
    var inp = d.querySelector("#tmg-kagi-in");
    if (inp) { try { inp.focus(); } catch (e) { } }
  }

  function hide() {
    var d = document.getElementById(PANEL_ID);
    if (d) d.style.display = "none";
  }

  /* 鍵が要る場面で呼ぶ。鍵があれば返す。無ければ入り口を出して "" を返す。 */
  function require_() {
    var k = get();
    if (k) return k;
    show();
    return "";
  }

  /* 開いた瞬間には何も出さない（お客さんの前に鍵の欄を出さない）。
     「話す」を押したとき、鍵が無ければそこで初めて出る。 */
  function start() { sync(); }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
  /* 後から #gkey を作るページ（958の配線）にも届くよう、もう一度だけ流す */
  global.addEventListener("load", function () { sync(); });

  global.TamagoKagi = {
    name: KEY,
    get: get,
    set: set,
    has: function () { return !!get(); },
    ask: show,
    hide: hide,
    require: require_,
    sync: sync
  };
})(window);
