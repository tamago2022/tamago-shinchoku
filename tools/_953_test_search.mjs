// 947ページの「棚を引く部分」だけを取り出して、ブラウザ抜きで動かす検品。
// 目的：案内人が実在しない曲を出さないこと・4枚出ること・次の4枚が別物であること。
import fs from "node:fs";
import path from "node:path";

const ASSET = path.resolve("share/check/assets/953-songs");
const head = JSON.parse(fs.readFileSync(path.join(ASSET, "head.json"), "utf8"));
const picks = JSON.parse(fs.readFileSync(path.join(ASSET, "picks.json"), "utf8"));
const shelfCache = {};
const shelf = n => (shelfCache[n] ??= (() => {
  const p = path.join(ASSET, "t", n + ".json");
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : [];
})());

const norm = s => String(s).normalize("NFKC").toLowerCase()
  .replace(/[\s'’`\-_.,!?/()（）「」『』・:;"]+/g, " ").trim();
const prefixes = s => {
  const out = new Set();
  for (const w of norm(s).split(" ")) if (w) out.add(w.slice(0, 2));
  return [...out];
};
const bucketOf = pre =>
  (pre.charCodeAt(0) * 131 + (pre.length > 1 ? pre.charCodeAt(1) : 0)) % head.nb;

const artistText = a => norm([a.n, (a.al || []).join(" "), (a.g || []).join(" "),
                              (a.e || []).join(" "), a.ab || ""].join(" "));

const shown = new Set();
function findSongs(queries) {
  const A = head.A;
  const qs = (queries || []).map(norm).filter(q => q.length >= 1);
  if (!qs.length) return [];
  const artScore = new Map();
  A.forEach((a, i) => {
    const hay = artistText(a);
    let sc = 0;
    for (const q of qs) {
      if (norm(a.n) === q) sc += 100;
      else if (hay.includes(q)) sc += (q.length >= 3 ? 40 : 12);
    }
    if (sc) artScore.set(i, sc);
  });
  function tidy(title){
    let p=0;
    if(title.length>45) p-=60; else if(title.length>30) p-=20;
    if(/[|｜]/.test(title)) p-=50;
    if(/[【】]/.test(title)) p-=25;
    if(/[☀-⟿✨🎵🔥]/u.test(title)) p-=30;
    if(/\bft\.?\b|\bfeat\.?\b/i.test(title)) p-=5;
    return p;
  }
  const out = [], seen = new Set();
  const push = (row, sc) => {
    const key = row[0] + "/" + row[1];
    if (seen.has(key) || shown.has(key)) return;
    seen.add(key);
    out.push({ ai: row[0], sid: row[1], title: row[2], year: row[3] || 0, yt: row[4] || "",
               sc: sc + tidy(row[2]) + (row[3] ? 10 : 0) });
  };
  if (artScore.size) for (const row of picks) {
    const sc = artScore.get(row[0]); if (sc) push(row, sc + 20);
  }
  const pres = new Set();
  for (const q of qs) for (const p of prefixes(q)) pres.add(p);
  const nums = [...new Set([...pres].map(bucketOf))].slice(0, 6);
  for (const n of nums) for (const row of shelf(n)) {
    const t = norm(row[2]); let sc = 0;
    for (const q of qs) { if (q.length < 2 && !/[^\x00-\x7F]/.test(q)) continue;
      if (t === q) sc += 90; else if (t.includes(q)) sc += 30; }
    if (sc) push(row, sc + (artScore.get(row[0]) || 0));
  }
  out.sort((x, y) => y.sc - x.sc);
  return out;
}

let pool = [];
function dealFour() {
  const take = [];
  while (take.length < 4 && pool.length) {
    const s = pool.shift(), key = s.ai + "/" + s.sid;
    if (shown.has(key)) continue;
    shown.add(key); take.push(s);
  }
  return take;
}
const url = s => head.base + "?artist=" + encodeURIComponent(head.A[s.ai].i) +
                 "&song=" + encodeURIComponent(s.sid);
const show = (label, take) => {
  console.log("\n── " + label + " → " + take.length + "枚 / 残り " + pool.length);
  for (const s of take)
    console.log("   ", s.title, "／", head.A[s.ai].n, s.year || "", "\n      " + url(s));
};

// 案内人が実際に投げそうな手がかり
const CASES = [
  ["しずかなバラード", ["Norah Jones", "Eva Cassidy", "José González", "ballad", "acoustic", "坂本龍一", "子守唄", "lullaby"]],
  ["中島みゆき 糸", ["中島みゆき", "糸", "nakajima"]],
  ["元気が出るやつ", ["Stevie Wonder", "Earth Wind & Fire", "funk", "soul", "dance", "Jamiroquai"]],
  ["雨の日", ["rain", "雨", "Bill Withers", "jazz"]],
  ["存在しない気分", ["ぬるぬるした宇宙ラーメン", "zzzzqqqq"]],
];

let fails = 0;
for (const [label, qs] of CASES) {
  pool = findSongs(qs);
  const a = dealFour(); show(label + "（1回目）", a);
  const b = dealFour(); show(label + "（他のを、2回目）", b);
  const overlap = a.filter(x => b.some(y => y.ai === x.ai && y.sid === x.sid));
  if (overlap.length) { console.log("   ✗ 同じ札が2回出た"); fails++; }
  if (label !== "存在しない気分" && a.length < 4) { console.log("   ✗ 4枚そろわなかった"); fails++; }
  if (label === "存在しない気分" && a.length) { console.log("   ※ 参考：空振りのはずが出た"); }
  for (const s of [...a, ...b]) {
    if (!s.yt) { console.log("   ✗ 動画IDが無い:", s.title); fails++; }
    if (!head.A[s.ai]) { console.log("   ✗ アーティストが引けない"); fails++; }
  }
}

// 実在チェック：出した曲が元データ（coverGuide.ts）にそのまま在るか
const src = fs.readFileSync("status/_952/recon/HIT_src_lib_coverGuide.ts", "utf8");
let checked = 0, missing = 0;
for (const key of [...shown].slice(0, 40)) {
  const [ai, sid] = [key.split("/")[0], key.slice(key.indexOf("/") + 1)];
  checked++;
  if (!src.includes('id: "' + sid + '"')) { missing++; console.log("   ✗ 元データに無い:", sid); }
}
console.log(`\n実在チェック：${checked}件みて、元データに無かったもの ${missing}件`);
console.log(fails === 0 && missing === 0 ? "\n合格" : `\n不合格（${fails + missing}件）`);
process.exit(fails === 0 && missing === 0 ? 0 : 1);
