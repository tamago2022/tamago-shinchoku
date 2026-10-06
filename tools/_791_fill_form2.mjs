#!/usr/bin/env node
// 791番・改良版：各ステップにタイムアウトと詳細ログを付けて、どこで詰まるか分かるようにする。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
import fs from "node:fs";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const EMAIL = "eggypop2010@gmail.com";
const bodyA = fs.readFileSync("/tmp/791_body_a.txt", "utf-8");
const bodyB = fs.readFileSync("/tmp/791_body_b.txt", "utf-8");
const targets = [
  ["creators-market", "https://contact.line.me/serviceId/10569", bodyA],
  ["sticker-maker", "https://contact-cc.line.me/detailId/11844", bodyB],
];

const log = (...a) => console.log(new Date().toISOString(), ...a);

async function fill(browser, name, url, body) {
  log(name, "STEP1 newPage");
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  try {
    log(name, "STEP2 goto");
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
    log(name, "STEP3 goto done", page.url());
    await page.waitForTimeout(1500);
    const btn = page.getByText("ログインせずにつづける", { exact: false });
    const c = await btn.count().catch(() => 0);
    log(name, "STEP4 continueBtnCount", c);
    if (c > 0) {
      await btn.first().click({ timeout: 10000 });
      log(name, "STEP5 clicked continue");
      await page.waitForTimeout(2000);
    }
    log(name, "STEP6 fill email");
    await page.locator("#FnReplyMail").fill(EMAIL, { timeout: 10000 }).catch((e) => log(name, "email fill ERR", e.message));
    log(name, "STEP7 fill body");
    await page.locator("textarea[name='mdInput01SummaryTextarea']").fill(body, { timeout: 10000 }).catch((e) => log(name, "body fill ERR", e.message));
    log(name, "STEP8 screenshot(viewport only)");
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
  log("launching browser");
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME,
    args: ["--mute-audio", "--no-sandbox", "--disable-gpu"],
  });
  log("browser launched");
  try {
    for (const [name, url, body] of targets) {
      await fill(browser, name, url, body);
    }
  } finally {
    await browser.close().catch(() => {});
  }
  log("ALL DONE");
}
main().catch((e) => {
  console.error("MAIN FATAL:", e.message);
  process.exit(1);
});
