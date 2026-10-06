#!/usr/bin/env node
// 769番：既存のログイン済みChrome（dispatch/chrome-publishプロファイル・CDP 9223・headless）に
// 新しいタブを1枚追加し、creator.line.me（LINE Creators Market）のログイン状態だけを確認する。
// 確認が終わったら必ずタブを閉じる。何もクリックしない・何も入力しない・読み取りのみ。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

async function main() {
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9223", { timeout: 30000 });
  const ctx = browser.contexts()[0];
  const page = await ctx.newPage();
  try {
    await page.goto("https://creator.line.me/ja/", { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);
    console.log("URL:", page.url());
    console.log("TITLE:", await page.title());
    const snippet = await page.evaluate(() => document.body.innerText.slice(0, 400));
    console.log("BODY:", snippet.replace(/\n+/g, " | "));
  } finally {
    await page.close();
  }
}
main().catch((e) => {
  console.error("ERR:", e.message);
  process.exit(1);
});
