#!/usr/bin/env node
/* 967【覆面調査員】お客さんのふりをして案内人の棚を何十回も叩き、体験を採点する。
 *
 * ■ なぜ要るか（たまごさんの言葉）
 *   「表参道ヒルズができたら、とりあえず偵察に行ってきて。何店舗か行って、
 *     商品を買うなり店員と話すなりして、体験どうだった、みたいな。
 *     対応遅くなかった？ いきなり画面切り替わんなかった？ コンシェルジュどうだった？」
 *
 * ■ 作りの出どころ（オリジナルではない）
 *   ・評価の3段（single-turn / replay / full simulation）と
 *     「お客さんの人格を決めて走らせる（persona-driven user simulation）」は
 *     ACL 2025 industry track "Evaluating Conversational Agents with Persona-driven
 *     User Simulations based on LLMs" と EVA-Bench(2606.13841) の型。
 *     https://aclanthology.org/2025.emnlp-industry.16/
 *   ・「聞き取りのゆらぎを混ぜて叩く（perturbation suite）」も EVA-Bench の型。
 *     ここでは声が使えないので、名前の誤変換・中黒・通称を混ぜて代用する。
 *   ・★採点に LLM を使わない のは意図的。LLM-as-a-judge は位置バイアス・長さバイアスで
 *     大きく外すことが分かっている（Adaline の偏りベンチで frontier モデルでも 50%超の誤り）。
 *     https://www.adaline.ai/blog/llm-as-judge-reliability-bias
 *     → 点数は全部、棚の実データと突き合わせる機械判定にしてある。
 *
 * ■ 何を試せて、何を試せていないか（正直に）
 *   試せる： お客さんの言葉 → kind/artists の組み立て → 棚引き → 出てきた4枚 → 事実シート
 *   試せない： 声の聞き取り（マイク）・しゃべりの間・声色。
 *             この箱から googleapis.com に出られないので Gemini 本体は一度も呼べていない。
 *             頭は代役（安いモデル）で叩いた。だから「言葉づかい」の点は付けていない。
 *
 * ■ 走らせ方
 *   node tools/967_fukumen.mjs
 *   （お金はかからない。棚のデータはローカルの share/check/assets/953-songs/ を読むだけ）
 *   お客さんの言葉を足す → tools/967_fukumen_cases.json
 *   頭の出した道具呼びを取り直す → tools/967_brain_out.json（作り直す手順は 967_brain_prompt.md）
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const PAGE = path.join(ROOT, "share/check/959-gemini-live-tamago.html");
const ASSETDIR = path.join(ROOT, "share/check/assets/953-songs");

/* ── 1. 本番ページから「棚のコード」をそのまま抜く ─────────────────
   写経すると必ずズレる。試すのは本番のコードそのものでなければ意味がない。 */
const src = fs.readFileSync(PAGE, "utf8");
function slice(from, to, incl = true) {
  const i = src.indexOf(from);
  const j = src.indexOf(to, i);
  if (i < 0 || j < 0) throw new Error("959ページの目印が見つからない: " + from.slice(0, 30));
  return src.slice(i, incl ? j + to.length : j);
}
const shelfCode = slice('const ASSET="assets/953-songs/";', 'const kindJa=k=>KIND_JA[k]||"";');
const factCode  = slice("function factSheet(list){", "\n}\n");

/* ── 2. ブラウザのふりをする（画面は無い。読むのはローカルのファイル）── */
const cache = new Map();
globalThis.fetch = async (u) => {
  const p = path.join(ASSETDIR, String(u).replace("assets/953-songs/", ""));
  if (!cache.has(p)) cache.set(p, fs.existsSync(p) ? fs.readFileSync(p, "utf8") : null);
  const body = cache.get(p);
  return { ok: body !== null, async json() { if (body === null) throw new Error("404"); return JSON.parse(body); } };
};
const $ = () => ({ innerHTML: "", textContent: "", style: {}, classList: { toggle(){}, remove(){}, add(){} } });
/* 並びが毎回変わると「直ったのか運が良かったのか」が分からない。種を固定する。 */
let seed = 20260920;
Math.random = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

const shelf = new Function("$", `${shelfCode}\n${factCode}\n
  /* 画面を描く部分だけ抜いた dealFour。取り出しの中身は本番と同じ（4枚・既出は飛ばす）。*/
  function dealFour(){ const take=[]; while(take.length<4 && pool.length){ const c=pool.shift();
    if(shown.has(c.key)) continue; shown.add(c.key); take.push(c); } return take; }
  let snap=[];
  async function newSearch(args,label){ await CAT.load();
    const kind=KINDS.includes(args.kind)?args.kind:"music";
    pool = (kind==="music") ? (await findSongs(args)).map(songCard) : findKind(kind, args.mood||[]);
    snap = pool.slice();   /* 配る前の「棚から出てきた全部」。順番を見るために取っておく */
    poolLabel=label||""; return dealFour(); }
  return { CAT, KINDS, KIND_JA, newSearch, dealFour, factSheet, norm,
           snap:()=>snap, poolLeft:()=>pool.length, resetShown:()=>shown.clear() };`)($);

/* ── 3. 覆面調査員が言う言葉と、頭が出した道具呼び ─────────────── */
const CASES = JSON.parse(fs.readFileSync(path.join(ROOT, "tools/967_fukumen_cases.json"), "utf8"));
const BRAIN = JSON.parse(fs.readFileSync(path.join(ROOT, "tools/967_brain_out.json"), "utf8"));
const byId = new Map(BRAIN.calls.map((c) => [c.id, c]));

await shelf.CAT.load();
const A = shelf.CAT.head.A;
const nameIdx = new Map();
A.forEach((a, i) => {
  nameIdx.set(shelf.norm(a.n), i);
  for (const al of a.al || []) nameIdx.set(shelf.norm(al), i);
});
const inShelf = (n) => nameIdx.has(shelf.norm(n));

/* ── 4. 1問ずつ叩いて、見たものを記録する ───────────────────── */
const rows = [];
let lastCards = [];
for (const c of CASES.cases) {
  const b = byId.get(c.id);
  const r = { ...c, act: b ? b.act : "none", args: (b && b.args) || null, ms: 0, cards: [], bad: [] };

  if (!b) { r.bad.push("頭が何も返さなかった"); rows.push(r); continue; }

  /* 1問ごとに新しいお客さんとして入り直す。
     「続き」の問（after 付き）だけは、前の問の続きとして同じ札を覚えたまま行く。 */
  if (!c.after) { shelf.resetShown(); lastCards = []; }

  if (b.act === "call") {
    const t0 = performance.now();
    r.cards = await shelf.newSearch(b.args, b.args.label || "");
    r.ms = Math.round(performance.now() - t0);
    r.rest = shelf.poolLeft();
    r.facts = shelf.factSheet(r.cards);
  } else if (b.act === "more") {
    const t0 = performance.now();
    r.cards = shelf.dealFour();
    r.ms = Math.round(performance.now() - t0);
    r.rest = shelf.poolLeft();
  }

  /* 見たもの */
  r.names = r.cards.map((x) => x.title);
  r.by = r.cards.map((x) => (x.fact && x.fact.artist) || "");
  r.kinds = [...new Set(r.cards.map((x) => x.kind))];
  r.betsu = new Set(r.by.filter(Boolean)).size;              // 何組にバラけたか
  r.kasanari = lastCards.filter((k) => r.cards.some((x) => x.key === k)).length; // 前の4枚との重複

  /* 頭が挙げた名前のうち、棚に本当に居た数 */
  if (r.args && (r.args.artists || []).length) {
    const li = r.args.artists;
    r.ageta = li.length;
    r.ita = li.filter(inShelf).length;
  }

  /* ── 採点（機械判定のみ）──────────────────────────── */
  /* たまごさんの軸は「頼んだ種類のものが出たか（4件中何件）」。
     ○か×かではなく、4枚のうち何枚が頼んだものだったかで点を付ける。 */
  const w = c.want || {};
  if (w.kind === "ASK") {
    r.atari = b.act === "ask";
    if (!r.atari) r.bad.push(b.act === "call" ? `聞き返さずに ${b.args.kind} の棚を勝手に引いた` : "何もしなかった");
  } else if (w.kind === "ONE") {
    r.atari = b.act === "call" && !!b.args.kind;
    if (!r.atari) r.bad.push("2つ頼まれて棚を1つに決められなかった");
  } else if (w.kind === "MORE") {
    r.atari = b.act === "more" && r.cards.length > 0 && r.kasanari === 0;
    if (b.act !== "more") r.bad.push("『ほかのを見せて』で済むのに道具を呼び直した");
    else if (!r.cards.length) r.bad.push("次の4枚が出てこなかった");
    else if (r.kasanari) r.bad.push(`さっきと同じ札が ${r.kasanari} 枚まざった`);
  } else if (w.artist === "__NONE__") {
    r.atari = r.cards.length === 0;
    if (!r.atari) r.bad.push(`居ない人を頼まれたのに ${r.cards.length} 枚出した（頭が足した他の名前で埋めている）`);
  } else if (w.artist) {
    const hit = r.by.filter((n) => shelf.norm(n) === shelf.norm(w.artist)).length;
    r.hit = hit;
    r.atari = hit > 0;
    if (!hit) {
      /* なぜ落ちたのかを1行で言えるようにする：棚から出てはいたのに、順番で負けたのか */
      const s = shelf.snap();
      const at = s.findIndex((x) => x.fact && shelf.norm(x.fact.artist) === shelf.norm(w.artist));
      r.jun = at < 0 ? null : at + 1;
      r.poolN = s.length;
      r.bad.push(
        at >= 0
          ? `${w.artist} は棚から出ていたのに ${at + 1}番目（${s.length}枚中）まで押し下げられて、上位4枚に入らなかった`
          : inShelf(w.artist)
            ? `${w.artist} は棚に居るのに一曲も拾えなかった`
            : `${w.artist} が引けなかった（頭が渡した名前で棚に当たらない）`
      );
    } else if (hit === 1 && r.cards.length === 4) {
      r.bad.push(`名指しなのに本人は4枚中1枚だけ（残り3枚は頭が勝手に足した別人）`);
    }
  } else if (w.kind) {
    r.atari = r.cards.length > 0 && r.kinds.length === 1 && r.kinds[0] === w.kind;
    if (!r.cards.length) r.bad.push("0枚。何も出なかった");
    else if (r.kinds[0] !== w.kind) r.bad.push(`${shelf.KIND_JA[w.kind]}を頼んだのに ${shelf.KIND_JA[r.kinds[0]]} が出た`);
  }

  /* 「同じ人が重なる」は曲の棚だけの話。動物や食の札にはアーティスト欄が無い */
  r.ongaku = r.cards.length > 0 && r.cards[0].kind === "music";
  if (r.ongaku && r.betsu < r.cards.length)
    r.bad.push(`4枚のうち同じ人が重なっている（${r.betsu}組しか居ない）`);
  if (r.ms > 1000) r.bad.push(`棚引きに ${r.ms}ms かかった`);

  /* 4枚中何枚が頼んだものだったか（0〜1）。名指しはここが効く */
  if (w.artist && w.artist !== "__NONE__") r.ten = (r.hit || 0) / 4;
  else if (w.kind && !["ASK", "ONE", "MORE"].includes(w.kind))
    r.ten = r.cards.length ? r.cards.filter((x) => x.kind === w.kind).length / 4 : (r.atari ? 1 : 0);
  else r.ten = r.atari ? 1 : 0;

  if (r.cards.length) lastCards = r.cards.map((x) => x.key);
  rows.push(r);
}

/* ── 5. 深掘り：出した4枚について聞かれて、答えられるか ──────────── */
const base = rows.find((r) => r.id === CASES.fukabori.on);
const fuka = CASES.fukabori.q.map((q) => {
  const cards = base ? base.cards : [];
  let able = 0, why = "";
  if (q.need === "year") { able = cards.filter((c) => c.fact && c.fact.year).length; why = `4枚中 ${able} 枚しか発表年が棚に入っていない`; }
  else if (q.need === "about") { able = cards.filter((c) => c.fact && c.fact.about).length; why = `4枚中 ${able} 枚に紹介文がある`; }
  else { able = 0; why = "事実シートに『代表曲』は一度も載らない。正しく『分かりません』になる"; }
  return { ...q, able, total: cards.length, ok: q.need === "__NEVER__" ? true : able === cards.length, why };
});

/* ── 6. 点をつける ───────────────────────────────── */
const scored = rows.filter((r) => r.atari !== undefined);
const rate = (f) => (scored.length ? scored.filter(f).length / scored.length : 0);
const withCards = rows.filter((r) => r.cards.length);
const onk = withCards.filter((r) => r.ongaku);   /* 重なり・バラけは曲の棚だけで測る */
const pt = {
  atari:   (scored.reduce((s, r) => s + (r.ten || 0), 0) / scored.length) * 40,
  kudoku:  (withCards.length ? withCards.filter((r) => (!r.ongaku || r.betsu === r.cards.length) && !r.kasanari).length / withCards.length : 0) * 20,
  tanoshi: (onk.length ? onk.reduce((s, r) => s + r.betsu / Math.max(1, r.cards.length), 0) / onk.length : 0) * 20,
  hayasa:  (withCards.length ? withCards.filter((r) => r.ms <= 1000).length / withCards.length : 0) * 10,
  uso:     (fuka.filter((f) => f.ok).length / fuka.length) * 10,
};
const total = Math.round(Object.values(pt).reduce((a, b) => a + b, 0));

/* 直すところ：同じ言い回しの不具合を数えて、多い順に */
const tally = new Map();
for (const r of rows) for (const b of r.bad) {
  /* 同じ不具合を、名前や数字の違いで別物に数えない */
  const k = b
    .replace(/^.+? は棚から出ていたのに \d+番目（\d+枚中）まで押し下げられて、上位4枚に入らなかった$/,
             "名指しした本人が棚から出ていたのに、順番で押し下げられて4枚に入らなかった")
    .replace(/^.+? は棚に居るのに一曲も拾えなかった$/, "名指しした本人が棚に居るのに一曲も拾えなかった")
    .replace(/^.+? が引けなかった/, "名指しした名前で棚に当たらなかった")
    .replace(/[0-9０-９]+/g, "N");
  if (!tally.has(k)) tally.set(k, { k, n: 0, ids: [] });
  tally.get(k).n++; tally.get(k).ids.push(r.id);
}
const naosu = [...tally.values()].sort((a, b) => b.n - a.n);

/* ── 6.5 棚そのものを数える（1問ずつでは見えない、体験の天井）──────── */
const abN = A.filter((a) => a.ab).length;
let songN = 0, yearN = 0;
for (let n = 0; n < 20; n++) { for (const row of await shelf.CAT.byArtist(n)) { songN++; if (row[3]) yearN++; } }
const shirabe = {
  shoukai: { n: abN, all: A.length, pct: Math.round((abN / A.length) * 100) },
  nen:     { n: yearN, all: songN, pct: Math.round((yearN / songN) * 100) },
  kotoba:  shelf.CAT.joy.cards.filter((c) => c.k === "joy").map((c) => c.t),
  /* 同じ人が2組に分かれていると、名指しの点が半分に割れる */
  futatsu: (() => {
    const m = new Map();
    for (const a of A) { const k = shelf.norm(a.n).replace(/\s*\(.*\)\s*$/, "").trim(); m.set(k, (m.get(k) || 0) + 1); }
    return [...m.entries()].filter(([, n]) => n > 1).length;
  })(),
};

const out = {
  when: new Date().toISOString(),
  shirabe,
  target: CASES.target,
  brain: BRAIN.brain,
  n: rows.length + fuka.length,
  total, pt, rows, fuka, naosu,
  stock: { artists: A.length, songs: shelf.CAT.head.n, joy: shelf.CAT.joy.cards.length },
};
fs.writeFileSync(path.join(ROOT, "tools/967_fukumen_result.json"), JSON.stringify(out, null, 1));
console.log(`${out.n}問  総合 ${total}点`);
const mk = (r) => (r.ten === undefined ? "―" : r.ten >= 0.75 ? "○" : r.ten > 0 ? "△" : "×");
for (const r of rows) console.log(` ${mk(r)} ${r.id} ${r.say}  → ${r.names.join(" / ") || "(なし)"}${r.bad.length ? "\n      ⚠ " + r.bad.join(" ／ ") : ""}`);
console.log("\n直すところ 多い順:");
naosu.slice(0, 6).forEach((x, i) => console.log(` ${i + 1}. (${x.n}件) ${x.k}  [${x.ids.join(",")}]`));
