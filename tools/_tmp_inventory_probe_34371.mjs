#!/usr/bin/env node
// 34371号専用の一回限り確認スクリプト。/admin/inventory を直接対象にする。
// ①ログイン前のスクショ ②合言葉を入れてログイン ③同じブラウザで再読込（新規タブ・履歴クリア相当）
//   して、ログイン欄が出ずに在庫ダッシュボードがそのまま出るかを確認する。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const BASE = "https://joy-relief-station.lovable.app";
const OUTDIR = "/Users/mac/tamago/tamago-shinchoku/status/public/34371";
fs.mkdirSync(OUTDIR, { recursive: true });

function findHeadless() {
  const root = path.join(os.homedir(), "Library", "Caches", "ms-playwright");
  let dirs = [];
  try { dirs = fs.readdirSync(root).filter((d) => d.startsWith("chromium_headless_shell-")).sort().reverse(); } catch { return undefined; }
  for (const d of dirs) {
    for (const sub of ["chrome-mac/headless_shell", "chrome-mac-arm64/headless_shell", "chrome-headless-shell-mac-arm64/chrome-headless-shell", "chrome-headless-shell-mac-x64/chrome-headless-shell"]) {
      const p = path.join(root, d, sub);
      if (fs.existsSync(p)) return p;
    }
  }
  return undefined;
}

let browser;
try {
  browser = await chromium.launch({ headless: true, args: ["--mute-audio"] });
} catch {
  browser = await chromium.launch({ headless: true, args: ["--mute-audio"], executablePath: findHeadless() });
}

const result = { base: BASE, path: "/admin/inventory", steps: [] };

const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const pwField = (p) => p.locator('input[name="password"][type="password"]');
const dashHeading = (p) => p.locator("text=📊 在庫ダッシュボード");

// どちらかが出るまで待つ（最大20秒）。出た方を返す。
async function waitEither(p) {
  try {
    await Promise.race([
      pwField(p).waitFor({ state: "visible", timeout: 20000 }),
      dashHeading(p).waitFor({ state: "visible", timeout: 20000 }),
    ]);
  } catch { /* どちらも出なかった＝タイムアウト。後続のisVisibleでfalseになる */ }
  await p.waitForTimeout(500);
}

try {
  // 1) まっさらな状態で /admin/inventory を開く → ログイン欄が出るはず
  await page.goto(BASE + "/admin/inventory", { waitUntil: "domcontentloaded", timeout: 60000 });
  await waitEither(page);
  const sawLoginBefore = await pwField(page).isVisible().catch(() => false);
  await page.screenshot({ path: path.join(OUTDIR, "1_before_login.png") });
  result.steps.push({ step: "fresh_visit", sawLoginForm: sawLoginBefore });

  if (sawLoginBefore) {
    await pwField(page).fill("@");
    await page.locator('button[type="submit"], form button').first().click();
    // ログイン後は23,000曲ぶんのデータ取得が走るので長めに待つ
    await dashHeading(page).waitFor({ state: "visible", timeout: 30000 }).catch(() => {});
  }
  await page.screenshot({ path: path.join(OUTDIR, "2_after_login.png") });
  const dashVisibleAfterLogin = await dashHeading(page).isVisible().catch(() => false);
  result.steps.push({ step: "after_login", dashVisible: dashVisibleAfterLogin });

  // 2) 同じブラウザ（Cookie保持）で再読込 → ログイン欄が出ないはず
  await page.reload({ waitUntil: "domcontentloaded", timeout: 60000 });
  await waitEither(page);
  const sawLoginAfterReload = await pwField(page).isVisible().catch(() => false);
  const dashVisibleAfterReload = await dashHeading(page).isVisible().catch(() => false);
  await page.screenshot({ path: path.join(OUTDIR, "3_after_reload.png") });
  result.steps.push({ step: "reload_same_browser", sawLoginForm: sawLoginAfterReload, dashVisible: dashVisibleAfterReload });

  // 3) 新しいタブ（同じCookieコンテキスト内）で開き直す → これも聞かれないはず
  const page2 = await ctx.newPage();
  await page2.goto(BASE + "/admin/inventory", { waitUntil: "domcontentloaded", timeout: 60000 });
  await waitEither(page2);
  const sawLoginNewTab = await pwField(page2).isVisible().catch(() => false);
  const dashVisibleNewTab = await dashHeading(page2).isVisible().catch(() => false);
  await page2.screenshot({ path: path.join(OUTDIR, "4_new_tab.png") });
  result.steps.push({ step: "new_tab_same_context", sawLoginForm: sawLoginNewTab, dashVisible: dashVisibleNewTab });

  result.ok = dashVisibleAfterLogin && !sawLoginAfterReload && dashVisibleAfterReload && !sawLoginNewTab && dashVisibleNewTab;
} catch (e) {
  result.error = String(e).slice(0, 300);
  result.ok = false;
} finally {
  await browser.close();
}

fs.writeFileSync(path.join(OUTDIR, "result.json"), JSON.stringify(result, null, 1));
console.log(JSON.stringify(result));
