/* 966番【自己検査】出す前に自分で試す。
 *
 * たまごさんの指示：
 *   「出す前に自分で10個試す。当たった数を報告に書く。」
 *   「出す前に自分で5つ試す。4件とも合っているかを見る。」
 *
 * ★ページの中のコードを写さない。966-gemini-live-tamago.html から
 *   その場で切り出して、そのまま走らせる。（写すと本番とズレる）
 * fetch は使えないので、CAT だけローカルのファイルを読む形に差し替える。
 */
import fs from "node:fs";
import path from "node:path";

const REPO = path.resolve(import.meta.dirname, "..");
const HTML = path.join(REPO, "share/check/966-gemini-live-tamago.html");
const ASSET = path.join(REPO, "share/check/assets/953-songs");

const html = fs.readFileSync(HTML, "utf8");

/* ── ページから、棚を引く部分だけを切り出す ───────────────── */
function cut(from, to) {
  const i = html.indexOf(from);
  const j = html.indexOf(to, i);
  if (i < 0 || j < 0) throw new Error("切り出せない: " + from);
  return html.slice(i, j);
}
const src = [
  cut("const norm=s=>String(s)", "const shown=new Set();"),
  cut("function loose(s){", "async function findSongs("),
  cut("async function findSongs(", "/* ★種類を1つに固定して引く"),
  cut("function spread(list){", "const artistOf=s=>"),
].join("\n");

const head = JSON.parse(fs.readFileSync(path.join(ASSET, "head.json"), "utf8"));
const reg = JSON.parse(fs.readFileSync(path.join(ASSET, "region.json"), "utf8"));
const joy = JSON.parse(fs.readFileSync(path.join(ASSET, "joy.json"), "utf8"));

const CAT = {
  head, reg, joy, t: {}, a: {},
  async load() {},
  async title(n) {
    const f = path.join(ASSET, "t", n + ".json");
    return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : [];
  },
  async byArtist(n) {
    const f = path.join(ASSET, "a", n + ".json");
    return fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, "utf8")) : [];
  },
};
const shown = new Set();

const run = new Function("CAT", "shown", src + `
  return { findSongs, earFind, buildEar, loose, regionSet, EARREF:()=>EAR, VOCABREF:()=>VOCAB };`);
const F = run(CAT, shown);
F.buildEar();

const A = head.A;
const nameOf = (s) => A[s.ai].n;

/* ══════════ ① 名前10個（たまごさんが挙げたもの） ══════════
   「言われた名前」と「その名前が当たるべき人」を書く。
   聞き間違いも一緒に試す（青葉市子→いちご が実際に起きた事故）。 */
const NAMES = [
  { say: "青葉市子",            want: "青葉市子" },
  { say: "ハリー・ベラフォンテ", want: "Harry Belafonte" },
  { say: "キングヌー",          want: "King Gnu" },
  { say: "ユーミン",            want: "松任谷由実" },
  { say: "EW&F",                want: "Earth, Wind & Fire" },
  { say: "スティービー",        want: "Stevie Wonder" },
  { say: "マイケル",            want: "Michael Jackson" },
  { say: "くるり",              want: "くるり" },
  { say: "坂本龍一",            want: "坂本龍一" },
  { say: "ビョーク",            want: "Björk" },
];
/* 実際に起きた聞き間違い（＋起きそうなもの）。おまけの検査。 */
const MISHEARD = [
  { say: "いちご",        want: "青葉市子" },
  { say: "ベラフォンテ",  want: "Harry Belafonte" },
  { say: "Bjork",         want: "Björk" },
  { say: "きんぐぬー",    want: "King Gnu" },
  { say: "アオバイチコ",  want: "青葉市子" },
];

async function testNames(list, title) {
  console.log("\n■ " + title);
  let ok = 0;
  for (const t of list) {
    const got = await F.findSongs({ artists: [t.say], mood: [], song_title: "" });
    const names = [...new Set(got.slice(0, 4).map(nameOf))];
    const hit = names.some((n) => n === t.want || n.indexOf(t.want) === 0);
    if (hit) ok++;
    console.log(`  ${hit ? "○" : "×"} 「${t.say}」→ ${names.join(" / ") || "0件"}`
      + (hit ? "" : `   （ほしかったのは ${t.want}）`));
    shown.clear();
  }
  console.log(`  → ${ok}/${list.length} 当たり`);
  return ok;
}

/* ══════════ ② 地域5つ ══════════ */
const REG = [
  { say: "アジアの曲",    region: "asia",   ok: ["asia"] },
  { say: "日本の曲",      region: "jp",     ok: ["jp"] },
  { say: "ブラジルの曲",  region: "br",     ok: ["br"] },
  { say: "韓国の",        region: "kr",     ok: ["kr"] },
  { say: "北欧の",        region: "nordic", ok: ["nordic"] },
];
async function testRegion() {
  console.log("\n■ 地域5つ（4件とも合っているか）");
  let all = 0;
  const idOf = new Map(A.map((a, i) => [i, a.i]));
  for (const t of REG) {
    const got = await F.findSongs({ artists: [], mood: [], song_title: "", region: t.region });
    const rows = got.slice(0, 4).map((s) => {
      const id = idOf.get(s.ai);
      const code = reg.r[id];
      const groups = (reg.group[code] || []).concat(code ? [code] : []);
      return { n: A[s.ai].n, code, good: t.ok.some((k) => groups.indexOf(k) >= 0) };
    });
    const n = rows.filter((r) => r.good).length;
    const four = rows.length === 4 && n === 4;
    if (four) all++;
    console.log(`  ${four ? "○" : "×"} 「${t.say}」 ${n}/${rows.length}件が合っている`);
    for (const r of rows) console.log(`      ${r.good ? "・" : "×"} ${r.n}（${r.code || "地域不明"}）`);
    shown.clear();
  }
  console.log(`  → 5つのうち ${all} つが「4件とも合っている」`);
  return all;
}

/* ══════════ ③ 棚ごとの件数 ══════════ */
function testShelf() {
  console.log("\n■ 棚ごとの件数");
  const JA = { music: "音楽", food: "食", cute: "動物", laugh: "笑い", travel: "旅", dance: "踊り", joy: "ことば" };
  const n = { music: head.n };
  for (const k of Object.keys(JA)) if (k !== "music") n[k] = 0;
  for (const c of joy.cards) if (c.k !== "music") n[c.k] = (n[c.k] || 0) + 1;
  const line = Object.keys(JA).map((k) => JA[k] + " " + n[k] + "件").join("／");
  console.log("  " + line);
  const empty = Object.keys(JA).filter((k) => !n[k]);
  console.log("  空の棚：" + (empty.length ? empty.map((k) => JA[k]).join("・") : "なし"));
  return { line, empty };
}

const a = await testNames(NAMES, "名前10個（たまごさんが挙げたもの）");
const b = await testNames(MISHEARD, "聞き間違いのとき（おまけ）");
const c = await testRegion();
const d = testShelf();
console.log("\n■ 語彙ヒント（customVocabulary）に渡す語数：" + F.VOCABREF().length);
console.log("\n════ まとめ ════");
console.log("名前10個：" + a + "/10　聞き間違い：" + b + "/5　地域：" + c + "/5");
console.log("棚：" + d.line);
