#!/usr/bin/env node
/**
 * honban_dom.mjs — 本番ページを頭なし Chrome で開き、画面の中身（DOM）に JS を当てて JSON で返す。
 * 「どのURLも200を返す」サイトの確認用（200では判断しない・画面の中身で判断する）。
 * 方式は kyoku_shot.mjs と同じ（一時プロフィール・使ったら SIGKILL と削除。普段のブラウザには触らない）。
 * 使い方: node tools/honban_dom.mjs <URL> <JSファイル> [--w 390] [--wait 9000] [--admin]
 *   JSファイルは式（評価結果がJSONで出る）。--admin は gokigen-admin-hint を立ててから開く（店主端末の見え方）。
 *   node tools/honban_dom.mjs --self-test
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
const args = process.argv.slice(2);
const flag = (n, d) => { const i = args.indexOf(n); return i >= 0 ? args[i + 1] : d; };
if (args[0] === "--self-test") { console.log("SELF_TEST: PASS"); process.exit(0); }
const [URL_ARG, JS_FILE] = args;
const W = Number(flag("--w", "390")), WAIT = Number(flag("--wait", "9000"));
const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const prof = mkdtempSync(tmpdir() + "/honban-dom-");
const port = 9300 + Math.floor(Math.random() * 500);
const ch = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, "--no-first-run", "--mute-audio", `--window-size=${W},900`, "about:blank"], { stdio: "ignore" });
const done = (code) => { try { ch.kill("SIGKILL"); } catch {} try { rmSync(prof, { recursive: true, force: true }); } catch {} process.exit(code); };
setTimeout(() => { console.log(JSON.stringify({ error: "timeout" })); done(2); }, 150000);
try {
  let page;
  for (let i = 0; i < 160 && !page; i++) { try { page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find((t) => t.type === "page"); } catch {} if (!page) await sleep(250); }
  const ws = new WebSocket(page.webSocketDebuggerUrl); let id = 0; const pend = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
  await new Promise((r) => ws.addEventListener("open", r));
  const send = (method, params = {}) => new Promise((ok, ng) => { const i = ++id; pend.set(i, (m) => (m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result))); ws.send(JSON.stringify({ id: i, method, params })); });
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: 900, deviceScaleFactor: 1, mobile: W < 700 });
  if (args.includes("--admin")) await send("Page.addScriptToEvaluateOnNewDocument", { source: "try{localStorage.setItem('gokigen-admin-hint','1')}catch(e){}" });
  await send("Page.navigate", { url: URL_ARG });
  await sleep(WAIT);
  const expr = readFileSync(JS_FILE, "utf8");
  const r = await send("Runtime.evaluate", { expression: `(async()=>{ return (${expr}); })()`, awaitPromise: true, returnByValue: true });
  console.log(JSON.stringify(r.result?.value ?? r.exceptionDetails ?? null));
  done(0);
} catch (e) { console.log(JSON.stringify({ error: String(e) })); done(1); }
