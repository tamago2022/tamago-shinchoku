/* 431番 — 案内人のトーキングアバター（箱）
 *
 * ★この箱が外から受け取るのは「母音・呼吸・揺れ」の3つの数値だけ。
 *   966番で決めた N = { koe, iki, yure } と loop をそのまま持ってきている。
 *   変えたのは「何を描くか」だけ。呼び出し側（geminilive / app）は1行も変えない。
 *
 * ★絵は作らない。Issue #431 の承認済みPNG
 *   src/assets/concierge/approved/02_静かなレコード店.png の画素だけを使う。
 *
 * ★974：口が「切り取られて」見えていた原因と、その直し方
 *   原因＝これまでは口を消したPNG（concierge-nomouth.png）を体に使っていた。
 *         消した跡が 181〜244 × 193〜226 の明るい四角い染みとして残っていて、
 *         上に描く笑みの線（幅55px）ではその染みを覆いきれず、縁が見えていた。実測で確認。
 *   直し方＝消したPNGを使うのをやめる。承認済みPNG（concierge.png／笑みの線つき）を
 *         そのまま体に使い、その笑みの線を「上くちびる」として、
 *         線の下だけを開ける。閉じているときは承認済みの絵そのもの＝染みが存在しない。
 *         （Live2D / VRM の口が「口角を固定して下に開く」のと同じ作り）
 *     L1 body  … img/concierge.png（承認済み。1画素も触っていない）
 *     L2 mouth … 承認済みの笑みの線の“下”に開く穴だけ
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
  /* ★974：承認済みPNGの笑みの線を画素から実測し直した値（444×412 の中の位置）。
     左端(191,207) 右端(244,206) 制御点(217,233)＝いちばん下が y220。線の太さ約6。
     この線じたいは承認済みPNGに焼き込まれている。ここに書くのは「その下に開ける穴」の形だけ。 */
  var MOUTH = { x: 217, x0: 191, x1: 244, y0: 207, y1: 206, cy: 233,
                lip: 2.2,          // 焼き込みの線の下端に穴の上辺を合わせる
                depth: 24,         // いちばん開いたときの深さ（蝶ネクタイに触れない所で止める）
                inset: 5,          // 口角は開かない（切り取られて見せない）
                hole: "#43200f" };

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
    img.src = (opt.src || "assets/431-seihon/img/concierge.png");
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

    /* ── 外から受け取る数値だけを持つ ─────────────────────
       966番の N = { koe, iki, yure } はそのまま。974で「話している最中の身振り」を1つ足した。 */
    var N = { koe: [1, 0], iki: 0, yure: 0, mi: 0 };

    var analyser = null, lv = 0, t = 0;
    var vis = "viseme_sil", visAt = 0, vx = 1, amp = 0, mi = 0;

    /* 笑みの線（＝上くちびる）を、よこはば倍率つきで辿る。
       口角の2点は動かさない。動くのは真ん中だけ。 */
    function lipPoint(u, wide) {
      var k = 1 - u;
      var x = k * k * MOUTH.x0 + 2 * k * u * MOUTH.x + u * u * MOUTH.x1;
      var y = k * k * MOUTH.y0 + 2 * k * u * MOUTH.cy + u * u * MOUTH.y1;
      return [MOUTH.x + (x - MOUTH.x) * wide, y];
    }

    function draw() {
      if (!box.w) { fit(); }
      if (!box.w) return;
      ctx.clearRect(0, 0, box.w, box.h);
      var s = box.s;

      var open = N.koe[1];                       // 0〜1
      var wide = N.koe[0];                       // よこはば倍率

      /* ★974：口は「開ける」だけ。閉じているあいだは1画素も描かない＝承認済みの絵そのもの。
         開くときは、焼き込みの笑みの線を上くちびるにして、その下だけを下へ落とす。
         口角（両端）は開かないので、どこにも切り口が出ない。 */
      if (open > 0.008) {
        var d = open * MOUTH.depth;
        var iu = MOUTH.inset / (MOUTH.x1 - MOUTH.x0);       // 口角から内側へ入る量
        var a = lipPoint(iu, wide), b = lipPoint(1 - iu, wide);
        var upX = MOUTH.x, upY = MOUTH.cy + MOUTH.lip * 2;   // 上辺の制御点（線の下端）
        var loY = MOUTH.cy + MOUTH.lip * 2 + d * 2;          // 下辺の制御点

        ctx.beginPath();
        ctx.moveTo(X(a[0]), Y(a[1] + MOUTH.lip));
        ctx.quadraticCurveTo(X(upX), Y(upY), X(b[0]), Y(b[1] + MOUTH.lip));
        ctx.quadraticCurveTo(X(upX), Y(loY), X(a[0]), Y(a[1] + MOUTH.lip));
        ctx.closePath();
        ctx.fillStyle = MOUTH.hole; ctx.fill();

        /* 口の中に落ちる影。平たい穴に見せない。 */
        var top = Y(MOUTH.cy), bot = Y(MOUTH.cy + d + 4);
        var g = ctx.createLinearGradient(0, top, 0, bot);
        g.addColorStop(0, "rgba(0,0,0,.62)");
        g.addColorStop(.55, "rgba(0,0,0,.12)");
        g.addColorStop(1, "rgba(92,44,24,.30)");
        ctx.fillStyle = g; ctx.fill();

        /* 下くちびるの照り返し。穴の底が紙に見えないように。 */
        ctx.globalAlpha = Math.min(.5, open * .9);
        ctx.beginPath();
        ctx.moveTo(X(a[0]), Y(a[1] + MOUTH.lip));
        ctx.quadraticCurveTo(X(upX), Y(loY), X(b[0]), Y(b[1] + MOUTH.lip));
        ctx.lineWidth = Math.max(1, 1.6 * s); ctx.lineCap = "round";
        ctx.strokeStyle = "rgba(214,150,120,.75)"; ctx.stroke();
        ctx.globalAlpha = 1;
      }

      /* 呼吸と揺れは体ごと。傾きの軸は接地している下端。
         揺れは「横にずれる」だけでなく「向きが変わる」＝奥行きに回す。
         ★974：話している最中だけ、ごく浅い頷きを足す（やりすぎない）。 */
      var yaw = (N.yure * 1.15).toFixed(3);
      rig.style.transform =
        "translateX(" + N.yure.toFixed(2) + "px)" +
        " translateY(" + N.mi.toFixed(2) + "px)" +
        " rotateY(" + yaw + "deg) rotate(" + (N.yure * 0.32 + N.mi * 0.12).toFixed(3) + "deg)" +
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

      /* ① 口の開き
         ★974：音素の精度は追わない（たまごさんの指示）。「喋っている間、自然に開閉する」だけ。
         開くのは速く、閉じるのはゆっくり（attack/release を分ける）。
         同じ速さで往復させると、カクカクして“切り取られた”ように見える。 */
      var want = Math.min(1, lv * 1.95);
      amp += (want - amp) * (want > amp ? 0.40 : 0.12);
      if (amp < 0.006) amp = 0;

      /* よこはばだけ母音から借りる（形は追わないが、ずっと同じ幅だと機械に見える） */
      var fresh = (performance.now() - visAt) < 260;
      var wantW = (fresh && VIS[vis]) ? (1 + (VIS[vis][0] - 1) * 0.55) : 1;
      vx += (wantW - vx) * 0.16;
      N.koe = [vx, amp];

      /* ② 呼吸（止まった人形にしない。無言のときこそ動かす） */
      N.iki = Math.sin(t / 47) * (0.62 + (1 - Math.min(1, lv * 3)) * 0.38);

      /* ③ 揺れ（呼吸と周期をずらす。同じ拍子にしない） */
      /* ④ 身振り：喋っているあいだだけ、体がわずかに動く。深追いしない。 */
      mi += (Math.min(1, lv * 3.2) - mi) * 0.045;
      N.yure = Math.sin(t / 121) * 2.1 + Math.sin(t / 37) * 0.35 + Math.sin(t / 26) * 1.15 * mi;
      N.mi   = Math.sin(t / 31) * 1.5 * mi;

      draw();
      requestAnimationFrame(loop);
    })();

    return {
      attach: function (a) { analyser = a; },
      speaking: function () {},
      level: function () { return lv; },
      viseme: function (v) { if (VIS[v] && v !== "viseme_sil") { vis = v; visAt = performance.now(); } },
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
