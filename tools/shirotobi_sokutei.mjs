#!/usr/bin/env node
/**
 * 白飛び（ページ切り替えで画面が一瞬まっさらになる）を、スマホ相当でフレーム単位に測る。
 * 2026-10-17 たまごさん「白飛びがまだ目立つ。徹底的に快適に」。
 *
 * 方式：headless Chrome（一時プロファイル・使用後kill。たまごさんのChrome/Braveには触れない）。
 *   390x844・DPR3・タッチ・CPU 4倍遅く・回線「Slow 4G」相当（150ms / 1.6Mbps）。
 *   Page.startScreencast で描かれたフレームを全部 JPEG で保存し、時刻とイベント（どこを押したか）を記録。
 *   判定は tools/shirotobi_hantei.py（フレームの98%以上が1色＝まっさら、を数える）。
 *
 * 使い方: node tools/shirotobi_sokutei.mjs <出力フォルダ> [基点URL]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const OUT = process.argv[2];
const BASE = (process.argv[3] || "https://joy-relief-station.lovable.app").replace(/\/$/, "");
if (!OUT) { console.error("使い方: node tools/shirotobi_sokutei.mjs <出力フォルダ> [基点URL]"); process.exit(1); }
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 押す順番：トップ →（下タブ等のリンクで）案内所 → 曲ページ → 特集 → マガジン（別HTML）→ 戻る → 戻る
const STEPS = [
  { kind: "goto", url: BASE + "/" },
  { kind: "click", sel: 'a[href^="/cover-guide"]', label: "トップ→案内所" },
  { kind: "click", sel: 'a[href*="/cover-guide?artist="]', label: "案内所→曲ページ" },
  { kind: "click", sel: 'a[href^="/feature/"]', label: "→特集", fallbackUrl: "/feature/hikigatari" },
  { kind: "click", sel: 'a[href^="/magazine/"]', label: "→マガジン", fallbackUrl: "/magazine/kimi-wa-hoshi-katsu.html" },
  { kind: "back", label: "戻る1" },
  { kind: "back", label: "戻る2" },
  { kind: "click", sel: 'a[href="/"]', label: "→トップ" },
];

const port = 9100 + Math.floor(Math.random() * 400);
const prof = mkdtempSync(`${tmpdir()}/shiro-`);
const chrome = spawn(CHROME, [
  "--headless=new", "--mute-audio", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`,
  "--no-first-run", "--no-default-browser-check", "--hide-scrollbars", "--autoplay-policy=user-gesture-required",
  "about:blank",
], { stdio: "ignore" });

let ws, idn = 0;
const pend = new Map();
const frames = [];
const events = [];
const t0 = Date.now();
const now = () => Date.now() - t0;
function send(method, params = {}) {
  const id = ++idn;
  ws.send(JSON.stringify({ id, method, params }));
  return new Promise((res, rej) => { pend.set(id, { res, rej }); setTimeout(() => { if (pend.has(id)) { pend.delete(id); rej(new Error("timeout " + method)); } }, 30000); });
}
async function ev(expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r.result?.value;
}

try {
  let target;
  for (let i = 0; i < 300; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); target = l.find((x) => x.type === "page" && x.webSocketDebuggerUrl); if (target) break; } catch {}
    await sleep(300);
  }
  if (!target) throw new Error("Chromeのデバッグ口が開かない");
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => ws.addEventListener("open", r));
  ws.addEventListener("message", async (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pend.has(d.id)) { const p = pend.get(d.id); pend.delete(d.id); d.error ? p.rej(new Error(JSON.stringify(d.error))) : p.res(d.result); return; }
    if (d.method === "Page.screencastFrame") {
      const n = frames.length;
      const f = `f${String(n).padStart(5, "0")}.jpg`;
      writeFileSync(join(OUT, f), Buffer.from(d.params.data, "base64"));
      frames.push({ f, t: now(), url: null });
      ws.send(JSON.stringify({ id: ++idn, method: "Page.screencastFrameAck", params: { sessionId: d.params.sessionId } }));
    }
  });
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Network.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 3, mobile: true });
  await send("Emulation.setTouchEmulationEnabled", { enabled: true });
  await send("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1 shirotobi-sokutei" });
  await send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await send("Network.emulateNetworkConditions", { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 });
  await send("Page.startScreencast", { format: "jpeg", quality: 60, maxWidth: 390, maxHeight: 844, everyNthFrame: 1 });

  for (const s of STEPS) {
    const at = now();
    let done = "";
    if (s.kind === "goto") { await send("Page.navigate", { url: s.url }); done = s.url; }
    else if (s.kind === "back") { done = String(await ev("history.back(),location.href")); }
    else {
      const href = await ev(`(()=>{const a=[...document.querySelectorAll(${JSON.stringify(s.sel)})].find(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.height>0});if(!a)return null;a.scrollIntoView({block:"center"});const h=a.getAttribute("href");setTimeout(()=>a.click(),50);return h})()`);
      if (href) done = href;
      else if (s.fallbackUrl) { await ev(`(()=>{const a=document.createElement("a");a.href=${JSON.stringify(s.fallbackUrl)};document.body.appendChild(a);setTimeout(()=>a.click(),50);return 1})()`); done = s.fallbackUrl + "（リンクが無いので同じページ内からリンクを足して押した）"; }
    }
    events.push({ t: at, label: s.label || "開く", target: done });
    await sleep(s.kind === "goto" ? 12000 : 7000);
    const u = await ev("location.href").catch(() => "?");
    events[events.length - 1].landed = u;
  }
  await send("Page.stopScreencast");
  await sleep(500);
} catch (e) {
  events.push({ error: String(e) });
} finally {
  writeFileSync(join(OUT, "kiroku.json"), JSON.stringify({ base: BASE, frames, events }, null, 1));
  try { chrome.kill("SIGKILL"); } catch {}
  try { rmSync(prof, { recursive: true, force: true }); } catch {}
  console.log(JSON.stringify({ frames: frames.length, events }, null, 1));
}
