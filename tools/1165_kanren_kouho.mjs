#!/usr/bin/env node
/**
 * 1165番【関連動画の候補を仕入れる】本番の searchYouTubeCandidates を使って、
 * 曲ごとに「この曲の関連動画」に置ける候補を集める。棚に入れるかは人が選ぶ。
 *
 * 憲法22条（識別子で同定）・素人カバー禁止に合わせて、ここで機械的に落とすもの:
 *   ・warning に「素人」が入っているもの
 *   ・再生数が少なく、公式アーティストチャンネルでもないもの
 *   ・メイン動画と同じ videoId
 *   ・30秒未満／25分超
 *
 * 使い方: node tools/1165_kanren_kouho.mjs <注文票.json> <出力.json>
 * 注文票: [{ "n":3, "artistId":"green-day", "songId":"...", "main":"NU9JoFKlaZ0",
 *            "queries":["...","..."] }, ...]
 */
import fs from "node:fs";

const SEROVAL = [
  "/Users/mac/Desktop/joy-relief-station/node_modules/seroval/dist/index.js",
  "/Users/mac/Desktop/tamago-shinchoku/status/1147/src_main/node_modules/seroval/dist/index.js",
];
let seroval = null;
for (const p of SEROVAL) {
  if (fs.existsSync(p)) {
    seroval = await import(p);
    break;
  }
}
if (!seroval) {
  console.error("seroval が無い");
  process.exit(2);
}

const BASE = process.env.JRS_BASE || "https://joy-relief-station.lovable.app";
const SEARCH_ID = "477140105289e7439bddae3188e6b94f557000676bf1bcc5b1c9fed1d328ab37";
const PW = process.env.JRS_ADMIN_PW || "@";

async function callFn(id, data) {
  const body = JSON.stringify(await seroval.toJSONAsync({ data }));
  const res = await fetch(`${BASE}/_serverFn/${id}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-tsr-serverFn": "true",
      accept: "application/json",
    },
    body,
  });
  const text = await res.text();
  if (res.status !== 200) return { http: res.status, err: text.slice(0, 300) };
  // 本番は seroval の cross-JSON で返す。ここで要るのは素の値だけなので、
  // 必要な種類（文字・数・真偽・配列・オブジェクト・参照）だけ自前でほどく。
  const line = text.split("\n").find((l) => l.trim());
  let val = null;
  try {
    val = unseroval(JSON.parse(line));
  } catch (e) {
    return { http: 200, err: "読めない: " + String(e).slice(0, 120), body: text.slice(0, 300) };
  }
  return { http: 200, val };
}

const CONST = { 1: undefined, 2: true, 3: false, 4: null, 5: -0, 6: NaN, 7: Infinity, 8: -Infinity };

function unseroval(node, refs = new Map()) {
  if (node === null || typeof node !== "object") return node;
  const t = node.t;
  if (t === 0 || t === 1) return node.s;
  if (t === 2) return CONST[node.s];
  if (t === 9) {
    const arr = [];
    if (node.i !== undefined) refs.set(node.i, arr);
    for (const x of node.a || []) arr.push(unseroval(x, refs));
    return arr;
  }
  if (t === 10) {
    const o = {};
    if (node.i !== undefined) refs.set(node.i, o);
    const k = node.p?.k || [];
    const v = node.p?.v || [];
    k.forEach((key, idx) => {
      o[key] = unseroval(v[idx], refs);
    });
    return o;
  }
  // 参照（すでに出た値をもう一度指している）
  if (node.i !== undefined && refs.has(node.i)) return refs.get(node.i);
  if (node.s !== undefined) return node.s;
  return null;
}

const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const OUT = process.argv[3];

function keep(c, main) {
  const why = [];
  if (c.youtubeId === main) why.push("メイン動画と同じ");
  if (/素人/.test(c.warning || "")) why.push("素人カバーの可能性");
  const views = Number(c.viewCount || 0);
  if (!c.isOfficialArtist && !c.isVevo && views < 300000) why.push(`公式でなく再生${views}回`);
  const d = Number(c.durationSec || 0);
  if (d && (d < 30 || d > 1500)) why.push(`長さ${d}秒`);
  return why;
}

const out = { at: new Date().toISOString(), rows: [] };
for (const job of jobs) {
  const seen = new Map();
  const errs = [];
  for (const q of job.queries) {
    const r = await callFn(SEARCH_ID, { password: PW, query: q, maxResults: 12 });
    if (r.err || !r.val?.result?.ok) {
      errs.push({ q, err: r.err || r.val?.result?.error || "不明" });
      continue;
    }
    for (const c of r.val.result.candidates || []) {
      if (!seen.has(c.youtubeId)) seen.set(c.youtubeId, { ...c, q });
    }
    await new Promise((s) => setTimeout(s, 350));
  }
  const all = [...seen.values()].map((c) => ({
    youtubeId: c.youtubeId,
    title: c.title,
    ch: c.channelTitle,
    chId: c.channelId,
    views: Number(c.viewCount || 0),
    sec: Number(c.durationSec || 0),
    official: !!c.isOfficialArtist,
    vevo: !!c.isVevo,
    warning: c.warning || "",
    q: c.q,
    otoshita: keep(c, job.main),
  }));
  all.sort((a, b) => b.views - a.views);
  out.rows.push({
    n: job.n,
    artistId: job.artistId,
    songId: job.songId,
    nokotta: all.filter((x) => x.otoshita.length === 0),
    otoshita: all.filter((x) => x.otoshita.length > 0),
    errs,
  });
  console.log(
    `${job.n} ${job.artistId}/${job.songId} 候補=${all.length} 残った=${all.filter((x) => !x.otoshita.length).length} 失敗=${errs.length}`,
  );
}
fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
console.log("書いた:", OUT);
