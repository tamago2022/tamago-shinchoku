// 画面の切り替え測定（iPhone相当・4G相当に絞る・無音・画面に出さない）
// たまごさん指示（2026-10-11）：「こういう動きのチェックも毎回ちゃんとして。重いは悪」
//
//   node tools/kirikae_sokutei.mjs [--base URL] [--stale] [--limit 3000] [--out file.json]
//
//   通常：トップ → 棚 → 曲ページ →（ホーム）→ 特集 → 戻る を、リンクを押して（画面内の遷移で）通し、
//         1回の切り替えが何秒かを測る。
//   --stale：古い版を開いたまま新しい版が公開された状態を作る（開いた後は、まだ読んでいない
//         塊を全部404にし、版の番号 x-deployment-id も別のものに変える。ページを丸ごと
//         読み直した後は新しい版として全部通す）。その状態で同じ切り替えが壊れないかを見る。
//   不合格（exit 1）：1回でも limit 秒を超えた／白い画面のまま／「読み込み直します」が出た／
//         「工事中」が出た／行き先に着かなかった。
//
//   ★ブラウザ（2026-10-11 17:04 の事故から）：Playwright の WebKit（~/Library/Caches/ms-playwright/
//     webkit_mac14_special-2251）は macOS 14.3 で起動直後に SIGBUS で落ち、Playwright.app という
//     アプリの形なので、たまごさんの画面に「予期しない理由で終了しました」の窓が出た
//     （~/Library/Logs/DiagnosticReports/Playwright-2026-10-11-1703xx.ips）。
//     → WebKit はやめ、Chromium の headless shell（アプリの形ではない裸の実行ファイル＝落ちても窓が出ない・
//       画面にも出ない）で、iPhone 15 と同じ画面幅・指タッチ・iPhoneの名乗り にして測る。
//     → 同時に1つだけ（status/kirikae/.lock）。終わったら・止まったら必ずブラウザを閉じる（4分で強制終了）。
//
//   回線（4G相当）：Chromium の回線絞り（往復 100ms・下り 5Mbps・上り 2Mbps）。
//   YouTube の埋め込み・広告は止める（無音・重さの測定対象外）。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import { muonLaunch } from "/Users/mac/tamago/tamago-shinchoku/tools/muon.mjs";

const require = createRequire(import.meta.url);
const { chromium, devices } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const arg = (k, d) => {
  const i = process.argv.indexOf(k);
  return i > 0 ? process.argv[i + 1] : d;
};
const BASE = (arg("--base", "https://joy-relief-station.lovable.app")).replace(/\/$/, "");
const STALE = process.argv.includes("--stale");
const LIMIT = Number(arg("--limit", "3000"));
const OUT = arg("--out", "");
const ORIGIN = new URL(BASE).origin;

const BLOCK = /youtube\.com|youtube-nocookie|googlevideo|doubleclick|googlesyndication|google-analytics|googletagmanager/;

// ---- 同時に1つだけ ----
const LOCK = "/Users/mac/tamago/tamago-shinchoku/status/kirikae/.lock";
fs.mkdirSync(path.dirname(LOCK), { recursive: true });
try {
  const st = fs.statSync(LOCK);
  if (Date.now() - st.mtimeMs < 6 * 60 * 1000) {
    console.error("別の切り替え測定が走っています（同時に立ち上げない）");
    process.exit(3);
  }
} catch {}
fs.writeFileSync(LOCK, String(process.pid));

const iphone = devices["iPhone 15"] || devices["iPhone 14"];
const browser = await muonLaunch(chromium, { headless: true }); // headless shell＝画面に出ない・アプリの形でない
const killer = setTimeout(async () => {
  console.error("4分を超えたので止めます");
  try { await browser.close(); } catch {}
  try { fs.unlinkSync(LOCK); } catch {}
  process.exit(2);
}, 4 * 60 * 1000);
const ctx = await browser.newContext({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: true,
  hasTouch: true,
  userAgent: iphone.userAgent,
});
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send("Network.enable");
await cdp.send("Network.emulateNetworkConditions", {
  offline: false,
  latency: 100,
  downloadThroughput: (5 * 1000 * 1000) / 8,
  uploadThroughput: (2 * 1000 * 1000) / 8,
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// ---- 古い版のまま新しい版が出た状態 ----
let deployed = false; // true の間：まだ読んでいない塊は404
const seen = new Set();
let docLoads = 0;
page.on("requestfinished", (r) => {
  const u = new URL(r.url());
  if (u.origin === ORIGIN && /\.(m?js|css)$/.test(u.pathname)) seen.add(u.pathname);
});

await page.route("**/*", async (route) => {
  const req = route.request();
  const url = req.url();
  if (BLOCK.test(url)) return route.abort();
  const u = new URL(url);
  const same = u.origin === ORIGIN;
  if (deployed && same && /\.(m?js|css)$/.test(u.pathname) && !seen.has(u.pathname)) {
    return route.fulfill({ status: 404, contentType: "text/plain", body: "Not Found" });
  }
  if (deployed && same && req.method() === "HEAD") {
    try {
      const resp = await route.fetch({ timeout: 30000 });
      const headers = { ...resp.headers() };
      if (headers["x-deployment-id"]) headers["x-deployment-id"] = headers["x-deployment-id"].replace(/psr2\.[^.]+/, "psr2.00000000-0000-4000-8000-00000000new1");
      return route.fulfill({ status: resp.status(), headers, body: "" });
    } catch {
      return route.abort();
    }
  }
  return route.continue();
});

const logs = [];
const T0 = Date.now();
page.on("console", (m) => {
  const t = m.text();
  if (/stale|nav-recover|reload|読み|chunk|module|Failed|error/i.test(t)) logs.push(`${((Date.now() - T0) / 1000).toFixed(1)}s ${m.type()}: ${t.slice(0, 200)}`);
});
page.on("pageerror", (e) => logs.push(`${((Date.now() - T0) / 1000).toFixed(1)}s pageerror: ${String(e).slice(0, 200)}`));
page.on("request", (r) => {
  if (r.isNavigationRequest() && r.frame() === page.mainFrame()) {
    logs.push(`${((Date.now() - T0) / 1000).toFixed(1)}s 文書読み込み: ${r.url().replace(ORIGIN, "")}`);
    docLoads++;
    // 丸ごと読み直した＝新しい版のHTMLを取った。以後は新しい版として全部通す
    if (deployed) deployed = false;
  }
});

const toastSeen = [];
const watchToast = async () => {
  const t = await page
    .evaluate(() => document.body?.innerText || "")
    .catch(() => "");
  if (/読み込み直します/.test(t)) toastSeen.push(Date.now());
  return t;
};

const state = () =>
  page
    .evaluate(() => {
      const pending = !!document.querySelector('[style*="route-pending"]');
      const t = (document.querySelector("main") || document.body)?.innerText || "";
      return {
        href: location.pathname + location.search,
        pending,
        textLen: t.replace(/\s+/g, "").length,
        toast: /読み込み直します/.test(document.body?.innerText || ""),
        kouji: /工事中/.test(document.body?.innerText || ""),
      };
    })
    .catch(() => null);

async function waitSettled(targetHref, t0, maxMs = 30000) {
  let toast = false;
  let kouji = false;
  let last = null;
  while (Date.now() - t0 < maxMs) {
    const s = await state();
    if (s) {
      last = s;
      if (s.toast) toast = true;
      if (s.kouji) kouji = true;
      const at = targetHref ? decodeURI(s.href) === decodeURI(targetHref) : true;
      if (at && !s.pending && s.textLen > 80) return { ms: Date.now() - t0, toast, kouji, last };
    }
    await sleep(50);
  }
  return { ms: null, toast, kouji, last };
}

const hydrateWaits = [];
async function clickLink(re) {
  const href = await page.evaluate((src) => {
    const re = new RegExp(src);
    const as = [...document.querySelectorAll("a[href]")].filter((a) => {
      const h = a.getAttribute("href") || "";
      if (!re.test(h)) return false;
      const r = a.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    });
    const a = as[0];
    if (!a) return null;
    a.scrollIntoView({ block: "center" });
    a.setAttribute("data-kirikae", "1");
    return a.getAttribute("href");
  }, re.source);
  if (!href) return null;
  // 押せる状態（Reactが部品に手を付け終わった＝画面内で切り替えられる）まで待つ。待った時間も記録する。
  const tH = Date.now();
  await page
    .waitForFunction(
      () => {
        const a = document.querySelector('[data-kirikae="1"]');
        return !!a && Object.keys(a).some((k) => k.startsWith("__reactProps"));
      },
      null,
      { timeout: 30000, polling: 100 },
    )
    .catch(() => {});
  hydrateWaits.push(Date.now() - tH);
  await sleep(300);
  const t0 = Date.now();
  await page.evaluate(() => document.querySelector('[data-kirikae="1"]')?.click());
  return { href, t0 };
}

const steps = [
  ["棚", /^\/(shelf|world)\//],
  ["曲ページ", /^\/(cover-guide\?artist=[^&]+&song=|room\/card\/|watch\/)/],
  ["特集", /^\/feature\/[^/?#]+/],
];

const result = { base: BASE, stale: STALE, limitMs: LIMIT, net: "4G相当 往復100ms・下り5Mbps（共有）", at: new Date().toISOString(), steps: [] };
let ok = true;

// 最初の表示
const tInit = Date.now();
await page.goto(BASE + "/", { waitUntil: "commit", timeout: 60000 });
const init = await waitSettled("/", tInit, 60000);
result.first = { ms: init.ms };
await sleep(2500);
const docBefore = docLoads;
if (STALE) deployed = true; // ここで「新しい版が公開された」

const history = ["/"];
for (const [name, re] of steps) {
  let c = await clickLink(re);
  if (!c && name === "特集") {
    // 曲ページに特集リンクが無いときは、下のタブの「ホーム」で戻ってから特集を押す（これも1回の切り替えとして測る）
    const h = await clickLink(/^\/$/);
    if (h) {
      const r = await waitSettled("/", h.t0);
      const good = r.ms != null && r.ms <= LIMIT && !r.toast && !r.kouji;
      if (!good) ok = false;
      result.steps.push({ name: "ホームへ", href: "/", ms: r.ms, ok: good, toast: r.toast, kouji: r.kouji, end: r.last?.href });
      history.push("/");
      await sleep(1500);
      c = await clickLink(re);
    }
  }
  if (!c) {
    result.steps.push({ name, ok: false, why: "押せるリンクが見つからない", from: history.at(-1) });
    ok = false;
    continue;
  }
  const r = await waitSettled(c.href, c.t0);
  const good = r.ms != null && r.ms <= LIMIT && !r.toast && !r.kouji;
  if (!good) ok = false;
  result.steps.push({ name, href: c.href, ms: r.ms, ok: good, toast: r.toast, kouji: r.kouji, end: r.last?.href });
  history.push(c.href);
  await sleep(1500);
}
// 戻る
{
  const want = history.at(-2);
  const t0 = Date.now();
  await page.evaluate(() => history.back());
  const r = await waitSettled(want, t0);
  const good = r.ms != null && r.ms <= LIMIT && !r.toast && !r.kouji;
  if (!good) ok = false;
  result.steps.push({ name: "戻る", href: want, ms: r.ms, ok: good, toast: r.toast, kouji: r.kouji, end: r.last?.href });
}
result.fullReloads = docLoads - docBefore;
result.logs = logs.slice(0, 80);
result.hydrateWaitsMs = hydrateWaits;
result.ok = ok;
clearTimeout(killer);
await browser.close();
try { fs.unlinkSync(LOCK); } catch {}
const line = result.steps.map((s) => `${s.name}${s.ms == null ? "×" : (s.ms / 1000).toFixed(1) + "秒"}${s.ok ? "" : "(NG)"}`).join(" / ");
result.summary = `${STALE ? "[古い版を開いたまま公開]" : "[通常]"} 最初${init.ms ? (init.ms / 1000).toFixed(1) + "秒" : "×"} / ${line} / 丸ごと読み直し${result.fullReloads}回`;
console.log(JSON.stringify(result, null, 1));
if (OUT) fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
process.exit(ok ? 0 : 1);
