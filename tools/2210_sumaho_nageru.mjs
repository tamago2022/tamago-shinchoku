#!/usr/bin/env node
/**
 * 2210番【スマホで1件投げて、何秒で「済」になるか測る】
 * iPhone Safari と同じ幅・UA の headless Chrome（使い捨てプロファイル・使ったら殺す）で
 * 本物の箱（https）を ?kakunin=1 で開き、URLを貼って棚を選び［投げる］を押す。
 * 画面に「入りました → ◯◯の棚を開く」が出るまでの秒数と、そのリンク先を返す。
 * たまごさんのブラウザには触らない。
 *
 * 使い方: node tools/2210_sumaho_nageru.mjs <箱URL> <投げるURL> <棚id> <棚名> <world> <PNG>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const [BOX, URL_IN, SID, STITLE, WORLD, PNG] = process.argv.slice(2);
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

const port = 9500 + Math.floor(Math.random() * 200);
const prof = mkdtempSync(resolve(tmpdir(), "2210-nageru-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--mute-audio", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
const out = { box: BOX, url: URL_IN, shelf: STITLE };
try {
  const t = await findPage(port);
  const { ready, send, close } = connect(t.webSocketDebuggerUrl);
  await ready;
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");
  await send("Network.setUserAgentOverride", { userAgent: UA });
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: true });
  await send("Page.navigate", { url: BOX + (BOX.includes("?") ? "&" : "?") + "kakunin=1&t=" + Date.now() });
  for (let i = 0; i < 40; i++) { await sleep(500); if ((await ev(send, "document.readyState")) === "complete") break; }
  out.hakoNew = await ev(send, "document.documentElement.outerHTML.includes('kakunin=1')");
  // 貼る＋棚を選ぶ（人が［貼る］と棚ボタンを押したのと同じ中身を入れる）
  await ev(send, `(() => { document.getElementById('u').value = ${JSON.stringify(URL_IN)};
     SHELVES.push({id:${JSON.stringify(SID)}, title:${JSON.stringify(STITLE)}, world:${JSON.stringify(WORLD)}}); drawChips(); return true })()`);
  const t0 = Date.now();
  await ev(send, "document.getElementById('send').click(), true");
  let msg = "";
  for (let i = 0; i < 120; i++) {
    await sleep(250);
    msg = (await ev(send, "document.getElementById('msg').innerText")) || "";
    if (/入りました|入りませんでした|届きませんでした/.test(msg)) break;
  }
  out.seconds = Math.round((Date.now() - t0) / 100) / 10;
  out.msg = msg;
  out.link = await ev(send, "(document.querySelector('#msg a')||{}).href || ''");
  out.sumi = /入りました/.test(msg);
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
process.exit(out.sumi ? 0 : 1);
