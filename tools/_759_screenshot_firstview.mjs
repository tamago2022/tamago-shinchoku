#!/usr/bin/env node
/**
 * 案件#759：完了条件④「1画面目を圧迫していない」の証拠。
 * 375px幅・開かずに（<details>を閉じたまま）最初のビューポート分だけを撮る。
 * 既存の tools/oni_kantoku_616_screenshot.mjs と同じ安全な headless Chrome 方式を流用。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const URL_ARG = process.argv[2];
const OUT_FILE = resolve(process.argv[3]);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch { /* 起動待ち */ }
    await sleep(250);
  }
  throw new Error("Chromeのデバッグ口が開きませんでした");
}
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { const cb = pending.get(msg.id); pending.delete(msg.id); cb(msg); }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) => new Promise((res2, rej2) => {
    const myId = ++id;
    pending.set(myId, (msg) => msg.error ? rej2(new Error(JSON.stringify(msg.error))) : res2(msg.result));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}
async function waitComplete(send) {
  const start = Date.now();
  while (Date.now() - start < 20000) {
    await sleep(400);
    try {
      const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (r.result?.value === "complete") return true;
    } catch { /* ナビゲーション中 */ }
  }
  return false;
}
async function main() {
  const outDir = dirname(OUT_FILE);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
  const port = 9800 + Math.floor(Math.random() * 90);
  const profile = mkdtempSync(resolve(tmpdir(), "759-fv-"));
  const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio", "--window-size=375,812",
    "--disable-features=Translate,MediaRouter", "about:blank",
  ], { stdio: "ignore" });
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 375, height: 812, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(1500);
    const info = await send("Runtime.evaluate", {
      expression: `(() => { const sec = document.getElementById('dekitaSec'); return JSON.stringify({ hasSec: !!sec, open: sec ? sec.open : null }); })()`,
      returnByValue: true,
    });
    console.log("実測(開閉状態):", info.result?.value);
    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 375, height: 812, scale: 1 } });
    writeFileSync(OUT_FILE, Buffer.from(shot.data, "base64"));
    console.log("保存:", OUT_FILE);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch { /* 無視 */ }
  }
}
main().catch((e) => { console.error("失敗:", e.message); process.exitCode = 1; });
