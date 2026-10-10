#!/usr/bin/env node
/**
 * 1168番：出す前に自分でスマホ幅で開いて見るためのスクショ。
 *
 * 方式は他の検品と同じ：headless Chrome・一時プロファイル・使用後SIGKILL。
 * ★たまごさんの通常のChrome／Braveには一切触れない。タブも開かない。
 *
 * 使い方: node tools/1168_shot.mjs <URLかfile:パス> <出力PNG> [幅]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const TARGET = process.argv[2];
const OUT = resolve(process.argv[3]);
const W = Number(process.argv[4] || 390);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
if (!TARGET || !OUT) { console.error("使い方: node tools/1168_shot.mjs <URL> <PNG> [幅]"); process.exit(1); }

const port = 9500 + Math.floor(Math.random() * 400);
const prof = mkdtempSync(`${tmpdir()}/t1168-`);
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--no-default-browser-check", "--allow-file-access-from-files",
  "--hide-scrollbars", "about:blank",
], { stdio: "ignore" });

async function findPage() {
  for (let i = 0; i < 200; i++) {
    try {
      const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = l.find((t) => t.type === "page");
      if (p?.webSocketDebuggerUrl) return p;
    } catch { /* 起動待ち */ }
    await sleep(300);
  }
  throw new Error("Chromeのデバッグ口が開かない");
}

try {
  const page = await findPage();
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0; const pend = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  });
  await new Promise((res, rej) => {
    ws.addEventListener("open", res); ws.addEventListener("error", () => rej(new Error("CDP失敗")));
  });
  const send = (method, params = {}) => new Promise((res) => {
    const i = ++id; pend.set(i, (m) => res(m.result));
    ws.send(JSON.stringify({ id: i, method, params }));
  });

  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride",
    { width: W, height: 900, deviceScaleFactor: 2, mobile: true });
  await send("Page.navigate", { url: TARGET });
  await sleep(3500);
  const { result: h } = await send("Runtime.evaluate",
    { expression: "document.documentElement.scrollHeight", returnByValue: true });
  const full = Math.min(Number(h?.value || 2000), 20000);
  await send("Emulation.setDeviceMetricsOverride",
    { width: W, height: full, deviceScaleFactor: 2, mobile: true });
  await sleep(900);
  const shot = await send("Page.captureScreenshot", { format: "png" });
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, Buffer.from(shot.data, "base64"));
  const { result: t } = await send("Runtime.evaluate",
    { expression: "document.body.innerText.length", returnByValue: true });
  console.log(`撮れた ${W}px 幅 / 高さ${full}px / 本文${t?.value}字 → ${OUT}`);
  ws.close();
} finally {
  try { chrome.kill("SIGKILL"); } catch { /* もう死んでいる */ }
}
