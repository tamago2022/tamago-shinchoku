#!/usr/bin/env node
// 791番：LINE問い合わせフォームのDOM構造を読み取るだけ（入力・送信はしない）。
// 新規headless Chromeを一時プロファインで起動し、たまごさんの通常ブラウザには一切触れない。
import { createRequire } from "node:module";
import os from "node:os";
import path from "node:path";
const require = createRequire(import.meta.url);
const { chromium } = require(path.join(os.homedir(), ".tamago", "node_modules", "playwright-core"));

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const urls = [
  "https://contact.line.me/serviceId/10569",
  "https://contact-cc.line.me/detailId/11844",
];

async function inspect(browser, url) {
  const page = await browser.newPage();
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
    await page.waitForTimeout(2500);
    console.log("=== URL:", page.url(), "===");
    console.log("TITLE:", await page.title());
    const info = await page.evaluate(() => {
      const els = Array.from(document.querySelectorAll("input, textarea, select, button"));
      return els.map((el) => ({
        tag: el.tagName,
        type: el.type || "",
        name: el.name || "",
        id: el.id || "",
        placeholder: el.placeholder || "",
        label: el.closest("label")?.innerText?.slice(0, 60) || "",
        text: el.tagName === "BUTTON" ? el.innerText?.slice(0, 40) : "",
      }));
    });
    console.log(JSON.stringify(info, null, 1));
  } catch (e) {
    console.log("ERR for", url, ":", e.message);
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
    for (const url of urls) {
      await inspect(browser, url);
    }
  } finally {
    await browser.close();
  }
}
main().catch((e) => {
  console.error("FATAL:", e.message);
  process.exit(1);
});
