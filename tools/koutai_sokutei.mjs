#!/usr/bin/env node
/**
 * 101885番【後退させない関所・測る係】ページを headless shell で開いて、数字だけ取る。判定しない。
 *
 * 測るもの（1ページにつき）
 *   ・1ページ目の時間：LCP（一番大きい絵/文字が出るまで）／FCP／load。4G相当に絞って測る
 *     （Lighthouse 公式の既定 "Slow 4G"：RTT 150ms・下り 1.6Mbps・上り 750Kbps・CPU 4倍遅く）
 *   ・送る量：JS / CSS / HTML / 画像 / フォント / データ(JSON) / その他 のKB（Network.loadingFinished の encodedDataLength）
 *   ・見た目（design-critique 5観点のうち機械で測れる4つの材料）：
 *       一貫性＝使っている書体の数・文字色の数／階層＝h1の数と「一番大きい文字がh1か」・文字サイズの種類数
 *       細部＝横に流れていないか(375px)・12px未満の文字・寸法の無い画像／機能＝壊れた画像・hrefの無いリンク・44px未満の押し物・コンソールエラー
 *     ★創造性は機械で測れない。測ったふりをしない（null）。
 *
 * 倣ったもの（オリジナル禁止・票 hyo-1792079434）
 *   tools/omosa.mjs（バイトの数え方）／tools/perf_watch.mjs（LCP）／tools/kirikae_sokutei.mjs（playwright-core + muonLaunch）
 *   Playwright 公式 CDPSession／Lighthouse throttling 既定値
 *
 * 安全：画面に出ない headless shell・無音（muon.mjs）・GETだけ・課金0・たまごさんのChrome/Braveに触らない。
 *
 * 使い方：node tools/koutai_sokutei.mjs --pages pages.json --out result.json [--runs 2] [--throttle slow4g|fast4g|none] [--width 375]
 *   pages.json = [{"key":"top","url":"https://..."}, ...]
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { muonLaunch } from "./muon.mjs";

const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const argv = process.argv.slice(2);
const argVal = (n, d) => { const i = argv.indexOf(n); return i >= 0 && argv[i + 1] ? argv[i + 1] : d; };
const PAGES_FILE = argVal("--pages", "");
const OUT = argVal("--out", "");
const RUNS = Math.max(1, Number(argVal("--runs", 2)));
const THROTTLE = argVal("--throttle", "fast4g"); // 実測(2026-10-16)：slow4g は本番で LCP 7〜14秒・timeout が出て物差しとして荒い。4G相当＝DevTools の Fast 4G 既定
const WIDTH = Number(argVal("--width", 375));
const SETTLE_MS = Number(argVal("--settle", 2500));
const NAV_TIMEOUT = Number(argVal("--timeout", 90000));
if (!PAGES_FILE || !OUT) { console.error("使い方: --pages pages.json --out result.json"); process.exit(1); }

// Lighthouse 既定（lighthouse-core/config/constants.js の throttling）
const THROTTLES = {
  slow4g: { latency: 150, downloadThroughput: 1.6 * 1024 * 1024 / 8, uploadThroughput: 750 * 1024 / 8, cpu: 4 },
  fast4g: { latency: 20, downloadThroughput: 4 * 1024 * 1024 / 8, uploadThroughput: 3 * 1024 * 1024 / 8, cpu: 2 },
  none: null,
};
const TH = THROTTLES[THROTTLE] ?? THROTTLES.slow4g;

// 置いてある headless shell（窓の出ない裸の実行ファイル）を探す（tools/daimei_kakunin.mjs と同じ）
function findShell() {
  const base = path.join(os.homedir(), "Library", "Caches", "ms-playwright");
  try {
    for (const d of fs.readdirSync(base).filter((x) => x.startsWith("chromium_headless_shell-")).sort().reverse()) {
      for (const sub of ["chrome-headless-shell-mac-arm64", "chrome-headless-shell-mac-x64"]) {
        const p = path.join(base, d, sub, "chrome-headless-shell");
        if (fs.existsSync(p)) return p;
      }
    }
  } catch {}
  return "";
}
const exe = (() => { try { const p = chromium.executablePath(); return fs.existsSync(p) ? "" : findShell(); } catch { return findShell(); } })();

const KIND = (r) => {
  const u = (r.url || "").split("?")[0].toLowerCase();
  const m = (r.mime || "").toLowerCase();
  if (r.type === "Document" || m.includes("text/html")) return "HTML";
  if (r.type === "Script" || m.includes("javascript") || u.endsWith(".js") || u.endsWith(".mjs")) return "JS";
  if (r.type === "Stylesheet" || m.includes("text/css") || u.endsWith(".css")) return "CSS";
  if (r.type === "Image" || m.startsWith("image/")) return "画像";
  if (r.type === "Font" || m.includes("font") || /\.(woff2?|ttf|otf|eot)$/.test(u)) return "フォント";
  if (m.includes("json") || u.endsWith(".json")) return "データ";
  if (r.type === "Media" || m.startsWith("video/") || m.startsWith("audio/")) return "動画音声";
  return "その他";
};
const shortName = (u) => { try { const x = new URL(u); return x.hostname + x.pathname; } catch { return String(u).slice(0, 120); } };

// ページに最初から仕込む見張り（LCP / CLS / FCP）— perf_watch.mjs・omosa.mjs の WATCHER と同じ考え方
const WATCHER = `(() => {
  window.__kt = { lcp: null, cls: 0 };
  try { new PerformanceObserver((l) => { const e = l.getEntries().pop(); if (e) window.__kt.lcp = Math.round(e.renderTime || e.loadTime || e.startTime); })
        .observe({ type: 'largest-contentful-paint', buffered: true }); } catch (e) {}
  try { let cur=0, first=0, last=0; new PerformanceObserver((l) => { for (const e of l.getEntries()) { if (e.hadRecentInput) continue;
        if (cur && (e.startTime - last > 1000 || e.startTime - first > 5000)) { cur = 0; first = e.startTime; }
        if (!cur) first = e.startTime; last = e.startTime; cur += e.value; if (cur > window.__kt.cls) window.__kt.cls = cur; } })
        .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
})()`;

const DESIGN = `(() => {
  const vw = window.innerWidth;
  const out = {};
  const all = Array.from(document.querySelectorAll('body *'));
  const vis = [];
  for (const e of all) { if (vis.length >= 1500) break; const r = e.getBoundingClientRect(); if (r.width > 0 && r.height > 0 && r.top < 4000) vis.push([e, r]); }
  const hasText = (e) => Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
  const fonts = new Set(), colors = new Set(), sizes = new Set();
  let small = 0, maxSize = 0, maxIsH1 = false;
  for (const [e] of vis) {
    if (!hasText(e)) continue;
    const cs = getComputedStyle(e);
    fonts.add((cs.fontFamily || '').split(',')[0].trim().replace(/["']/g, '').toLowerCase());
    colors.add(cs.color);
    const fs = Math.round(parseFloat(cs.fontSize) || 0);
    if (fs) { sizes.add(fs); if (fs < 12) small++; if (fs > maxSize) { maxSize = fs; maxIsH1 = e.tagName === 'H1' || !!e.closest('h1'); } }
  }
  const imgs = Array.from(document.images);
  out.fonts = fonts.size; out.colors = colors.size; out.sizes = sizes.size; out.smallText = small;
  out.h1 = document.querySelectorAll('h1').length; out.maxIsH1 = maxIsH1; out.maxFontPx = maxSize;
  out.overflowX = document.documentElement.scrollWidth > vw + 1;
  out.scrollWidth = document.documentElement.scrollWidth; out.vw = vw;
  out.imgs = imgs.length;
  out.imgsBroken = imgs.filter(i => i.complete && i.naturalWidth === 0 && i.getAttribute('src')).length;
  out.imgsNoDims = imgs.filter(i => !i.getAttribute('width') && !i.getAttribute('height') && !(getComputedStyle(i).aspectRatio && getComputedStyle(i).aspectRatio !== 'auto')).length;
  out.linksNoHref = Array.from(document.querySelectorAll('a')).filter(a => !a.getAttribute('href')).length;
  let tiny = 0;
  for (const [e, r] of vis) { if ((e.tagName === 'A' || e.tagName === 'BUTTON') && (r.width < 44 || r.height < 44) && r.width > 0) tiny++; }
  out.tinyTargets = tiny;
  out.textLen = (document.body.innerText || '').length;
  return out;
})()`;

const clamp = (v) => Math.max(0, Math.min(10, Math.round(v)));
function scores(d, consoleErrors) {
  if (!d) return null;
  const ikkansei = clamp(10 - 2 * Math.max(0, d.fonts - 2) - Math.max(0, d.colors - 12) * 0.5);
  let kaisou = d.h1 === 1 ? 10 : d.h1 === 0 ? 5 : 7;
  if (!d.maxIsH1) kaisou -= 1;
  kaisou -= Math.min(3, Math.floor(Math.max(0, d.sizes - 8) / 2));
  // imgsNoDims は遅延読み込みの画像がどこまで来たかで毎回ゆれる（実測 2026-10-16：棚 30→39点）ので点数には入れない（材料としては残す）
  const saibu = clamp(10 - (d.overflowX ? 4 : 0) - Math.min(3, Math.floor(d.smallText / 5)));
  const kinou = clamp(10 - Math.min(4, d.imgsBroken * 2) - Math.min(2, d.linksNoHref) - Math.min(2, Math.floor(d.tinyTargets / 5)) - Math.min(2, consoleErrors));
  return { ikkansei, kaisou: clamp(kaisou), saibu, kinou, souzousei: null, kikai_gokei: ikkansei + clamp(kaisou) + saibu + kinou };
}

async function measureOnce(browser, pg) {
  const ctx = await browser.newContext({
    viewport: { width: WIDTH, height: Math.round(WIDTH * 2.16) }, deviceScaleFactor: 2, isMobile: WIDTH < 600, hasTouch: WIDTH < 600,
    userAgent: WIDTH < 600 ? "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1 koutai-kanmon" : undefined,
  });
  const page = await ctx.newPage();
  await page.addInitScript(WATCHER);
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(String(m.text()).slice(0, 160)); });
  page.on("pageerror", (e) => consoleErrors.push("pageerror:" + String(e.message || e).slice(0, 160)));
  const cdp = await ctx.newCDPSession(page);
  await cdp.send("Network.enable", { maxTotalBufferSize: 100e6, maxResourceBufferSize: 50e6 });
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  if (TH) {
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: TH.latency, downloadThroughput: TH.downloadThroughput, uploadThroughput: TH.uploadThroughput });
    await cdp.send("Emulation.setCPUThrottlingRate", { rate: TH.cpu });
  }
  const byId = new Map(); const done = [];
  cdp.on("Network.responseReceived", (p) => byId.set(p.requestId, { url: p.response?.url || "", type: p.type || "Other", mime: p.response?.mimeType || "", status: p.response?.status || 0 }));
  cdp.on("Network.loadingFinished", (p) => { const r = byId.get(p.requestId); if (!r) return; done.push({ ...r, bytes: Math.max(0, p.encodedDataLength || 0) }); byId.delete(p.requestId); });

  const t0 = Date.now();
  let status = 0, navErr = "";
  try { const resp = await page.goto(pg.url, { waitUntil: "load", timeout: NAV_TIMEOUT }); status = resp ? resp.status() : 0; }
  catch (e) { navErr = String(e.message || e).slice(0, 200); }
  await page.waitForTimeout(SETTLE_MS);
  try { await page.waitForLoadState("networkidle", { timeout: 15000 }); } catch {}

  const timing = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    const fcp = performance.getEntriesByType("paint").find((p) => p.name === "first-contentful-paint");
    return { dcl: nav ? Math.round(nav.domContentLoadedEventEnd) : null, load: nav ? Math.round(nav.loadEventEnd) : null,
             fcp: fcp ? Math.round(fcp.startTime) : null, lcp: window.__kt?.lcp ?? null, cls: Math.round((window.__kt?.cls ?? 0) * 1000) / 1000 };
  }).catch(() => ({ dcl: null, load: null, fcp: null, lcp: null, cls: null }));
  const design = await page.evaluate(DESIGN).catch(() => null);

  const bytes = {}; let total = 0; let own = 0; const ownBytes = {};
  let host = ""; try { host = new URL(pg.url).host; } catch {}
  for (const r of done) {
    const k = KIND(r); bytes[k] = (bytes[k] || 0) + r.bytes; total += r.bytes;
    let h = ""; try { h = new URL(r.url).host; } catch {}
    if (h === host) { own += r.bytes; ownBytes[k] = (ownBytes[k] || 0) + r.bytes; }
  }
  const top = done.slice().sort((a, b) => b.bytes - a.bytes).slice(0, 12).map((r) => ({ name: shortName(r.url), kind: KIND(r), kb: Math.round(r.bytes / 1024) }));
  await ctx.close();
  return {
    key: pg.key, url: pg.url, status, navErr, wallMs: Date.now() - t0,
    timeMs: timing, firstPageMs: timing.lcp ?? timing.load ?? null,
    bytes: { total, ...bytes }, kb: Object.fromEntries(Object.entries({ total, ...bytes }).map(([k, v]) => [k, Math.round(v / 1024)])),
    ownBytes: { total: own, ...ownBytes }, ownKb: Object.fromEntries(Object.entries({ total: own, ...ownBytes }).map(([k, v]) => [k, Math.round(v / 1024)])),
    requests: done.length, top, design, scores: scores(design, consoleErrors.length), consoleErrors: consoleErrors.slice(0, 8),
  };
}

const pages = JSON.parse(fs.readFileSync(PAGES_FILE, "utf8"));
const browser = await muonLaunch(chromium, exe ? { headless: true, executablePath: exe } : { headless: true });
const result = { measuredAt: new Date().toISOString(), throttle: THROTTLE, throttleSpec: TH, width: WIDTH, runs: RUNS, exe: exe || "playwright既定", pages: [] };
try {
  for (const pg of pages) {
    const runs = [];
    for (let i = 0; i < RUNS; i++) { try { runs.push(await measureOnce(browser, pg)); } catch (e) { runs.push({ key: pg.key, url: pg.url, status: 0, navErr: "MEASURE_FAIL:" + String(e.message || e).slice(0, 160), firstPageMs: null, bytes: { total: 0 }, kb: { total: 0 }, design: null, scores: null, consoleErrors: [] }); } }
    // 複数回のうち「一番良い回」を採る（Lighthouse と同じく、たまたまの引っかかりを後退と誤判定しない）
    const ok = runs.filter((r) => r.firstPageMs != null);
    const best = Object.assign({}, ok.length ? ok.reduce((a, b) => (a.firstPageMs <= b.firstPageMs ? a : b)) : runs[0]);
    // 送る量は「一番たくさん取れた回」を採る（途中で切れた回の少ない数字を『軽くなった』と誤読しない）
    const full = runs.reduce((a, b) => (((b.ownBytes?.total ?? 0) > (a.ownBytes?.total ?? 0)) ? b : a));
    for (const k of ["bytes", "kb", "ownBytes", "ownKb", "top", "requests"]) if (full[k] !== undefined) best[k] = full[k];
    best.allRuns = runs.map((r) => ({ firstPageMs: r.firstPageMs, totalKb: r.kb?.total ?? null, ownKb: r.ownKb?.total ?? null, status: r.status, navErr: r.navErr || "" }));
    result.pages.push(best);
    console.error(`[koutai_sokutei] ${pg.key}: status=${best.status} first=${best.firstPageMs}ms own=${best.ownKb?.total}KB total=${best.kb?.total}KB score=${best.scores?.kikai_gokei ?? "-"}/40 ${best.navErr || ""}`);
  }
} finally { await browser.close().catch(() => {}); }
fs.mkdirSync(path.dirname(path.resolve(OUT)), { recursive: true });
fs.writeFileSync(OUT, JSON.stringify(result, null, 1));
console.error(`[koutai_sokutei] → ${OUT}`);
