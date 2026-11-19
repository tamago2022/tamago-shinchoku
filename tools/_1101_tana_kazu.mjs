#!/usr/bin/env node
/**
 * 1101番【棚の並び・実測】たまごさんのiPhoneのSafariと同じ条件で /world/music を開き、
 * 「背表紙で探す」の一覧から〈見出し／棚の名前／枚数〉をそのまま読み取る。
 *
 * ・tools/sumaho_gate.mjs と同じ安全側（headless Chrome・使い捨てプロファイル・必ず殺す）。
 * ・たまごさんの普段のブラウザには一切触らない。タブを1枚も増やさない。
 *
 * 使い方: node tools/_1101_tana_kazu.mjs <URL> <出力JSON> [PNG]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const URL_ = process.argv[2] || "https://joy-relief-station.lovable.app/world/music";
const OUT = resolve(process.argv[3] || "/tmp/tana_kazu.json");
const PNG = process.argv[4] ? resolve(process.argv[4]) : null;

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
  + "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1";
const W = 375, H = 812;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 160; i++) {
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
  const send = (method, params = {}) => new Promise((res, rej) => {
    const myId = ++id;
    pending.set(myId, (m) => (m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result)));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}

async function evalIn(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  return r?.result?.value;
}

const SCRAPE = `(function(){
  var sec = null;
  var ps = Array.from(document.querySelectorAll("p"));
  var head = ps.find(function(p){ return /棚は\\s*\\d+\\s*本/.test(p.textContent||""); });
  if (head) sec = head.closest("section");
  if (!sec) return JSON.stringify({ found:false, text:(document.body.innerText||"").slice(0,400) });
  var blocks = [];
  Array.from(sec.children).forEach(function(div){
    var h = div.querySelector && div.querySelector("h3");
    if (!h) return;
    var items = Array.from(div.querySelectorAll("a")).map(function(a){
      var sp = a.querySelectorAll("span");
      return { title: (sp[0]||{}).textContent || "", kazu: (sp[1]||{}).textContent || "" };
    });
    blocks.push({ midashi: h.textContent.trim(), items: items });
  });
  return JSON.stringify({ found:true, ichigyo: head.textContent.trim(), blocks: blocks });
})()`;

async function main() {
  const res = { at: new Date().toISOString(), url: URL_, ua: "iPhone Safari 17.5", size: W + "x" + H };
  const port = 9600 + Math.floor(Math.random() * 300);
  const profile = mkdtempSync(resolve(tmpdir(), "tana-kazu-"));
  const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio", `--window-size=${W},${H}`,
    "--disable-features=Translate,MediaRouter", "about:blank",
  ], { stdio: "ignore" });

  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable"); await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 3, mobile: true });
    await send("Emulation.setUserAgentOverride", { userAgent: UA, platform: "iPhone" });
    await send("Emulation.setTouchEmulationEnabled", { enabled: true, maxTouchPoints: 5 });

    const u = URL_ + (URL_.includes("?") ? "&" : "?") + "t=" + Date.now();
    await send("Page.navigate", { url: u });
    for (let i = 0; i < 80 && (await evalIn(send, "document.readyState")) !== "complete"; i++) await sleep(300);
    // DBの棚が届くまで待つ（棚の本数が2回続けて同じになったら落ち着いたとみなす）
    let prev = -1, same = 0;
    for (let i = 0; i < 40; i++) {
      await sleep(1000);
      const n = await evalIn(send, `(function(){var m=(document.body.innerText||"").match(/棚は\\s*(\\d+)\\s*本/);return m?+m[1]:-1})()`);
      if (n > 0 && n === prev) { same++; if (same >= 3) break; } else same = 0;
      prev = n;
    }
    res.honsuu = prev;
    const raw = await evalIn(send, SCRAPE);
    res.gamen = JSON.parse(raw || "{}");
    res.deploymentId = await evalIn(send, `(function(){return (window.performance.getEntriesByType("navigation")[0]||{}).name||""})()`);

    if (PNG) {
      mkdirSync(dirname(PNG), { recursive: true });
      const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true });
      writeFileSync(PNG, Buffer.from(shot.data, "base64"));
      res.png = PNG;
    }
    close();
  } catch (e) {
    res.error = String(e && e.message ? e.message : e);
  } finally {
    try { chrome.kill("SIGKILL"); } catch {}
  }
  if (!existsSync(dirname(OUT))) mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(res, null, 1));
  console.log(JSON.stringify(res, null, 1));
}
main();
