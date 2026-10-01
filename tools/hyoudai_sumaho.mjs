#!/usr/bin/env node
/**
 * 2026-10-01 進捗表の題名（hyoudai）をスマホ幅 375×812 で確かめる。
 * 使い捨てプロファイルの headless Chrome で開き、走っているもの／次に発車の文字と
 * 画面写真を残す。たまごさんのブラウザには触らない。
 * 使い方: node tools/hyoudai_sumaho.mjs <URL> <PNG>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const [URL_IN, PNG] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const W = 375, H = 812;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find((t) => t.type === "page");
      if (p?.webSocketDebuggerUrl) return p;
    } catch { /* 起動待ち */ }
    await sleep(250);
  }
  throw new Error("デバッグ口が開かない");
}
function connect(u) {
  const ws = new WebSocket(u);
  let id = 0;
  const pend = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { const cb = pend.get(m.id); pend.delete(m.id); cb(m); }
  });
  const ready = new Promise((a, b) => { ws.addEventListener("open", a); ws.addEventListener("error", b); });
  const send = (method, params = {}) => new Promise((a, b) => {
    const i = ++id;
    pend.set(i, (m) => (m.error ? b(new Error(JSON.stringify(m.error))) : a(m.result)));
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}
const ev = async (send, expr) => (await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;

const port = 9700 + Math.floor(Math.random() * 200);
const prof = mkdtempSync(resolve(tmpdir(), "hyoudai-sumaho-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--mute-audio", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
const out = { url: URL_IN };
try {
  const t = await findPage(port);
  const { ready, send, close } = connect(t.webSocketDebuggerUrl);
  await ready;
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");
  await send("Network.setCacheDisabled", { cacheDisabled: true });
  await send("Network.setUserAgentOverride", { userAgent: UA });
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: true });
  await send("Page.navigate", { url: URL_IN + (URL_IN.includes("?") ? "&" : "?") + "t=" + Date.now() });
  for (let i = 0; i < 40; i++) { await sleep(500); if ((await ev(send, "document.readyState")) === "complete") break; }
  await sleep(6000);
  out.hasMidashi = await ev(send, "typeof midashi === 'function'");
  out.run = await ev(send, "[...document.querySelectorAll('#running .rt')].map(e => (e.querySelector('summary')||e).innerText)");
  out.runLines = await ev(send, "[...document.querySelectorAll('#running .rt')].map(e => Math.round((e.querySelector('summary')||e).getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight)))");
  out.next = await ev(send, "[...document.querySelectorAll('#next li')].map(e => (e.querySelector('summary')||e).innerText)");
  out.omosa = await ev(send, "(document.getElementById('omosa')||{}).innerText||''");
  out.stamp = await ev(send, "(document.getElementById('stamp')||{}).innerText||''");
  // 走っているものが画面に入る位置までスクロールして撮る
  await ev(send, "(document.getElementById('runHead')||document.body).scrollIntoView(), window.scrollBy(0,-20), true");
  await sleep(500);
  if (PNG) {
    const s = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(PNG, Buffer.from(s.data, "base64"));
    out.png = PNG;
  }
  close();
} catch (e) {
  out.error = String(e.message || e);
} finally {
  chrome.kill("SIGKILL");
  try { rmSync(prof, { recursive: true, force: true }); } catch { /* 無視 */ }
}
console.log(JSON.stringify(out, null, 1));
