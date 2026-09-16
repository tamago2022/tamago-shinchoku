#!/usr/bin/env node
/**
 * 769番：LINE Creators Market専用プロファイル(~/.tamago/chrome-line・CDP 9224)の
 * ログイン状態だけを確認する。フォーム入力や審査リクエストなど、ページの内容を
 * 書き換える操作は一切しない（読み取りのみ）。
 *
 * 判定：
 *   NO_CHROME  … 9224番でChromeが起動していない（start_chrome_line_login.shをまだ実行していない）
 *   NOT_LOGIN  … Chromeは起動しているが、LINEにログインしていない（「登録はこちら」画面）
 *   LOGGED_IN  … ログイン済み（マイページ相当の表示が出ている）
 *
 * 使い方: node tools/line_login_check.mjs
 */
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
const require = createRequire(import.meta.url);

const CDP_URL = "http://127.0.0.1:9224";

async function main() {
  let version;
  try {
    version = await (await fetch(`${CDP_URL}/json/version`, { signal: AbortSignal.timeout(3000) })).json();
  } catch {
    console.log(JSON.stringify({ state: "NO_CHROME", detail: "9224番でChromeが起動していません" }));
    return;
  }
  const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));
  const browser = await chromium.connectOverCDP(CDP_URL, { timeout: 15000 });
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  try {
    // 2026-09-16是正（案件#883）：/ja/dashboard は実在しないURL（404「指定された
    // ページは存在しません」）だったため、旧ロジック（本文にlogin/登録はこちらを
    // 含まない=ログイン済み、という判定）は404ページを常にLOGGED_INと誤判定する
    // バグがあった。正しいトップページ(/ja/)から「マイページ」リンクの実際の遷移先
    // (href)で判定する方式に修正。未ログイン時はhrefが/signup/line_authになる。
    await page.goto("https://creator.line.me/ja/", { waitUntil: "domcontentloaded", timeout: 20000 });
    await page.waitForTimeout(1500);
    const mypageHref = await page.evaluate(() => {
      const a = Array.from(document.querySelectorAll("a")).find((el) => el.textContent.includes("マイページ"));
      return a ? a.getAttribute("href") : null;
    });
    const loggedIn = !!mypageHref && !mypageHref.includes("/signup/line_auth");
    console.log(JSON.stringify({
      state: loggedIn ? "LOGGED_IN" : "NOT_LOGIN",
      url: page.url(),
      mypageHref,
      browser: version.Browser || null,
    }));
  } finally {
    await page.close();
  }
}
main().catch((e) => {
  console.log(JSON.stringify({ state: "ERROR", detail: e.message }));
  process.exit(1);
});
