#!/usr/bin/env node
// 791番・3回目（経路変更）：新規Chrome起動(launch)がハングしたため、
// 既存の稼働中headless Chrome（dispatch/chrome-publishプロファイル・CDP 9223）へ
// 新しいタブとして接続する方式に切り替える（769番の既存実績と同じ経路）。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const EMAIL = "eggypop2010@gmail.com";
const bodyA = fs.readFileSync("/tmp/791_body_a.txt", "utf-8");
const bodyB = fs.readFileSync("/tmp/791_body_b.txt", "utf-8");
const targets = [
  ["creators-market", "https://contact.line.me/serviceId/10569", bodyA],
  ["sticker-maker", "https://contact-cc.line.me/detailId/11844", bodyB],
];

const LOGF = "/tmp/791_fill3.log";
const log = (...a) => fs.appendFileSync(LOGF, new Date().toISOString() + " " + a.join(" ") + "\n");

async function fill(ctx, name, url, body) {
  log(name, "STEP1 newPage");
  const page = await ctx.newPage();
  page.setDefaultTimeout(15000);
  try {
    log(name, "STEP2 goto");
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
    log(name, "STEP3 goto done", page.url());
    await page.waitForTimeout(1500);
    const btn = page.getByText("ログインせずにつづける", { exact: false });
    const c = await btn.count().catch(() => 0);
    log(name, "STEP4 continueBtnCount", String(c));
    if (c > 0) {
      await btn.first().click({ timeout: 10000 });
      log(name, "STEP5 clicked continue");
      await page.waitForTimeout(2000);
    }
    log(name, "STEP6 fill email");
    await page.locator("#FnReplyMail").fill(EMAIL, { timeout: 10000 }).catch((e) => log(name, "email fill ERR", e.message));
    log(name, "STEP7 fill body");
    await page.locator("textarea[name='mdInput01SummaryTextarea']").fill(body, { timeout: 10000 }).catch((e) => log(name, "body fill ERR", e.message));
    log(name, "STEP8 screenshot");
    const shot = "/tmp/791_filled_" + name + ".png";
    await page.screenshot({ path: shot, timeout: 15000 }).catch((e) => log(name, "screenshot ERR", e.message));
    log(name, "STEP9 done", shot);
  } catch (e) {
    log(name, "FATAL ERR", e.message);
  } finally {
    await page.close().catch(() => {});
  }
}

async function main() {
  log("connecting CDP 9223");
  const browser = await chromium.connectOverCDP("http://127.0.0.1:9223", { timeout: 20000 });
  log("connected");
  const ctx = browser.contexts()[0];
  try {
    for (const [name, url, body] of targets) {
      await fill(ctx, name, url, body);
    }
  } finally {
    // 共有ブラウザ(Lovable公開便等が使う既存プロセス)は絶対に閉じない。
    // 接続だけを切る（disconnectが無い版もあるためcatchで握りつぶす）。
    if (typeof browser.disconnect === "function") {
      await browser.disconnect().catch(() => {});
    }
  }
  log("ALL DONE");
}
main().catch((e) => {
  log("MAIN FATAL", e.message);
  process.exit(1);
});
