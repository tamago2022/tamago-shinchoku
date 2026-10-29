#!/usr/bin/env node
/**
 * 曲ページ・アーティストページを「本当の見え方」で撮る（2026-10-29 たまごさん「GitHub Pages の見本では実際の見え方が分からない。
 * 本番かプレビューを、スマホ幅とPC幅、ライトとダークで撮って見せて」）。
 * 方式は tools/_1371_screenshot.mjs と同じ（headless Chrome・一時プロフィール・使ったら SIGKILL と削除。
 * たまごさんの Brave・Chrome には触らない。許可ダイアログは出ない）。
 *
 * 使い方: node tools/kyoku_shot.mjs <URL> <出力PNG> [--w 390|1280] [--dark] [--max 14000]
 *   ページの下まで少しずつ下ろして、後から描かれる欄（関連・好きなら等）を出し切ってから全体を撮る。
 *   同じ名前の .txt に、見出しの並び（h2/h3と小見出し）を書き出す（目で見る前の下調べ用）。
 * 逆テスト: node tools/kyoku_shot.mjs --self-test
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
if (args[0] === "--self-test") {
  const ok = flag.length === 2 && typeof resolve("a.png") === "string";
  console.log(ok ? "SELF_TEST: PASS" : "SELF_TEST: FAIL");
  process.exit(ok ? 0 : 1);
}
const URL_ARG = args[0];
const OUT_FILE = args[1] ? resolve(args[1]) : "";
const WIDTH = Number(flag("--w", "390"));
const DARK = args.includes("--dark");
const MAXH = Number(flag("--max", "14000"));
if (!URL_ARG || !OUT_FILE) {
  console.error("使い方: node tools/kyoku_shot.mjs <URL> <出力PNG> [--w 390|1280] [--dark]");
  process.exit(1);
}
const MOBILE = WIDTH < 700;
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {}
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
  const ready = new Promise((res, rej) => { ws.addEventListener("open", res); ws.addEventListener("error", () => rej(new Error("CDP接続失敗"))); });
  const send = (method, params = {}) => new Promise((ok, ng) => {
    const myId = ++id;
    pending.set(myId, (m) => (m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result)));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}
const ev = async (send, expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.value;

async function main() {
  if (!existsSync(dirname(OUT_FILE))) mkdirSync(dirname(OUT_FILE), { recursive: true });
  const port = 9300 + Math.floor(Math.random() * 500);
  const profile = mkdtempSync(resolve(tmpdir(), "kyoku-shot-"));
  const H = MOBILE ? 844 : 900;
  const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--mute-audio", `--window-size=${WIDTH},${H}`, "--disable-features=Translate,MediaRouter", "about:blank"], { stdio: "ignore" });
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: H, deviceScaleFactor: MOBILE ? 2 : 1, mobile: MOBILE });
    if (MOBILE) await send("Emulation.setUserAgentOverride", { userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1" });
    await send("Page.addScriptToEvaluateOnNewDocument", { source: `try{localStorage.setItem('gokigen-theme','${DARK ? "dark" : "light"}')}catch(e){}` });
    await send("Page.navigate", { url: URL_ARG });
    for (let i = 0; i < 60; i++) { await sleep(500); if ((await ev(send, "document.readyState").catch(() => "")) === "complete") break; }
    await sleep(2500);
    // 下まで少しずつ下ろす（後から描く欄を出し切る）
    for (let i = 0; i < 40; i++) {
      const done = await ev(send, `(()=>{window.scrollBy(0, ${H * 0.8}); return (window.scrollY + innerHeight + 4) >= document.documentElement.scrollHeight;})()`);
      await sleep(450);
      if (done) { await sleep(1500); if (await ev(send, `(window.scrollY + innerHeight + 4) >= document.documentElement.scrollHeight`)) break; }
    }
    await ev(send, "window.scrollTo(0,0)");
    await sleep(1200);
    const outline = await ev(send, `(()=>{const o=[];document.querySelectorAll('h1,h2,h3,section > div:first-child, [data-related-reason]').forEach(e=>{const t=(e.innerText||'').trim().split('\\n')[0].slice(0,60);if(t)o.push(e.tagName+' '+t)});return JSON.stringify({dark:document.documentElement.classList.contains('dark'),h:document.documentElement.scrollHeight,o:o.slice(0,200)})})()`);
    const docH = Math.min(await ev(send, "document.documentElement.scrollHeight"), MAXH);
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: docH, deviceScaleFactor: MOBILE ? 2 : 1, mobile: MOBILE });
    await sleep(1500);
    const shot = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: 0, width: WIDTH, height: docH, scale: MOBILE ? 1 : 1 }, captureBeyondViewport: true });
    writeFileSync(OUT_FILE, Buffer.from(shot.data, "base64"));
    writeFileSync(OUT_FILE.replace(/\.png$/, ".txt"), outline || "");
    console.log("保存:", OUT_FILE, docH);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  }
}
main().catch((e) => { console.error("失敗:", e.message); process.exitCode = 1; });
