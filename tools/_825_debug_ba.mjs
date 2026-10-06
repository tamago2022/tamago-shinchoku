#!/usr/bin/env node
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const URL_ARG = process.argv[2];
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {}
    await sleep(250);
  }
  throw new Error("no debug port");
}
function connect(wsUrl) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) { const cb = pending.get(msg.id); pending.delete(msg.id); cb(msg); }
  });
  const ready = new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", (e) => rej(e)); });
  const send = (method, params = {}) => new Promise((res2, rej) => {
    const myId = ++id;
    pending.set(myId, (msg) => { if (msg.error) rej(new Error(JSON.stringify(msg.error))); else res2(msg.result); });
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}
async function waitComplete(send) {
  const start = Date.now();
  while (Date.now() - start < 20000) {
    await sleep(400);
    try { const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true }); if (r.result?.value === "complete") return; } catch {}
  }
}
async function main() {
  const port = 9900 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(resolve(tmpdir(), "825-dbg-"));
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--mute-audio", "--window-size=375,1400", "about:blank"], { stdio: "ignore" });
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable"); await send("Runtime.enable");
    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(1500);
    await send("Runtime.evaluate", { expression: `document.getElementById('dekitaSec').open = true` });
    await sleep(500);
    const r1 = await send("Runtime.evaluate", {
      expression: `fetchCheckPageBeforeAfter('${new URL("share/check/daily-ingest.html", URL_ARG).href}').then(x=>JSON.stringify(x))`,
      awaitPromise: true, returnByValue: true,
    });
    console.log("daily-ingest ba:", r1.result?.value);
    await sleep(1500);
    const r2 = await send("Runtime.evaluate", {
      expression: `JSON.stringify(Object.keys(window.__baCache).length) `, returnByValue: true,
    });
    console.log("cache keys:", r2.result?.value);
    const r3 = await send("Runtime.evaluate", {
      expression: `document.querySelectorAll('.dkbaimg img').length`, returnByValue: true,
    });
    console.log("img elements:", r3.result?.value);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  }
}
main().catch(e => { console.error(e); process.exit(1); });
