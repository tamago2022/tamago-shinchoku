#!/usr/bin/env node
/**
 * 案件#909：カードページ表示不具合3点の修理確認用スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_742_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 対象ページ：X投稿カード(xUrl)を含む /room/food/matcha-soft-cake
 *   （@sorealfoodsそのものはDB管理で直接特定できなかったため、同種のTweetCardを
 *   使う既存カードで代表確認する。TweetCard/FeedbackDoor/ナビはどのページでも共通部品）
 *
 * 使い方: node tools/q909_card_fix_screenshot.mjs
 * 出力: share/check/img/909-card-390.png / 909-card-1280.png
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, mkdirSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = process.argv[2] || "https://joy-relief-station.lovable.app/room/food/matcha-soft-cake?nc=" + Date.now();
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 3500;

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

async function waitComplete(send) {
  const start = Date.now();
  while (Date.now() - start < LOAD_TIMEOUT_MS) {
    await sleep(400);
    try {
      const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (r.result?.value === "complete") return true;
    } catch {
      /* ナビゲーション中 */
    }
  }
  return false;
}

async function evalJs(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result?.value;
}

async function shoot(send, width, height, outFile) {
  width = Math.round(width);
  height = Math.round(height);
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: width < 500 });
  await sleep(300);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width, height, scale: 1 } });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function runAt(port, width, height, outFile) {
  const profile = mkdtempSync(join(tmpdir(), "q909-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      `--window-size=${width},${height}`,
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
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: width < 500 });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    const info = await evalJs(send, `(() => {
      const has = (t) => document.body.innerText.includes(t);
      return JSON.stringify({
        hasGuideMisplaced: has('まだ手探りで始めたばかりです') && !!document.querySelector('main') && (() => {
          // 案内所ブロック(感想箱)がページ最上部（Breadcrumbs直下）に出ていないか、
          // それとも下部(FeedbackDoor本来の位置)にあるかをおおまかに判定
          const el = [...document.querySelectorAll('*')].find(e => e.textContent && e.textContent.includes('まだ手探りで始めたばかりです') && e.children.length === 0);
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          return { top: rect.top, docHeight: document.body.scrollHeight };
        })(),
        hasOldGuideLabel: has('案内所') ,
        hasNewLabel: has('ひとこと目安箱'),
        scrollHeight: document.body.scrollHeight,
      });
    })()`);
    console.log(`[${width}px] ページ状態:`, info);

    await shoot(send, width, Math.min(height, JSON.parse(info).scrollHeight || height), outFile);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* 無視 */
    }
  }
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
  const port1 = 31000 + Math.floor(Math.random() * 3000);
  await runAt(port1, 390, 1600, join(OUT_DIR, "909-card-390.png"));
  const port2 = 34000 + Math.floor(Math.random() * 3000);
  await runAt(port2, 1280, 1000, join(OUT_DIR, "909-card-1280.png"));
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
