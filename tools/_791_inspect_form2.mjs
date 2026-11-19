#!/usr/bin/env node
// 791番：「ログインせずにつづける」を押した先のフォーム構造を読み取るだけ（入力・送信はしない）。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const urls = [
  ["creators-market", "https://contact.line.me/serviceId/10569"],
  ["sticker-maker", "https://contact-cc.line.me/detailId/11844"],
];

async function inspect(browser, name, url) {
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2000);
    // 「ログインせずにつづける」ボタンを探してクリック
    const btn = page.getByText("ログインせずにつづける", { exact: false });
    const count = await btn.count().catch(() => 0);
    console.log(name, "続けるボタン数:", count);
    if (count > 0) {
      await btn.first().click();
      await page.waitForTimeout(3000);
    }
    console.log("=== [" + name + "] URL:", page.url(), "===");
    console.log("TITLE:", await page.title());
    const info = await page.evaluate(() => {
      const els = Array.from(document.querySelectorAll("input, textarea, select, button"));
      return els.map((el) => ({
        tag: el.tagName,
        type: el.type || "",
        name: el.name || "",
        id: el.id || "",
        placeholder: el.placeholder || "",
        required: el.required || false,
        label: el.closest("label")?.innerText?.slice(0, 60) || "",
        text: (el.tagName === "BUTTON" || el.tagName === "OPTION") ? el.innerText?.slice(0, 40) : "",
      }));
    });
    console.log(JSON.stringify(info, null, 1));
    const shot = "/tmp/791_" + name + ".png";
    await page.screenshot({ path: shot, fullPage: true });
    console.log("SCREENSHOT:", shot);
  } catch (e) {
    console.log("ERR for", name, ":", e.message);
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
    for (const [name, url] of urls) {
      await inspect(browser, name, url);
    }
  } finally {
    await browser.close();
  }
}
main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
