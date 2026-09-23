/* 1042番【口の形が母音ごとに変わるか、ブラウザ無しで実測する】
   avatar431.js をそのまま読み込み、偽のDOMで回す。canvas に描かれた点を横取りして、
   実際に描かれた口の「よこはば(px)」と「深さ(px)」を数える。目で見なくても数字で出る。
     node tools/_1042_kuchi_test.mjs
*/
import fs from "fs";

const src = fs.readFileSync(new URL("../share/check/assets/431-seihon/avatar431.js", import.meta.url), "utf8");
let T = 0;
const raf = [];

function el(rec) {
  const o = {
    className: "", style: {}, children: [],
    clientWidth: 444, clientHeight: 412, offsetLeft: 0, offsetTop: 0,
    width: 444, height: 412, complete: true, src: "", alt: "",
    setAttribute() {}, appendChild(c) { o.children.push(c); }, addEventListener() {},
    getContext() {
      const noop = () => {};
      return {
        setTransform: noop, clearRect: noop, fill: noop, stroke: noop, closePath: noop,
        beginPath() { if (rec) rec.pts = []; },
        moveTo(x, y) { if (rec) rec.pts.push([x, y]); },
        quadraticCurveTo(cx, cy, x, y) { if (rec) rec.pts.push([cx, cy], [x, y]); },
        createLinearGradient: () => ({ addColorStop: noop }),
        globalAlpha: 1, fillStyle: "", strokeStyle: "", lineWidth: 1, lineCap: ""
      };
    }
  };
  return o;
}
const win = { devicePixelRatio: 1, addEventListener() {},
  requestAnimationFrame(f) { raf.push(f); return raf.length; },
  performance: { now: () => T }, document: { createElement: el } };
win.window = win;
new Function("window", "document", "performance", "requestAnimationFrame", src)
  (win, win.document, win.performance, win.requestAnimationFrame);

/* 母音を1つ与えて落ち着くまで回し、描かれた口を測る */
function hakaru(opt, v) {
  raf.length = 0;
  const rec = { pts: [] };
  const holder = el(null);
  holder.ownerRec = rec;
  const origCreate = win.document.createElement;
  win.document.createElement = (tag) => el(tag === "canvas" ? rec : null);
  const face = win.Tamako431.stand(holder, opt);
  win.document.createElement = origCreate;
  for (let i = 0; i < 40; i++) {
    face.viseme(v); face.pulse(1);
    T += 1000 / 60; raf.splice(0).forEach(f => f());
  }
  if (!rec.pts.length) return { w: 0, d: 0 };
  const xs = rec.pts.map(p => p[0]), ys = rec.pts.map(p => p[1]);
  return { w: +(Math.max(...xs) - Math.min(...xs)).toFixed(1),
           d: +(Math.max(...ys) - Math.min(...ys)).toFixed(1) };
}

const rows = [["あ", "viseme_aa"], ["い", "viseme_I"], ["う", "viseme_U"],
              ["え", "viseme_E"], ["お", "viseme_O"], ["閉じ", "viseme_PP"]];
const out = { hakatta: "node tools/_1042_kuchi_test.mjs（工場内・ブラウザ不使用）", mae: {}, ato: {} };

console.log("実際にcanvasへ描かれた口（444×412の絵に対するpx）");
console.log("  母音    前の口 よこ×深さ      直した口 よこ×深さ");
for (const [k, v] of rows) {
  const a = hakaru({ kuchi: "mae" }, v), b = hakaru({}, v);
  out.mae[k] = a; out.ato[k] = b;
  console.log(`  ${k.padEnd(3, "　")}  ${String(a.w).padStart(5)} × ${String(a.d).padStart(5)}      ${String(b.w).padStart(5)} × ${String(b.d).padStart(5)}`);
}
const kataMae = new Set(rows.map(([k]) => out.mae[k].w + "x" + out.mae[k].d));
const kataAto = new Set(rows.map(([k]) => out.ato[k].w + "x" + out.ato[k].d));
const fukasaMae = new Set(rows.map(([k]) => out.mae[k].d));
const fukasaAto = new Set(rows.map(([k]) => out.ato[k].d));
console.log(`\n  形の種類     前 ${kataMae.size}/6 → 後 ${kataAto.size}/6`);
console.log(`  深さの種類   前 ${fukasaMae.size}/6 → 後 ${fukasaAto.size}/6  ${fukasaAto.size === 6 ? "OK（あ・い・う・え・お・閉じ が全部ちがう深さ）" : "NG"}`);

const pp = win.Tamako431.kanaToViseme("まみむめも").filter(s => s.v === "viseme_PP").length;
console.log(`  ま行5文字の前に閉じ  ${pp}/5  ${pp === 5 ? "OK" : "NG"}`);
const aiueo = win.Tamako431.kanaToViseme("あいうえお").filter(s => s.v !== "viseme_sil").map(s => s.v);
console.log(`  あいうえお → ${new Set(aiueo).size}/5 種類  ${new Set(aiueo).size === 5 ? "OK" : "NG"}`);

out.kekka = { katachi_mae: kataMae.size, katachi_ato: kataAto.size,
              fukasa_mae: fukasaMae.size, fukasa_ato: fukasaAto.size, ma_pp: pp };
fs.writeFileSync(new URL("../status/1042_kuchi_katachi.json", import.meta.url),
                 JSON.stringify(out, null, 2), "utf8");
console.log("\n→ status/1042_kuchi_katachi.json");
