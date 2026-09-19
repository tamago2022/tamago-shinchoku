// GitHub の runner の上で走り、公開中のトップを「外から」素で開いて重さを測る係。
// たまごさんのスマホと同じ条件（ログイン無し・キャッシュ無しの初回訪問）で測る。
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const URL = process.env.TARGET_URL || "https://joy-relief-station.lovable.app/";
const LABEL = process.env.LABEL || "after";
const RUNS = 3;
const OUT = path.join("status", "public", "top_measure.json");

const median = (a) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.floor(s.length / 2)];
};

const browser = await chromium.launch();
const runs = [];

for (let i = 0; i < RUNS; i++) {
  // 毎回まっさらな入れ物＝キャッシュを持ち越さない（初めて開く人と同じ条件）
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 },
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 " +
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
  });
  const page = await ctx.newPage();

  let bytes = 0;
  let requests = 0;
  page.on("response", async (res) => {
    requests++;
    try {
      const len = res.headers()["content-length"];
      if (len) bytes += Number(len);
      else {
        const b = await res.body().catch(() => null);
        if (b) bytes += b.length;
      }
    } catch {
      /* 本文が取れないものは数えない（数えられないものを水増ししない） */
    }
  });

  const t0 = Date.now();
  await page.goto(URL, { waitUntil: "load", timeout: 120000 });
  const loadSec = (Date.now() - t0) / 1000;

  // ブラウザ自身が持っている数字でも測る（こちらが正確な転送量）
  const perf = await page.evaluate(() => {
    const rs = performance.getEntriesByType("resource");
    const nav = performance.getEntriesByType("navigation")[0];
    let enc = 0;
    for (const r of rs) enc += r.encodedBodySize || 0;
    if (nav) enc += nav.encodedBodySize || 0;
    return {
      encodedBytes: enc,
      resources: rs.length + (nav ? 1 : 0),
      domContentLoadedSec: nav ? nav.domContentLoadedEventEnd / 1000 : null,
      loadEventSec: nav ? nav.loadEventEnd / 1000 : null,
      firstPaintSec:
        (performance.getEntriesByName("first-contentful-paint")[0]?.startTime ?? 0) / 1000 ||
        null,
    };
  });

  runs.push({
    n: i + 1,
    loadSec: Number(loadSec.toFixed(2)),
    loadEventSec: perf.loadEventSec ? Number(perf.loadEventSec.toFixed(2)) : null,
    firstPaintSec: perf.firstPaintSec ? Number(perf.firstPaintSec.toFixed(2)) : null,
    transferMB: Number((perf.encodedBytes / 1024 / 1024).toFixed(2)),
    requests: perf.resources,
    responseCountedMB: Number((bytes / 1024 / 1024).toFixed(2)),
  });
  console.log(JSON.stringify(runs[runs.length - 1]));
  await ctx.close();
}

await browser.close();

const payload = {
  測定日時_UTC: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
  見出し: LABEL,
  URL,
  測り方:
    "GitHubのrunnerから、キャッシュ空のChromiumでiPhone相当の画面で開き、load完了までの秒数と " +
    "encodedBodySize の合計（＝実際に降ってきた量）を3回測って中央値を採った",
  中央値: {
    秒: median(runs.map((r) => r.loadSec)),
    転送MB: median(runs.map((r) => r.transferMB)),
    リクエスト本数: median(runs.map((r) => r.requests)),
    初回描画秒: median(runs.map((r) => r.firstPaintSec ?? 0)),
  },
  各回: runs,
};

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log(JSON.stringify(payload.中央値));
