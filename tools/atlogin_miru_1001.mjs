#!/usr/bin/env node
/**
 * 2026-10-01 「@」ログイン確認（一回きり）。headless Chrome・使い捨てプロファイル・iPhone幅375×812。
 * 本番の編集画面を開き、合言葉欄に「@」だけを入れて送り、ログイン欄が消えて編集画面になったかを見る。
 * そのあと再読み込みして、聞かれずに入ったまま（端末に覚えられた）かも見る。
 * 使い方: node tools/atlogin_miru_1001.mjs <URL> <PNG前置き>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";

const [URL_ARG, PNG] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const W = 375, H = 812;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find((t) => t.type === "page");
      if (p?.webSocketDebuggerUrl) return p;
    } catch {}
    await sleep(250);
  }
  throw new Error("no debug port");
}
function connect(u) {
  const ws = new WebSocket(u); let id = 0; const pend = new Map();
  ws.addEventListener("message", (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { const cb = pend.get(m.id); pend.delete(m.id); cb(m); } });
  const ready = new Promise((a, b) => { ws.addEventListener("open", a); ws.addEventListener("error", b); });
  const send = (method, params = {}) => new Promise((a, b) => { const i = ++id; pend.set(i, (m) => (m.error ? b(new Error(JSON.stringify(m.error))) : a(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
  return { ready, send, close: () => ws.close() };
}
const port = 9500 + Math.floor(Math.random() * 150);
const prof = mkdtempSync(resolve(tmpdir(), "atlogin-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, "--no-first-run", "--mute-audio", `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
const out = { url: URL_ARG };
const STATE = `(() => { const pw = document.querySelector('input[type=password]'); const t = document.body ? document.body.innerText : ''; return { hasPwInput: !!pw, len: t.length, head: t.slice(0, 400) }; })()`;
try {
  const t = await findPage(port);
  const { ready, send, close } = connect(t.webSocketDebuggerUrl);
  await ready;
  await send("Page.enable"); await send("Runtime.enable"); await send("Network.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 2, mobile: true });
  await send("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1" });
  await send("Page.navigate", { url: URL_ARG });
  const ev = async (e) => (await send("Runtime.evaluate", { expression: e, returnByValue: true, awaitPromise: true })).result?.value;
  let st;
  for (let i = 0; i < 30; i++) { await sleep(1000); st = await ev(STATE).catch(() => null); if (st?.hasPwInput) break; }
  out.before = st;
  if (PNG) writeFileSync(PNG + "_1before.png", Buffer.from((await send("Page.captureScreenshot", { format: "png" })).data, "base64"));
  if (st?.hasPwInput) {
    await ev(`(() => { const pw = document.querySelector('input[type=password]'); pw.focus(); return true })()`);
    await send("Input.insertText", { text: "@" });
    await sleep(300);
    out.submitted = await ev(`(() => { const pw = document.querySelector('input[type=password]'); const f = pw.closest('form'); if (f) { f.requestSubmit ? f.requestSubmit() : f.submit(); return 'form' } const b = [...document.querySelectorAll('button')].find(b => /ログイン|入る|開く|OK|送/.test(b.textContent||'')); if (b) { b.click(); return 'button:' + b.textContent.trim() } return 'none' })()`);
    for (let i = 0; i < 20; i++) { await sleep(1000); st = await ev(STATE).catch(() => null); if (st && !st.hasPwInput) break; }
    out.after = st;
    if (PNG) writeFileSync(PNG + "_2after.png", Buffer.from((await send("Page.captureScreenshot", { format: "png" })).data, "base64"));
    const ck = await send("Network.getCookies", { urls: [URL_ARG] });
    out.cookies = (ck.cookies || []).map((c) => c.name).filter((n) => n.startsWith("gokigen"));
    await send("Page.reload", {});
    for (let i = 0; i < 20; i++) { await sleep(1000); st = await ev(STATE).catch(() => null); if (st && st.len > 50) { await sleep(3000); st = await ev(STATE).catch(() => st); break; } }
    out.afterReload = st;
    if (PNG) writeFileSync(PNG + "_3reload.png", Buffer.from((await send("Page.captureScreenshot", { format: "png" })).data, "base64"));
  }
  out.ok = !!(out.before?.hasPwInput && out.after && !out.after.hasPwInput);
  close();
} catch (e) { out.error = String(e.message || e); }
finally { chrome.kill("SIGKILL"); try { rmSync(prof, { recursive: true, force: true }); } catch {} }
console.log(JSON.stringify(out, null, 1));
process.exit(out.ok ? 0 : 1);
