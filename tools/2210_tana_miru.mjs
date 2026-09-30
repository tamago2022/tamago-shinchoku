#!/usr/bin/env node
/**
 * 2210番【本番の棚を目で見る】headless Chrome（使い捨てプロファイル・使ったら殺す）で
 * 本番の棚ページを iPhone 幅で開き、画面に出ている文字を読んで、探す言葉があるか／無いかを返す。
 * たまごさんのブラウザには触らない（tools/_825_screenshot_375.mjs と同じ型）。
 *
 * 使い方: node tools/2210_tana_miru.mjs <URL> <PNG> "<出るべき言葉>" ["<出てはいけない言葉>" ...]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const [URL_ARG, PNG, MUST, ...MUSTNOT] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
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

const port = 9700 + Math.floor(Math.random() * 200);
const prof = mkdtempSync(resolve(tmpdir(), "2210-miru-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--mute-audio", "--autoplay-policy=user-gesture-required", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
const out = { url: URL_ARG, must: MUST, mustNot: MUSTNOT };
try {
  const t = await findPage(port);
  const { ready, send, close } = connect(t.webSocketDebuggerUrl);
  await ready;
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: true });
  await send("Page.navigate", { url: URL_ARG });
  let text = "";
  for (let i = 0; i < 40; i++) {           // 最大40秒、探す言葉が出るまで待つ（DBの棚は後から描かれる）
    await sleep(1000);
    try {
      // 棚は下へ送ると続きが描かれる（遅延描画）ので、毎秒いちばん下まで送ってから読む
      await send("Runtime.evaluate", { expression: "window.scrollTo(0, document.body ? document.body.scrollHeight : 0)" });
      const r = await send("Runtime.evaluate", { expression: "document.body ? document.body.innerText : ''", returnByValue: true });
      text = r.result?.value || "";
      if (MUST && text.includes(MUST)) break;
    } catch { /* 描画中 */ }
  }
  out.found = MUST ? text.includes(MUST) : null;
  out.foundNot = MUSTNOT.filter((w) => text.includes(w));
  out.textLen = text.length;
  const at = MUST ? text.indexOf(MUST) : -1;
  out.around = at >= 0 ? text.slice(Math.max(0, at - 80), at + 120) : text.slice(0, 300);
  if (PNG && out.found) {
    const r = await send("Runtime.evaluate", {
      expression: `(() => { const w = ${JSON.stringify(MUST)}; const it = [...document.querySelectorAll('body *')].find(e => e.children.length === 0 && (e.textContent||'').includes(w)); if (it) { it.scrollIntoView({block:'center'}); return true } return false })()`,
      returnByValue: true });
    out.scrolled = r.result?.value;
    await sleep(1500);
  }
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
process.exit(out.found ? 0 : 1);
