// トップの「HTML＋HTMLから直に読まれるJS」だけを測る係。
//
// なぜこの測り方か：951番が直す前に測った 1.37MB は、この測り方で出した数字
// （status/_951/recon/11_live_bytes.txt）。同じ測り方で測らないと before/after を並べられない。
// 画像やフォントは入れない（今回の直しが触っていないものを混ぜると、何が変わったのか分からなくなる）。
//
// before は「直す前のトップが読んでいた JS 11本」。Lovable の資産は中身ごとに名前が
// 変わる（ハッシュ付き）ので、古い名前のファイルは今も配信に残っている。実際に叩いて測る。
import fs from "node:fs";
import path from "node:path";

const BASE = "https://joy-relief-station.lovable.app";
const OUT = path.join("status", "public", "top_bytes.json");

// 2026-09-19 10:26 実測（status/_951/recon/11_live_bytes.txt）＝直す前のトップ
const BEFORE_JS = [
  "/assets/youtube-id-map-D3kTqsFk.js",
  "/assets/index-KG8jSGRB.js",
  "/~flock.js",
  "/assets/trails-DnlpvE5k.js",
  "/assets/video-health-flags-BYQBcsoC.js",
  "/assets/index-BD9Gr-NB.js",
  "/assets/FeedbackDoor-DidibMY6.js",
  "/assets/petitTrips-DudSIcqe.js",
  "/assets/EggConcierge-CrOoan-m.js",
  "/assets/coverguide-session-D8jT813g.js",
  "/assets/x-CqKJd_za.js",
];

const H = { "accept-encoding": "gzip, br", "user-agent": "tamago-measure/1" };

async function grab(url) {
  const t0 = Date.now();
  const r = await fetch(url, { headers: H, cache: "no-store" });
  const buf = Buffer.from(await r.arrayBuffer());
  // fetch は自動で解凍するので、転送量は Content-Length（圧縮後）を正とする
  const cl = Number(r.headers.get("content-length") || 0);
  return {
    url: url.replace(BASE, ""),
    http: r.status,
    転送B: cl || buf.length,
    展開B: buf.length,
    秒: Number(((Date.now() - t0) / 1000).toFixed(2)),
  };
}

/** HTML から <script src> と modulepreload を拾う（直す前の測り方と同じ）。 */
function jsFromHtml(html) {
  const out = new Set();
  for (const m of html.matchAll(/<script[^>]+src=["']([^"']+)["']/g)) out.add(m[1]);
  for (const m of html.matchAll(/rel=["']modulepreload["'][^>]*href=["']([^"']+)["']/g)) out.add(m[1]);
  for (const m of html.matchAll(/href=["']([^"']+\.js)["'][^>]*rel=["']modulepreload["']/g)) out.add(m[1]);
  return [...out].filter((u) => u.endsWith(".js"));
}

async function measure(label, jsList, htmlEntry) {
  const files = [];
  if (htmlEntry) files.push(htmlEntry);
  const t0 = Date.now();
  const got = await Promise.all(jsList.map((u) => grab(BASE + u)));
  const wall = (Date.now() - t0) / 1000;
  files.push(...got);
  const 転送 = files.reduce((s, f) => s + f.転送B, 0);
  const 展開 = files.reduce((s, f) => s + f.展開B, 0);
  return {
    見出し: label,
    本数: files.length,
    転送MB: Number((転送 / 1024 / 1024).toFixed(2)),
    展開MB: Number((展開 / 1024 / 1024).toFixed(2)),
    まとめて取り切る秒: Number(wall.toFixed(2)),
    落ちたもの: files.filter((f) => f.http !== 200).map((f) => `${f.url}(${f.http})`),
    内訳: files.sort((a, b) => b.転送B - a.転送B).slice(0, 14),
  };
}

const htmlRes = await fetch(BASE + "/", { headers: H, cache: "no-store" });
const html = await htmlRes.text();
const htmlEntry = {
  url: "/ (HTML)",
  http: htmlRes.status,
  転送B: Number(htmlRes.headers.get("content-length") || Buffer.byteLength(html)),
  展開B: Buffer.byteLength(html),
  秒: 0,
};
const afterJs = jsFromHtml(html);
console.log("いまのHTMLが直に読むJS:", afterJs.length, "本");

const after = await measure("after（いま本番に出ているトップ）", afterJs, htmlEntry);
const before = await measure("before（2026-09-19 10:26 実測の11本）", BEFORE_JS, null);

const payload = {
  測定日時_UTC: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
  測り方:
    "GitHubのrunnerから、HTMLと『HTMLが直に読むJS』だけを gzip/br で取得して転送バイトを合計した。" +
    "画像・フォント・あとから読む分は入れていない（直す前の 1.37MB と同じ測り方に揃えるため）。",
  before,
  after,
  差: {
    転送MB: Number((before.転送MB - after.転送MB).toFixed(2)),
    展開MB: Number((before.展開MB - after.展開MB).toFixed(2)),
    秒: Number((before.まとめて取り切る秒 - after.まとめて取り切る秒).toFixed(2)),
  },
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log(JSON.stringify({ before: before.転送MB, after: after.転送MB }, null, 1));
