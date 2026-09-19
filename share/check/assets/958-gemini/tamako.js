/* 958番 — 案内人「たまこ」コンシェルジュ（957番の写し＋口の形（viseme）対応）
 *
 * 原案の姿（Dispatchが実物を見て書き起こしたもの）:
 *  - ローポリ（多面体）の卵。生成りのベージュ。表面に細かい面の切り替えがあるCG調。
 *  - ピンクの縁の立体メガネ。左レンズが青、右レンズが赤（3Dメガネ）。
 *  - 赤いボウタイ。ベージュのジャケット。襟と一つボタンが見える。短い腕。
 *  - 口は小さな笑みの線。目はメガネで隠れている。
 *  ★「細長い卵に目と口」の顔は使わない。ページのどこにも残さない。
 *  ★吹き出しの横の小さい丸アイコンも、同じこの顔にする（Tamako.avatar）。
 *
 * 口だけが声に合わせて動く（既存の口パクを壊さない）。
 */
(function (global) {
  "use strict";

  var NS = "http://www.w3.org/2000/svg";

  /* ── 卵の形（多面体にするための元の曲面） ─────────────────
     y は SVG のまま（下が＋）。上が細く、下がふくらむ卵。 */
  var A = 59, B = 90;
  function surf(v, u) {
    var R = A * Math.sin(v) * (1 - 0.30 * Math.cos(v));
    return [R * Math.cos(u), -B * Math.cos(v), R * Math.sin(u)];
  }
  /** その高さ（y）での卵の半分の幅。ジャケットの形を卵に沿わせるのに使う。 */
  function halfW(y) {
    var c = Math.max(-1, Math.min(1, -y / B)), v = Math.acos(c);
    return A * Math.sin(v) * (1 - 0.30 * c);
  }
  function sub(p, q) { return [p[0] - q[0], p[1] - q[1], p[2] - q[2]]; }
  function cross(p, q) {
    return [p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0]];
  }
  function unit(p) {
    var m = Math.sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]) || 1;
    return [p[0] / m, p[1] / m, p[2] / m];
  }
  // 光は左上の手前から
  var L = unit([-0.44, -0.70, 0.56]);

  /** 多面体の卵の面を並べた markup を返す。CG調の面の切り替えはここで出る。 */
  function facets(nlat, nlon, hue, sat, lig) {
    var out = [], i, j;
    for (i = 0; i < nlat; i++) {
      for (j = 0; j < nlon; j++) {
        var v0 = Math.PI * i / nlat, v1 = Math.PI * (i + 1) / nlat;
        // 段ごとに半コマずらす。これで格子縞ではなく多面体の面の切り替えになる。
        var oa = (i % 2) * Math.PI / nlon, ob = ((i + 1) % 2) * Math.PI / nlon;
        var u0 = 2 * Math.PI * j / nlon, u1 = 2 * Math.PI * (j + 1) / nlon;
        var p0 = surf(v0, u0 + oa), p1 = surf(v0, u1 + oa),
            p2 = surf(v1, u1 + ob), p3 = surf(v1, u0 + ob);
        var n = unit(cross(sub(p3, p0), sub(p1, p0)));
        if (n[2] <= 0.02) continue;                      // 裏の面は描かない
        var d = Math.max(0, n[0] * L[0] + n[1] * L[1] + n[2] * L[2]);
        var li = (lig - 9) + 24 * Math.pow(d, 0.85);
        var pts = [p0, p1, p2, p3].map(function (p) {
          return p[0].toFixed(1) + "," + p[1].toFixed(1);
        }).join(" ");
        out.push({
          z: Math.max(p0[2], p1[2], p2[2], p3[2]),
          s: '<polygon points="' + pts + '" fill="hsl(' + hue + ',' + (sat - 5 * d).toFixed(0)
             + '%,' + li.toFixed(1) + '%)" stroke="rgba(124,98,62,.13)" stroke-width=".5"/>',
        });
      }
    }
    out.sort(function (a, b) { return a.z - b.z; });
    return out.map(function (o) { return o.s; }).join("");
  }

  /* ── 立体メガネ（ピンクの縁／左レンズ青・右レンズ赤） ───── */
  function glasses(id) {
    return '' +
      // つる
      '<path d="M-42,-44 L-55,-38" stroke="#e07fa2" stroke-width="4" stroke-linecap="round" fill="none"/>' +
      '<path d="M42,-44 L55,-38" stroke="#e07fa2" stroke-width="4" stroke-linecap="round" fill="none"/>' +
      // レンズ（左＝青）
      '<rect x="-42" y="-55" width="32" height="27" rx="7" fill="#2f6bc4" fill-opacity=".86"/>' +
      // レンズ（右＝赤）
      '<rect x="10" y="-55" width="32" height="27" rx="7" fill="#cd3a2c" fill-opacity=".86"/>' +
      // ハイライト（立体感）
      '<path d="M-38,-31 L-29,-52" stroke="#ffffff" stroke-opacity=".5" stroke-width="4" stroke-linecap="round"/>' +
      '<path d="M14,-31 L23,-52" stroke="#ffffff" stroke-opacity=".45" stroke-width="4" stroke-linecap="round"/>' +
      // ピンクの縁
      '<rect x="-42" y="-55" width="32" height="27" rx="7" fill="none" stroke="#ef8fb0" stroke-width="4.6"/>' +
      '<rect x="10" y="-55" width="32" height="27" rx="7" fill="none" stroke="#ef8fb0" stroke-width="4.6"/>' +
      '<path d="M-10,-45 Q0,-49 10,-45" stroke="#ef8fb0" stroke-width="4.6" fill="none" stroke-linecap="round"/>' +
      '<rect x="-42" y="-55" width="32" height="27" rx="7" fill="none" stroke="#c96b8c" stroke-width="1" stroke-opacity=".8"/>' +
      '<rect x="10" y="-55" width="32" height="27" rx="7" fill="none" stroke="#c96b8c" stroke-width="1" stroke-opacity=".8"/>';
  }

  /* ── 赤いボウタイ ─────────────────────────────────── */
  function bowtie(cy) {
    return '' +
      '<path d="M-2,' + cy + ' L-22,' + (cy - 9) + ' Q-25,' + cy + ' -22,' + (cy + 9) + ' Z" fill="#c0332b"/>' +
      '<path d="M2,' + cy + ' L22,' + (cy - 9) + ' Q25,' + cy + ' 22,' + (cy + 9) + ' Z" fill="#b62d26"/>' +
      '<rect x="-5" y="' + (cy - 5.4) + '" width="10" height="10.8" rx="2.6" fill="#9e241f"/>';
  }

  /* ── ジャケット（襟と一つボタン）。形そのものを卵に沿わせる ── */
  function jacket() {
    var TOP = 4, d = "", y;
    d = "M" + (-halfW(TOP)).toFixed(1) + "," + TOP + " Q0,26 " + halfW(TOP).toFixed(1) + "," + TOP;
    for (y = TOP; y <= B; y += 6) d += "L" + halfW(y).toFixed(1) + "," + y.toFixed(1);
    d += "L0," + B;
    for (y = B; y >= TOP; y -= 6) d += "L" + (-halfW(y)).toFixed(1) + "," + y.toFixed(1);
    d += "Z";
    return '' +
      '<path d="' + d + '" fill="#d8c69f"/>' +
      '<path d="M' + (-halfW(TOP)).toFixed(1) + "," + TOP + " Q0,26 "
        + halfW(TOP).toFixed(1) + "," + TOP + '" fill="none" stroke="#bda57a" stroke-width="1.6"/>' +
      // 襟（Ｖ）とその中の白
      '<path d="M-26,14 L0,62 L26,14 L34,19 L0,76 L-34,19 Z" fill="#f2ead9"/>' +
      '<path d="M-26,14 L0,62 L26,14" fill="none" stroke="#c2aa7e" stroke-width="2.2"/>' +
      '<path d="M-34,19 L0,76 L34,19" fill="none" stroke="#c2aa7e" stroke-width="2.2"/>' +
      // 一つボタン
      '<circle cx="0" cy="84" r="4.2" fill="#b59d72" stroke="#8f7a55" stroke-width=".9"/>';
  }

  /* ── 短い腕 ───────────────────────────────────────── */
  function arms() {
    return '' +
      '<path d="M-44,38 C-63,43 -73,58 -71,74 C-70,85 -60,88 -55,79 C-48,67 -44,53 -44,38 Z" ' +
        'fill="#d3c099" stroke="#b9a274" stroke-width="1.1"/>' +
      '<path d="M44,38 C63,43 73,58 71,74 C70,85 60,88 55,79 C48,67 44,53 44,38 Z" ' +
        'fill="#d3c099" stroke="#b9a274" stroke-width="1.1"/>';
  }

  var seq = 0;

  /**
   * ヒーローに立つコンシェルジュ本人。
   * el に描き、口パク用の face（core.js が使う）を返す。
   */
  function stand(el, opt) {
    opt = opt || {};
    var uid = "tmk" + (++seq);
    var svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", "-96 -116 192 260");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "ごきげん補給所の案内人");
    svg.innerHTML =
      (opt.shadow === false ? "" :
        '<ellipse cx="3" cy="97" rx="50" ry="9" fill="rgba(0,0,0,.26)"/>') +
      arms() +
      '<g>' + facets(9, 15, 38, 30, 78) + "</g>" +
      jacket() +
      bowtie(21) +
      glasses(uid) +
      // 口（笑みの線 → 声で開く）
      '<path id="' + uid + '-smile" d="M-11,-20 Q0,-11 11,-20" fill="none" stroke="#7a5a3a" ' +
        'stroke-width="3.4" stroke-linecap="round"/>' +
      '<ellipse id="' + uid + '-mouth" cx="0" cy="-17" rx="7" ry="0" fill="#7d3b34" opacity="0"/>';
    el.appendChild(svg);

    var smile = svg.querySelector("#" + uid + "-smile");
    var mouth = svg.querySelector("#" + uid + "-mouth");
    var analyser = null, lv = 0, t = 0;

    /* ── 口の形（viseme）──────────────────────────────
       958番で足した口。wawa-lipsync（MIT）が出す15種類の viseme を、
       この卵の口（楕円ひとつ）の 横はば・たてはば の比率に置き換える。
       viseme が来ていないときは、これまでどおり音の大きさだけで開く。   */
    var VIS = {
      viseme_sil: [1.00, 0.00], viseme_PP: [0.75, 0.05], viseme_FF: [0.85, 0.25],
      viseme_TH:  [0.90, 0.35], viseme_DD: [0.90, 0.45], viseme_kk: [0.95, 0.50],
      viseme_CH:  [0.80, 0.40], viseme_SS: [0.90, 0.20], viseme_nn: [0.85, 0.25],
      viseme_RR:  [0.90, 0.50], viseme_aa: [1.25, 1.00], viseme_E:  [1.35, 0.55],
      viseme_I:   [1.40, 0.30], viseme_O:  [0.85, 0.90], viseme_U:  [0.60, 0.60]
    };
    var vis = "viseme_sil", visAt = 0, vx = 1, vy = 0;

    (function loop() {
      t++;
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
      // viseme が 300ms 以内に来ていれば口の形を使う。来ていなければ元どおり。
      var fresh = (performance.now() - visAt) < 300;
      var want = (fresh && VIS[vis]) ? VIS[vis] : [1 + lv * 0.49, lv];
      vx += (want[0] - vx) * 0.45;
      vy += (want[1] - vy) * 0.45;
      var openH = fresh ? vy * lv * 13 : lv * 11;
      mouth.setAttribute("ry", openH.toFixed(2));
      mouth.setAttribute("rx", (7 * vx).toFixed(2));
      mouth.setAttribute("opacity", Math.min(1, openH * 0.5).toFixed(2));
      smile.setAttribute("opacity", (1 - Math.min(1, openH * 0.42)).toFixed(2));
      svg.style.transform = "translateY(" + (Math.sin(t / 58) * 2.2).toFixed(2) + "px)";
      requestAnimationFrame(loop);
    })();

    return {
      attach: function (a) { analyser = a; },
      speaking: function () {},
      level: function () { return lv; },
      /* 958番で足した口。wawa-lipsync の viseme をそのまま渡す。 */
      viseme: function (v) { if (VIS[v]) { vis = v; visAt = performance.now(); } },
      svg: svg,
    };
  }

  /* ── 吹き出しの横に出る小さい丸アイコン ───────────────
     ★ヒーローに立っているコンシェルジュ本人の顔。
       多面体の卵／ピンク縁の3Dメガネ（左青・右赤）／赤いボウタイ。  */
  var AVATAR = null;
  function avatar() {
    if (AVATAR) return AVATAR;
    AVATAR =
      '<svg class="tamako-ava" viewBox="-60 -60 120 120" aria-hidden="true">' +
      '<circle cx="0" cy="0" r="60" fill="#efe6d2"/>' +
      '<g transform="translate(0,22) scale(.864)">' +
      '<g>' + facets(8, 13, 38, 30, 78) + "</g>" +
      jacket() +
      bowtie(21) +
      glasses() +
      '<path d="M-11,-20 Q0,-11 11,-20" fill="none" stroke="#7a5a3a" stroke-width="3.6" stroke-linecap="round"/>' +
      "</g></svg>";
    return AVATAR;
  }

  /* ── 「あなた」側の丸アイコン（人のシルエット。原案どおり） ── */
  function you() {
    return '<svg class="you-ava" viewBox="0 0 40 40" aria-hidden="true">' +
      '<circle cx="20" cy="20" r="20" fill="#e3e8de"/>' +
      '<circle cx="20" cy="15.4" r="6.2" fill="#8d9585"/>' +
      '<path d="M7.6 34c1.6-6.6 6.4-9.6 12.4-9.6S30.8 27.4 32.4 34z" fill="#8d9585"/>' +
      "</svg>";
  }

  global.Tamako = { stand: stand, avatar: avatar, you: you };
})(window);
