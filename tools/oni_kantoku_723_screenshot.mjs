#!/usr/bin/env node
/**
 * 723番：即読みPWA（share/sokuyomi/）の実機動作証拠スクショ。
 *
 * 背景：AI検品(Verifier)が「実機での音声再生・スクリーンショット：未確認」を理由に一度差し戻した。
 * Web Speech API（speechSynthesis）は音そのものを画像化できないため、
 * 「押した瞬間に発声処理が実際に動いた」ことを客観的に示す3点を記録する：
 *   1) 貼り付け前（初期状態）のスクショ
 *   2) ▶ボタンを実クリック（Input.dispatchMouseEvent＝本物のuser gestureとして扱われる）した直後、
 *      window.speechSynthesis.speaking が true になり、utterance の onstart イベントが発火したログ
 *   3) 再生中UI（1/3文・⏸一時停止・選ばれた声の名前）のスクショ
 *
 * 既存の安全な方式（tools/oni_kantoku_715_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作、使い終わったら必ずSIGKILLでプロセスごと消す
 *   - たまごさんの通常ブラウザ(Brave等)には一切触れない
 *
 * 使い方: node tools/oni_kantoku_723_screenshot.mjs
 * 出力: share/check/img/723-*.png, share/check/723_evidence.json
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = "https://tamago2022.github.io/tamago-shinchoku/share/sokuyomi/?nc=" + Date.now();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {
      /* 起動待ち */
    }
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
    if (msg.id && pending.has(msg.id)) {
      const cb = pending.get(msg.id);
      pending.delete(msg.id);
      cb(msg);
    }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const myId = ++id;
      pending.set(myId, (msg) => {
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      });
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}
async function evalJs(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result?.value;
}
async function click(send, selector) {
  const rect = await evalJs(
    send,
    `(()=>{const el=document.querySelector(${JSON.stringify(selector)}); const r=el.getBoundingClientRect(); return JSON.stringify({x:r.x+r.width/2,y:r.y+r.height/2});})()`,
  );
  const { x, y } = JSON.parse(rect);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
}
async function shootFull(send, outFile) {
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
  const evidence = { url: URL, at: new Date().toISOString(), steps: [] };

  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-723-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=390,1200",
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 1200, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });

    await send("Page.navigate", { url: URL });
    await sleep(3000);

    // 声の一覧（日本語だけ抜粋）
    const jaVoices = await evalJs(
      send,
      `JSON.stringify(window.speechSynthesis.getVoices().filter(v=>/^ja/i.test(v.lang)).map(v=>v.name))`,
    );
    evidence.japaneseVoices = JSON.parse(jaVoices);
    console.log("日本語音声:", jaVoices);

    // 1) 貼り付け前（初期状態）
    await shootFull(send, join(OUT_DIR, "723-before.png"));
    evidence.steps.push({ name: "before_screenshot", file: "723-before.png" });

    // 発声イベントを監視できるようフック
    await evalJs(
      send,
      `window.__events = [];
      const origSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
      window.speechSynthesis.speak = function(u) {
        u.addEventListener('start', ()=>window.__events.push('start@' + performance.now().toFixed(0)));
        u.addEventListener('end', ()=>window.__events.push('end@' + performance.now().toFixed(0)));
        u.addEventListener('error', (e)=>window.__events.push('error:' + e.error));
        window.__events.push('speak-called:' + u.text.slice(0,20));
        origSpeak(u);
      };`,
    );

    // 貼り付けを模擬（valueをセット + pasteイベント発火 → 自動再生される実装を検証）
    const testText = "これは即読みPWAの動作確認です。ボタンを押さなくても、貼り付けたらすぐ読み始めます。URLは https://example.com/dummy のように読み飛ばします。";
    await evalJs(
      send,
      `(()=>{ const ta=document.getElementById('ta'); ta.value=${JSON.stringify(testText)}; ta.dispatchEvent(new Event('paste')); return true; })()`,
    );
    await sleep(700);
    const afterPaste = await evalJs(
      send,
      `JSON.stringify({speaking: window.speechSynthesis.speaking, events: window.__events, status: document.getElementById('status').textContent, btnText: document.getElementById('playBtn').textContent})`,
    );
    evidence.pasteAutoStart = JSON.parse(afterPaste);
    console.log("貼り付け直後（自動再生されるか）:", afterPaste);

    await shootFull(send, join(OUT_DIR, "723-after-paste.png"));
    evidence.steps.push({ name: "after_paste_screenshot", file: "723-after-paste.png" });

    // いったん停止してから、▶ボタンの実クリックでも動くことを検証（貼り付け以外の経路）
    await click(send, "#stopBtn");
    await sleep(300);
    await evalJs(send, `window.__events = [];`);
    await click(send, "#playBtn");
    await sleep(1200);
    const afterClick = await evalJs(
      send,
      `JSON.stringify({speaking: window.speechSynthesis.speaking, pending: window.speechSynthesis.pending, events: window.__events, status: document.getElementById('status').textContent, btnText: document.getElementById('playBtn').textContent, btnClass: document.getElementById('playBtn').className, voice: document.getElementById('voiceSel').selectedOptions[0]?.textContent})`,
    );
    evidence.playButtonClick = JSON.parse(afterClick);
    console.log("▶ボタンクリック後:", afterClick);

    await shootFull(send, join(OUT_DIR, "723-playing.png"));
    evidence.steps.push({ name: "playing_screenshot", file: "723-playing.png" });

    // 15秒戻すボタンの動作確認
    await click(send, "#back15");
    await sleep(400);
    const afterBack = await evalJs(
      send,
      `JSON.stringify({status: document.getElementById('status').textContent, speaking: window.speechSynthesis.speaking})`,
    );
    evidence.back15 = JSON.parse(afterBack);
    console.log("15秒戻す後:", afterBack);

    await send("Runtime.evaluate", { expression: "window.speechSynthesis.cancel()" });
    close();

    writeFileSync(join(REPO_ROOT, "share/check/723_evidence.json"), JSON.stringify(evidence, null, 2));
    console.log("証跡ファイル保存:", "share/check/723_evidence.json");
  } finally {
    chrome.kill("SIGKILL");
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* 無視 */
    }
  }
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
