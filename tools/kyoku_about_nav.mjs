#!/usr/bin/env node
/**
 * 曲ページから「〇〇 — Room」を押してアーティストページへ移ったとき、紹介文（メモ）が消えていないかを確かめる
 * （2026-10-29 たまごさん「曲ページからTLCのアーティストページへ行くと、アーティスト紹介が消えている」）。
 * 直接開いた時と、画面の中で移った時の両方で「メモ」欄の文字数を数えて並べる。
 * 方式は tools/kyoku_shot.mjs と同じ（headless Chrome・一時プロフィール・使ったら消す）。
 * 使い方: node tools/kyoku_about_nav.mjs <base> <artistId> <songId> [<artistId> <songId> ...]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
const [base, ...pairs] = process.argv.slice(2);
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json(); const p = l.find((t) => t.type === "page"); if (p?.webSocketDebuggerUrl) return p; } catch {}
    await sleep(250);
  }
  throw new Error("no devtools");
}
function connect(u) {
  const ws = new WebSocket(u); let id = 0; const pend = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
  const ready = new Promise((r) => ws.addEventListener("open", r));
  const send = (method, params = {}) => new Promise((ok, ng) => { const i = ++id; pend.set(i, (m) => (m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
  return { ready, send, close: () => ws.close() };
}
const ev = async (send, expression) => (await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true })).result?.value;
const MEMO = `(()=>{const s=[...document.querySelectorAll('details summary')].find(x=>x.textContent.trim()==='メモ'||x.textContent.trim()==='Notes');return s? s.parentElement.innerText.length : 0})()`;
const port = 9800 + Math.floor(Math.random() * 150);
const profile = mkdtempSync(resolve(tmpdir(), "kyoku-nav-"));
const chrome = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, "--no-first-run", "--mute-audio", "--window-size=390,844", "about:blank"], { stdio: "ignore" });
try {
  const t = await findPage(port); const { ready, send, close } = connect(t.webSocketDebuggerUrl); await ready;
  await send("Page.enable"); await send("Runtime.enable");
  for (let i = 0; i < pairs.length; i += 2) {
    const a = pairs[i], s = pairs[i + 1];
    await send("Page.navigate", { url: `${base}/cover-guide?artist=${a}` }); await sleep(7000);
    const direct = await ev(send, MEMO);
    await send("Page.navigate", { url: `${base}/cover-guide?artist=${a}&song=${s}` }); await sleep(9000);
    await ev(send, `(()=>{const b=[...document.querySelectorAll('button')].find(x=>/— Room$/.test(x.textContent.trim()));b&&b.click();return !!b})()`);
    await sleep(8000);
    const url = await ev(send, "location.href");
    const nav = await ev(send, MEMO);
    console.log(JSON.stringify({ artist: a, song: s, direct, afterNav: nav, url }));
  }
  close();
} finally { chrome.kill("SIGKILL"); try { rmSync(profile, { recursive: true, force: true }); } catch {} }
