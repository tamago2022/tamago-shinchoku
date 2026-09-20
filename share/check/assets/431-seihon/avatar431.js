/* 431番 — 案内人のトーキングアバター（箱）
 *
 * ★この箱が外から受け取るのは「母音・呼吸・揺れ」の3つの数値だけ。
 *   966番で決めた N = { koe, iki, yure } と loop をそのまま持ってきている。
 *   変えたのは「何を描くか」だけ。呼び出し側（geminilive / app）は1行も変えない。
 *
 * ★絵は作らない。Issue #431 の承認済みPNG
 *   src/assets/concierge/approved/02_静かなレコード店.png の画素だけを使う。
 *     L1 body  … img/concierge-nomouth.png（承認済みPNGから案内人だけを抜き、口だけ消したもの）
 *     L2 mouth … 承認済みPNGと同じ位置・同じ色の笑みの線（母音で開く）
 *   目は承認済みの3Dメガネで隠れているので層を持たない（無いものを足さない）。
 *
 * ★平たい2Dにしない（NVIDIA Tokkio を手本にした3点）
 *     奥行き … 揺れを Y軸の回転に回し、親に perspective を掛ける
 *     陰影   … 体の上に回り込む光と落ち影を重ね、揺れに合わせて位置を動かす
 *     接地   … 足元の影を呼吸で縮め、浮いた人形にしない
 */
(function (global) {
  "use strict";

  var SRCW = 444, SRCH = 412;                 // 切り抜きPNGの実寸
  /* 承認済みPNGを実測した口の座標（444×412 の中の位置） */
  var MOUTH = { x: 219, x0: 190, x1: 248, y0: 206, cy: 234, open: 216,
                w: 5.0, line: "#2b1b10", hole: "#4a2416" };

  /* 母音（viseme）→ 口の［よこはば, たてはば］。958/966の対応表をそのまま使う。 */
  var VIS = {
    viseme_sil: [1.00, 0.00], viseme_PP: [0.75, 0.05], viseme_FF: [0.85, 0.25],
    viseme_TH:  [0.90, 0.35], viseme_DD: [0.90, 0.45], viseme_kk: [0.95, 0.50],
    viseme_CH:  [0.80, 0.40], viseme_SS: [0.90, 0.20], viseme_nn: [0.85, 0.25],
    viseme_RR:  [0.90, 0.50], viseme_aa: [1.25, 1.00], viseme_E:  [1.35, 0.55],
    viseme_I:   [1.40, 0.30], viseme_O:  [0.85, 0.90], viseme_U:  [0.60, 0.60]
  };

  function stand(el, opt) {
    opt = opt || {};

    var stage = document.createElement("div");
    stage.className = "tmk-stage";
    var rig = document.createElement("div");
    rig.className = "tmk-rig";
    var img = document.createElement("img");
    img.className = "tmk-body";
    img.src = (opt.src || "assets/431-seihon/img/concierge-nomouth.png");
    img.alt = "ごきげん補給所の案内人";
    var cv = document.createElement("canvas");
    cv.className = "tmk-face";
    cv.setAttribute("aria-hidden", "true");
    var lit = document.createElement("span");      // 回り込む光（陰影）
    lit.className = "tmk-lit";
    var ground = document.createElement("span");   // 足元の影（接地）
    ground.className = "tmk-ground";
    rig.appendChild(img);
    rig.appendChild(cv);
    rig.appendChild(lit);
    stage.appendChild(ground);
    stage.appendChild(rig);
    el.appendChild(stage);

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
      var s = Math.min(w / SRCW, h / SRCH);
      box = { w: w, h: h, s: s, dx: (w - SRCW * s) / 2, dy: h - SRCH * s };
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

    function draw() {
      if (!box.w) { fit(); }
      if (!box.w) return;
      ctx.clearRect(0, 0, box.w, box.h);
      var s = box.s;

      var open = N.koe[1];                       // 0〜1
      var wide = N.koe[0];                       // よこはば倍率
      var smile = Math.max(0, 1 - open * 2.4);

      /* 口：閉じているときは承認済みPNGと同じ笑みの線、開くほど穴に置き換わる */
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
        var rx = 17 * wide * s, ry = Math.max(1.4, open * 13) * s;
        ctx.beginPath();
        ctx.ellipse(X(MOUTH.x), Y(MOUTH.open), rx, ry, 0, 0, 6.2832);
        ctx.fillStyle = MOUTH.hole; ctx.fill();
        /* 口の中に落ちる影。平たい穴に見せない。 */
        var g = ctx.createLinearGradient(0, Y(MOUTH.open) - ry, 0, Y(MOUTH.open) + ry);
        g.addColorStop(0, "rgba(0,0,0,.55)"); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.fillStyle = g; ctx.fill();
        ctx.beginPath();
        ctx.ellipse(X(MOUTH.x), Y(MOUTH.open), rx, ry, 0, 0, 6.2832);
        ctx.lineWidth = Math.max(1, 1.2 * s); ctx.strokeStyle = "rgba(48,26,14,.5)";
        ctx.stroke();
      }

      /* 呼吸と揺れは体ごと。傾きの軸は接地している下端。
         揺れは「横にずれる」だけでなく「向きが変わる」＝奥行きに回す。 */
      var yaw = (N.yure * 1.15).toFixed(3);
      rig.style.transform =
        "translateX(" + N.yure.toFixed(2) + "px)" +
        " rotateY(" + yaw + "deg) rotate(" + (N.yure * 0.32).toFixed(3) + "deg)" +
        " scaleY(" + (1 + N.iki * 0.014).toFixed(4) + ")" +
        " scaleX(" + (1 - N.iki * 0.008).toFixed(4) + ")";
      /* 陰影：光は動かない。体が回るぶんだけ、回り込む光の位置がずれる。 */
      lit.style.transform = "translateX(" + (-N.yure * 2.4).toFixed(2) + "px)";
      lit.style.opacity = (0.34 + Math.max(0, N.yure) * 0.035).toFixed(3);
      /* 接地：息を吸うと体が伸びて、足元の影はわずかに小さく濃くなる。 */
      ground.style.transform =
        "translateX(calc(-50% + " + (N.yure * 1.5).toFixed(2) + "px))" +
        " scaleX(" + (1 - N.iki * 0.035).toFixed(4) + ")";
      ground.style.opacity = (0.55 + N.iki * 0.06).toFixed(3);
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
  function avatar() { return '<span class="tmk-ava" aria-hidden="true"></span>'; }
  function you() { return '<span class="tmk-ava you" aria-hidden="true"></span>'; }

  var api = { stand: stand, avatar: avatar, you: you };
  global.Tamako431 = api;
  global.Tamako966 = api;   // 966の呼び出し側をそのまま使う
})(window);
