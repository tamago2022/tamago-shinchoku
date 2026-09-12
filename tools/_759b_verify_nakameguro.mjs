#!/usr/bin/env node
/**
 * 案件#759・第2便：AI検品の再指摘（中目黒の実例が見つからない）への実測証拠。
 * 「できたもの」棚を開く→「昨日」で絞る→検索欄に「中目黒」と入れる→
 * 実際に#749の行が出てくることをDOMから確認し、スクショも撮る。
 * 既存の _759_screenshot.mjs と同じ安全なheadless Chrome方式（たまごさんの通常ブラウザ不使用）。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

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
async function evalJson(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
  return r.result?.value;
}
async function main() {
  const outDir = dirname(OUT_FILE);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });
  const port = 9700 + Math.floor(Math.random() * 90);
  const profile = mkdtempSync(resolve(tmpdir(), "759b-verify-"));
  const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio", "--window-size=430,1400",
    "--disable-features=Translate,MediaRouter", "about:blank",
  ], { stdio: "ignore" });
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 430, height: 1400, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(2000);

    // できたもの棚を開く
    await send("Runtime.evaluate", { expression: `(() => { document.getElementById('dekitaSec').open = true; })()` });
    await sleep(300);

    // dekimonoデータが読み込まれるまで待つ
    let loaded = false;
    for (let i = 0; i < 20; i++) {
      const v = await evalJson(send, `(window.__dekimono && window.__dekimono.items ? window.__dekimono.items.length : -1)`);
      if (v && v > 0) { loaded = true; break; }
      await sleep(500);
    }
    console.log("dekimono読み込み件数:", await evalJson(send, `(window.__dekimono ? window.__dekimono.items.length : -1)`));

    // 「昨日」で絞り込む
    await send("Runtime.evaluate", { expression: `(() => { document.querySelector('[data-dkdays="1"]').click(); })()` });
    await sleep(300);
    const yestCount = await evalJson(send, `document.querySelectorAll('#dekita .dkrow').length`);
    console.log("「昨日」だけで絞った件数:", yestCount);
    const yestHasNaka = await evalJson(send, `document.getElementById('dekita').innerText.includes('中目黒')`);
    console.log("「昨日」の中に中目黒が見えるか:", yestHasNaka);

    // 検索欄に「中目黒」と入れる（全部＋全期間に戻してから）
    await send("Runtime.evaluate", { expression: `(() => { document.querySelector('[data-dkdays="all"]').click(); })()` });
    await sleep(200);
    await send("Runtime.evaluate", {
      expression: `(() => { const inp = document.getElementById('dkq'); inp.value = '中目黒'; inp.dispatchEvent(new Event('input')); })()`,
    });
    await sleep(400);
    const searchInfo = await evalJson(send, `JSON.stringify({
      rows: document.querySelectorAll('#dekita .dkrow').length,
      text: document.getElementById('dekita').innerText.slice(0, 300)
    })`);
    console.log("検索「中目黒」の結果:", searchInfo);

    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: 430, height: 1400, scale: 1 } });
    writeFileSync(OUT_FILE, Buffer.from(shot.data, "base64"));
    console.log("保存:", OUT_FILE);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch { /* 無視 */ }
  }
}
main().catch((e) => { console.error("失敗:", e.message); process.exitCode = 1; });
