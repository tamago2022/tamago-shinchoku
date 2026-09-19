#!/usr/bin/env node
/**
 * 724番：「AIがオンラインを代替するほどリアル集合価値は高まるか」聞くページの実機動作証拠スクショ。
 *
 * 背景：前回はブラウザ内蔵speechSynthesisの合成音声を使ってAI検品にはねられた。
 * 今回は tools/dokudoku_worker.py（AivisSpeechで実音声ファイルを生成する既存の仕組み）で
 * 作った本物のm4aを <audio> タグで再生する方式に作り直した。725番の手法(headless Chrome+CDP実クリック)
 * を <audio> 要素向けに流用する。
 *
 * 確認する事実：
 *   1) 貼り付け前（初期状態）のスクショ
 *   2) ▶ボタンを実クリック（Input.dispatchMouseEvent＝本物のuser gesture）した直後、
 *      audio.paused が false になり、audio.currentTime が実際に進んでいること
 *   3) 再生中UI（時刻表示・⏸一時停止表示）のスクショ
 *   4) 15秒戻す／停止ボタンの動作確認
 *
 * 安全策：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作、使い終わったら必ずSIGKILLでプロセスごと消す
 *   - たまごさんの通常ブラウザ(Brave等)には一切触れない
 *
 * 使い方: node tools/oni_kantoku_724_screenshot.mjs
 * 出力: share/check/img/724-*.png, share/check/724_evidence.json
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
const URL = "https://tamago2022.github.io/tamago-shinchoku/share/sokuyomi/notes/724-ai-online-real-value.html?nc=" + Date.now();
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
  const profile = mkdtempSync(join(tmpdir(), "oni-724-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--autoplay-policy=no-user-gesture-required",
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

    // audio要素の初期状態（読み込めているか）
    const initial = await evalJs(
      send,
      `JSON.stringify({readyState: document.getElementById('player').readyState, duration: document.getElementById('player').duration, src: document.getElementById('player').currentSrc, error: document.getElementById('player').error && document.getElementById('player').error.message})`,
    );
    evidence.initialAudioState = JSON.parse(initial);
    console.log("初期audio状態:", initial);

    // 1) 初期状態
    await shootFull(send, join(OUT_DIR, "724-before.png"));
    evidence.steps.push({ name: "before_screenshot", file: "724-before.png" });

    // ▶ボタンの実クリック
    await click(send, "#playBtn");
    await sleep(2500);
    const afterClick = await evalJs(
      send,
      `JSON.stringify({paused: document.getElementById('player').paused, currentTime: document.getElementById('player').currentTime, duration: document.getElementById('player').duration, status: document.getElementById('status').textContent, btnText: document.getElementById('playBtn').textContent, btnClass: document.getElementById('playBtn').className})`,
    );
    evidence.playButtonClick = JSON.parse(afterClick);
    console.log("▶ボタンクリック後:", afterClick);

    await sleep(2000);
    const progressed = await evalJs(
      send,
      `JSON.stringify({currentTime: document.getElementById('player').currentTime, paused: document.getElementById('player').paused})`,
    );
    evidence.progressCheck = JSON.parse(progressed);
    console.log("2秒後の進み具合:", progressed);

    await shootFull(send, join(OUT_DIR, "724-playing.png"));
    evidence.steps.push({ name: "playing_screenshot", file: "724-playing.png" });

    // 15秒戻すボタンの動作確認（まず少し進めてから戻す）
    await click(send, "#back15");
    await sleep(400);
    const afterBack = await evalJs(
      send,
      `JSON.stringify({currentTime: document.getElementById('player').currentTime, status: document.getElementById('status').textContent})`,
    );
    evidence.back15 = JSON.parse(afterBack);
    console.log("15秒戻す後:", afterBack);

    // 停止ボタンの動作確認
    await click(send, "#stopBtn");
    await sleep(300);
    const afterStop = await evalJs(
      send,
      `JSON.stringify({paused: document.getElementById('player').paused, btnText: document.getElementById('playBtn').textContent})`,
    );
    evidence.stopButtonClick = JSON.parse(afterStop);
    console.log("停止ボタン後:", afterStop);

    close();

    writeFileSync(join(REPO_ROOT, "share/check/724_evidence.json"), JSON.stringify(evidence, null, 2));
    console.log("証跡ファイル保存:", "share/check/724_evidence.json");
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
