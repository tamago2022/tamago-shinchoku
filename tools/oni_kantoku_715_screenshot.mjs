#!/usr/bin/env node
/**
 * 715番：憲法遵守点検（kenpouSec）の証拠スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_682_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 撮る2枚：
 *   1) 赤バナー（🔴憲法違反）が出ている状態
 *   2) 「🏛️ 憲法遵守点検」の開いた中身（9項目のカード、赤/緑が分かる）
 *
 * 使い方: node tools/oni_kantoku_715_screenshot.mjs
 * 出力: share/check/img/715-*.png
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
const URL = "https://tamago2022.github.io/tamago-shinchoku/index.html?nc=" + Date.now();
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 3000;

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

async function shoot(send, width, height, y, outFile) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: width < 500 });
  await sleep(250);
  const clip = { x: 0, y: Math.max(0, y - 20), width, height, scale: 1 };
  const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile, "y=", clip.y);
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-715-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=390,1600",
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
    await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 1600, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });

    await send("Page.navigate", { url: URL });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    // 1) 赤バナー（見えているか。無ければbanner高さ0として上部だけ撮る）
    const bannerInfo = await evalJs(send, `(() => {
      const el = document.getElementById('kenpouAlert');
      if (!el) return JSON.stringify({found:false});
      const rect = el.getBoundingClientRect();
      const visible = rect.height > 0 && getComputedStyle(el).display !== 'none';
      return JSON.stringify({found:true, visible, top: rect.top + window.scrollY, height: rect.height, text: el.textContent});
    })()`);
    console.log("赤バナー:", bannerInfo);
    const banner = JSON.parse(bannerInfo);
    if (banner.found) {
      await shoot(send, 390, 260, Math.max(0, banner.top - 60), join(OUT_DIR, "715-alert-banner.png"));
    }

    // 2) 憲法遵守点検セクションを開いて中身を撮る
    await evalJs(send, `(() => { const sec = document.getElementById('kenpouSec'); if (sec) sec.open = true; return true; })()`);
    await sleep(600);
    const secInfo = await evalJs(send, `(() => {
      const sec = document.getElementById('kenpouSec');
      const box = document.getElementById('kenpouBox');
      const rect = sec.getBoundingClientRect();
      const cardCount = box ? box.querySelectorAll('.c').length : 0;
      const redCount = box ? box.querySelectorAll('.c.red').length : 0;
      return JSON.stringify({top: rect.top + window.scrollY, height: rect.height, cardCount, redCount});
    })()`);
    console.log("憲法点検セクション:", secInfo);
    const sec = JSON.parse(secInfo);
    await shoot(send, 390, Math.min(1600, Math.max(400, sec.height + 60)), sec.top, join(OUT_DIR, "715-kenpou-section.png"));

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

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
