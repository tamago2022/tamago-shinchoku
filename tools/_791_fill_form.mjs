#!/usr/bin/env node
// 791番：LINE問い合わせフォームに、メールアドレス・カテゴリ・本文を実際に入力し、
// キャプチャ／送信ボタンの手前でスクリーンショットを撮る。送信は絶対にしない。
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

async function fill(browser, name, url, body) {
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(1500);
    const btn = page.getByText("ログインせずにつづける", { exact: false });
    if (await btn.count().catch(() => 0)) {
      await btn.first().click();
      await page.waitForTimeout(2500);
    }
    console.log("[" + name + "] URL:", page.url());

    // カテゴリselectの選択肢を確認
    const selectOptions = await page.evaluate(() => {
      const sels = Array.from(document.querySelectorAll("select"));
      return sels.map((s) => ({
        name: s.name,
        options: Array.from(s.options).map((o) => ({ value: o.value, text: o.text.trim() })),
        value: s.value,
      }));
    });
    console.log("[" + name + "] SELECTS:", JSON.stringify(selectOptions));

    // メールアドレス入力
    const emailInput = page.locator("#FnReplyMail");
    if (await emailInput.count()) {
      await emailInput.fill(EMAIL);
    }

    // 本文入力
    const textarea = page.locator("textarea[name='mdInput01SummaryTextarea']");
    if (await textarea.count()) {
      await textarea.fill(body);
    }

    await page.waitForTimeout(1000);
    const shot = "/tmp/791_filled_" + name + ".png";
    await page.screenshot({ path: shot, fullPage: true });
    console.log("[" + name + "] SCREENSHOT:", shot);

    // 送信ボタン・キャプチャ周辺の状態を確認（クリックはしない）
    const hasCaptchaImg = await page.locator("img[alt*='captcha' i], img[src*='captcha' i]").count().catch(() => 0);
    const captchaInputVal = await page.locator("input[placeholder='Enter the text in the image']").inputValue().catch(() => "");
    console.log("[" + name + "] captchaImgCount:", hasCaptchaImg, "captchaInputVal:", JSON.stringify(captchaInputVal));
  } catch (e) {
    console.log("[" + name + "] ERR:", e.message);
  } finally {
    await page.close();
  }
}

async function main() {
  const browser = await chromium.launch({
    headless: true,
    executablePath: CHROME,
    args: ["--mute-audio", "--no-sandbox"],
  });
  try {
    for (const [name, url, body] of targets) {
      await fill(browser, name, url, body);
    }
  } finally {
    await browser.close();
  }
}
main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
