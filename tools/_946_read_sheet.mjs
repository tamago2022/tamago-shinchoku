#!/usr/bin/env node
/** 【946番】見本帳の実測表を、実際にブラウザで描いてから文字で読み出す（目視でなく数字で確かめるため）。
 *  使い方: node tools/_946_read_sheet.mjs <URL> [幅]
 */
import { spawn } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const URL_ARG = process.argv[2];
const WIDTH = Number(process.argv[3] || 1440);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
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
  throw new Error("Chromeのデバッグ口が開きませんでした");
}
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0; const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { const cb = pending.get(m.id); pending.delete(m.id); cb(m); }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(String(e?.message ?? e))));
  });
  const send = (method, params = {}) => new Promise((ok, ng) => {
    const myId = ++id;
    pending.set(myId, (m) => (m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result)));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}

const port = 9300 + Math.floor(Math.random() * 200);
const profile = mkdtempSync(resolve(tmpdir(), "946-sheet-"));
const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--mute-audio", `--window-size=${WIDTH},1400`, "about:blank",
], { stdio: "ignore" });
try {
  const t = await findPage(port);
  const { ready, send, close } = connect(t.webSocketDebuggerUrl);
  await ready;
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: 1400, deviceScaleFactor: 1, mobile: WIDTH < 768 });
  await send("Page.navigate", { url: URL_ARG });
  for (let i = 0; i < 60; i++) {
    await sleep(500);
    const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
    if (r.result?.value === "complete") break;
  }
  await sleep(2500);
  const r = await send("Runtime.evaluate", {
    expression: `(document.getElementById('ink946out')||document.body).innerText`,
    returnByValue: true,
  });
  console.log(`\n### 見本帳の実測表（幅 ${WIDTH}px で描いて読み出した）`);
  console.log(r.result?.value || "(空)");
  close();
} catch (e) {
  console.log("NG: " + e.message);
} finally {
  try { chrome.kill("SIGKILL"); } catch { /* 既に死んでいる */ }
}
