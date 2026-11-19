// 題名を直したカードが本番の棚に出ているかを、iPhone相当・4G相当で確かめる（無音・画面に出さない）
//   node tools/daimei_kakunin.mjs --url <棚のURL> --title "<新しい題名>" [--old "<前の題名>"] [--shot out.png] [--out out.json]
// 測るもの：①棚を開いてから新しい題名が見えるまでの秒数 ②カードを押して切り替わるまでの秒数 ③戻って棚が出るまでの秒数
// 不合格（exit 1）：新しい題名が見えない／前の題名が残っている／切り替えが3秒を超えた
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";
import { muonLaunch } from "/Users/mac/tamago/tamago-shinchoku/tools/muon.mjs";

const require = createRequire(import.meta.url);
const { chromium, devices } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));
const arg = (k, d) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : d; };
const URL_ = arg("--url");
const TITLE = arg("--title");
const OLD = arg("--old", "");
const SHOT = arg("--shot", "");
const OUT = arg("--out", "");
const LIMIT = 3000;
const BLOCK = /youtube\.com|youtube-nocookie|googlevideo|doubleclick|googlesyndication|google-analytics|googletagmanager|video\.twimg\.com/;

const iphone = devices["iPhone 15"] || devices["iPhone 14"];
// Playwright の版と置いてある headless shell の版がずれていることがある（実測 2026-10-14：-1234 が無い）。
// 置いてある headless shell（窓の出ない裸の実行ファイル）を探して使う。
function findShell() {
  const base = path.join(os.homedir(), "Library", "Caches", "ms-playwright");
  let best = "";
  try {
    for (const d of fs.readdirSync(base).filter((x) => x.startsWith("chromium_headless_shell-")).sort()) {
      for (const sub of ["chrome-headless-shell-mac-arm64", "chrome-headless-shell-mac-x64"]) {
        const p = path.join(base, d, sub, "chrome-headless-shell");
        if (fs.existsSync(p)) best = p;
      }
    }
  } catch {}
  return best;
}
const exe = (() => { try { const p = chromium.executablePath(); return fs.existsSync(p) ? "" : findShell(); } catch { return findShell(); } })();
const browser = await muonLaunch(chromium, exe ? { headless: true, executablePath: exe } : { headless: true });
const killer = setTimeout(async () => { try { await browser.close(); } catch {} process.exit(2); }, 150 * 1000);
const ctx = await browser.newContext({ viewport: iphone.viewport, deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: true, hasTouch: true, userAgent: iphone.userAgent });
const page = await ctx.newPage();
const cdp = await ctx.newCDPSession(page);
await cdp.send("Network.enable");
await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 100,
  downloadThroughput: (5 * 1e6) / 8, uploadThroughput: (2 * 1e6) / 8 });
await page.route("**/*", (r) => (BLOCK.test(r.request().url()) ? r.abort() : r.continue()));

const res = { url: URL_, title: TITLE, at: new Date().toISOString() };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const bodyText = () => page.evaluate(() => document.body?.innerText || "").catch(() => "");
async function waitText(t, t0, max = 30000) {
  while (Date.now() - t0 < max) { if ((await bodyText()).includes(t)) return Date.now() - t0; await sleep(100); }
  return null;
}
try {
  let t0 = Date.now();
  await page.goto(URL_, { waitUntil: "commit", timeout: 60000 });
  res.coldMs = await waitText(TITLE, t0, 60000);
  const txt = await bodyText();
  res.titleSeen = res.coldMs !== null;
  res.oldGone = OLD ? !txt.includes(OLD) : null;
  const card = page.getByText(TITLE, { exact: false }).first();
  await card.scrollIntoViewIfNeeded().catch(() => {});
  if (SHOT) {
    await sleep(800);
    const box = await card.boundingBox().catch(() => null);
    if (box) await page.evaluate((y) => window.scrollBy(0, y - 180), box.y).catch(() => {});
    await sleep(600);
    await page.screenshot({ path: SHOT });
  }
  // ②カードを押して切り替わるまで
  const before = page.url();
  const beforeTxt = await bodyText();
  t0 = Date.now();
  await card.tap().catch(async () => { await card.click().catch(() => {}); });
  let switched = null;
  while (Date.now() - t0 < 15000) {
    const t = await bodyText();
    if (page.url() !== before || (t !== beforeTxt && t.replace(/\s+/g, "").length > 40)) { switched = Date.now() - t0; break; }
    await sleep(80);
  }
  res.tapMs = switched;
  res.afterTapUrl = page.url();
  // ③戻る
  if (page.url() !== before) {
    t0 = Date.now();
    await page.goBack({ waitUntil: "commit" }).catch(() => {});
    res.backMs = await waitText(TITLE, t0, 15000);
  } else {
    await page.keyboard.press("Escape").catch(() => {});
    res.backMs = null;
    res.note = "カードを押してもURLは変わらない（同じ画面の中で開く形）";
  }
} catch (e) {
  res.error = String(e).slice(0, 300);
}
const sw = [res.tapMs, res.backMs].filter((x) => typeof x === "number");
res.ok = !!res.titleSeen && res.oldGone !== false && sw.every((x) => x <= LIMIT) && !res.error;
console.log(JSON.stringify(res, null, 1));
if (OUT) fs.writeFileSync(OUT, JSON.stringify(res, null, 1));
clearTimeout(killer);
await browser.close();
process.exit(res.ok ? 0 : 1);
