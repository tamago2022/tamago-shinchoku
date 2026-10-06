/* 966番 — 案内人のトーキングアバター（箱）
 *
 * ★この箱が外から受け取るのは「母音・呼吸・揺れ」の3つの数値だけ。
 *   描き方（下の draw）は丸ごと入れ替えられる。965番・960番で決めた形のまま。
 *
 * ★絵は作らない。正本（docs/design/concierge-html-css）が指している
 *   承認済み PNG（egg-concierge.png）を、そのまま層に切って使うだけ。
 *     L1 body  … egg-body.png（承認済みPNGから目と口だけを消したもの）
 *     L2 eyes  … 承認済みPNGと同じ位置・同じ色の点（瞬きで閉じる）
 *     L3 mouth … 承認済みPNGと同じ笑みの線（母音で開く）
 *   目と口の座標・色は、承認済みPNG（480×480）を実測した値。
 *
 * ★平たい2Dにしない：呼吸（縦の伸び縮み）と揺れ（傾き）を体に掛け、
 *   影は正本の drop-shadow に任せる（正本にないものを足さない）。
 *
 * API は 958/960 の Tamako.stand と同じ。差し替えても呼び出し側は変えない。
 */
(function (global) {
  "use strict";

  var SRC = 480;                       // 承認済みPNGの一辺
  /* 承認済みPNGを実測した顔の座標（480×480の中の位置） */
  var EYE_L = { x: 210.5, y: 204.5, rx: 7.2, ry: 8.0, fill: "#462c1d" };
  var EYE_R = { x: 269.5, y: 203.5, rx: 7.2, ry: 8.0, fill: "#38210f" };
  var MOUTH = { x: 240, y0: 216.5, x0: 226, x1: 254, cy: 237.5,
                w: 4.2, line: "#3b2415", hole: "#4b2417" };

  /* 母音（viseme）→ 口の［よこはば, たてはば］。958番の対応表をそのまま使う。 */
  var VIS = {
    viseme_sil: [1.00, 0.00], viseme_PP: [0.75, 0.05], viseme_FF: [0.85, 0.25],
    viseme_TH:  [0.90, 0.35], viseme_DD: [0.90, 0.45], viseme_kk: [0.95, 0.50],
    viseme_CH:  [0.80, 0.40], viseme_SS: [0.90, 0.20], viseme_nn: [0.85, 0.25],
    viseme_RR:  [0.90, 0.50], viseme_aa: [1.25, 1.00], viseme_E:  [1.35, 0.55],
    viseme_I:   [1.40, 0.30], viseme_O:  [0.85, 0.90], viseme_U:  [0.60, 0.60]
  };

  function stand(el, opt) {
    opt = opt || {};

    var rig = document.createElement("div");
    rig.className = "tmk-rig";
    var img = document.createElement("img");
    img.className = "tmk-body";
    img.src = (opt.src || "assets/966/egg-body-lit.png");
    img.alt = "ごきげん補給所の案内人";
    var cv = document.createElement("canvas");
    cv.className = "tmk-face";
    cv.setAttribute("aria-hidden", "true");
    rig.appendChild(img);
    rig.appendChild(cv);
    el.appendChild(rig);

    var ctx = cv.getContext("2d");
    var box = { w: 0, h: 0, s: 1, dx: 0, dy: 0 };

    /* 画像の実寸に canvas をぴったり重ねる。
       正本の object-fit:contain / object-position:center bottom と同じ計算をする。 */
    function fit() {
      var w = img.clientWidth, h = img.clientHeight;
      if (!w || !h) return;
      var dpr = Math.min(2, global.devicePixelRatio || 1);
      cv.style.width = w + "px"; cv.style.height = h + "px";
      cv.style.left = img.offsetLeft + "px"; cv.style.top = img.offsetTop + "px";
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      var s = Math.min(w / SRC, h / SRC);
      box = { w: w, h: h, s: s, dx: (w - SRC * s) / 2, dy: h - SRC * s };
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    if (img.complete) fit(); else img.addEventListener("load", fit);
    global.addEventListener("resize", fit);

    var X = function (x) { return box.dx + x * box.s; };
    var Y = function (y) { return box.dy + y * box.s; };

    /* ── 外から受け取る3つの数値だけを持つ ───────────────── */
    var N = { koe: [1, 0], iki: 0, yure: 0 };   // 母音・呼吸・揺れ

    var analyser = null, lv = 0, t = 0;
    var vis = "viseme_sil", visAt = 0, vx = 1, vy = 0;
    var blink = 1, blinkAt = performance.now() + 2200;

    function draw() {
      if (!box.w) { fit(); }
      if (!box.w) return;
      ctx.clearRect(0, 0, box.w, box.h);
      var s = box.s;

      /* 目（瞬きは たてはば だけ縮める） */
      [EYE_L, EYE_R].forEach(function (e) {
        ctx.beginPath();
        ctx.ellipse(X(e.x), Y(e.y), e.rx * s, Math.max(.4, e.ry * blink) * s, 0, 0, 6.2832);
        ctx.fillStyle = e.fill; ctx.fill();
      });

      /* 口：閉じているときは承認済みPNGと同じ笑みの線、開くほど穴に置き換わる */
      var open = N.koe[1];                       // 0〜1
      var wide = N.koe[0];                       // よこはば倍率
      var smile = Math.max(0, 1 - open * 2.4);
      if (smile > 0.01) {
        ctx.globalAlpha = smile;
        ctx.beginPath();
        ctx.moveTo(X(MOUTH.x0), Y(MOUTH.y0));
        ctx.quadraticCurveTo(X(MOUTH.x), Y(MOUTH.cy), X(MOUTH.x1), Y(MOUTH.y0));
        ctx.lineWidth = MOUTH.w * s; ctx.lineCap = "round";
        ctx.strokeStyle = MOUTH.line; ctx.stroke();
        ctx.globalAlpha = 1;
      }
      if (open > 0.012) {
        var rx = 14 * wide * s, ry = Math.max(1.2, open * 11) * s;
        ctx.beginPath();
        ctx.ellipse(X(MOUTH.x), Y(224), rx, ry, 0, 0, 6.2832);
        ctx.fillStyle = MOUTH.hole; ctx.fill();
        ctx.beginPath();     // 口の縁をすこし締める（平たく見せない）
        ctx.ellipse(X(MOUTH.x), Y(224), rx, ry, 0, 0, 6.2832);
        ctx.lineWidth = Math.max(1, 1.2 * s); ctx.strokeStyle = "rgba(48,26,14,.55)";
        ctx.stroke();
      }

      /* 呼吸と揺れは体ごと。傾きの軸は接地している下端。 */
      rig.style.transform =
        "translateX(" + N.yure.toFixed(2) + "px) rotate(" + (N.yure * 0.32).toFixed(3) + "deg)" +
        " scaleY(" + (1 + N.iki * 0.014).toFixed(4) + ")" +
        " scaleX(" + (1 - N.iki * 0.008).toFixed(4) + ")";
    }

    (function loop() {
      t++;
      /* 音の大きさ */
      if (analyser) {
        var n = analyser.frequencyBinCount, d = new Uint8Array(n);
        analyser.getByteFrequencyData(d);
        var cut = Math.floor(n * 0.12), top = Math.floor(n * 0.5), lo = 0, hi = 0, i;
        for (i = 0; i < cut; i++) lo += d[i];
        for (i = cut; i < top; i++) hi += d[i];
        lo /= cut * 255; hi /= (top - cut) * 255;
        lv += (Math.min(1, lo * 1.4 + hi) - lv) * 0.35;
        if (lv < 0.03) lv *= 0.6;
      } else { lv *= 0.85; }

      /* ① 母音 */
      var fresh = (performance.now() - visAt) < 300;
      var want = (fresh && VIS[vis]) ? VIS[vis] : [1 + lv * 0.49, lv];
      vx += (want[0] - vx) * 0.45;
      vy += (want[1] - vy) * 0.45;
      N.koe = [vx, fresh ? vy * lv * 1.18 : lv];

      /* ② 呼吸（止まった人形にしない。無言のときこそ動かす） */
      N.iki = Math.sin(t / 47) * (0.62 + (1 - Math.min(1, lv * 3)) * 0.38);

      /* ③ 揺れ（呼吸と周期をずらす。同じ拍子にしない） */
      N.yure = Math.sin(t / 121) * 2.1 + Math.sin(t / 37) * 0.35;

      /* 瞬き */
      var now = performance.now();
      if (now > blinkAt) {
        var d2 = now - blinkAt;
        blink = d2 < 60 ? 1 - d2 / 60 : (d2 < 130 ? (d2 - 60) / 70 : 1);
        if (d2 > 130) { blink = 1; blinkAt = now + 2600 + Math.random() * 3400; }
      }

      draw();
      requestAnimationFrame(loop);
    })();

    return {
      attach: function (a) { analyser = a; },
      speaking: function () {},
      level: function () { return lv; },
      viseme: function (v) { if (VIS[v]) { vis = v; visAt = performance.now(); } },
      el: rig
    };
  }

  /* 吹き出しの横の小さい丸アイコン。承認済みPNGをそのまま丸く抜くだけ。 */
  function avatar() {
    return '<span class="tmk-ava" aria-hidden="true"></span>';
  }
  function you() {
    return '<span class="tmk-ava you" aria-hidden="true"></span>';
  }

  global.Tamako966 = { stand: stand, avatar: avatar, you: you };
})(window);
