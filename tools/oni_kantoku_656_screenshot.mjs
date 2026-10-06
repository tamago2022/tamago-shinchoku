#!/usr/bin/env node
/**
 * 案件#656：カバー・パロディをハーフサイズで本人3曲の下へ＋Latelyコピー書き直し。
 * 本番の証拠スクショを2枚取得する。
 *
 * 既存の安全な方式（tools/oni_kantoku_655_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作、再生ボタンは押さない
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 1枚目：Stevie Wonder「Lately」本番ページ、「カバー・パロディ」見出し＋Jodeci/福原美穂
 * 2枚目：中島みゆき「糸」本番ページ、本編動画セクション（重複が無いことの証拠）
 *
 * 使い方: node tools/oni_kantoku_656_screenshot.mjs
 * 出力: share/check/img/656-lately-cover-parody.png, share/check/img/656-ito-no-dup.png
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");
const OUT_FILE_1 = join(OUT_DIR, "656-lately-cover-parody.png");
const OUT_FILE_2 = join(OUT_DIR, "656-ito-no-dup.png");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL_LATELY = "https://joy-relief-station.lovable.app/cover-guide?artist=stevie-wonder&song=lately";
const URL_ITO = "https://joy-relief-station.lovable.app/cover-guide?artist=nakajima&song=ito";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 2000;

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

async function shootLately(send) {
  await send("Page.navigate", { url: URL_LATELY });
  await waitComplete(send);
  await sleep(SETTLE_MS);

  const check = await send("Runtime.evaluate", {
    expression: `(() => {
      const all = Array.from(document.querySelectorAll('div, h2, h3'));
      const heading = all.find(el => el.textContent.trim() === 'カバー・パロディ');
      const rect = heading ? heading.getBoundingClientRect() : null;
      return JSON.stringify({ found: !!heading, rect });
    })()`,
    returnByValue: true,
  });
  const info = JSON.parse(check.result?.value || "{}");
  console.log("実測(Lately):", check.result?.value);
  if (!info.found) throw new Error("「カバー・パロディ」見出しが本番ページに見つからない");

  await send("Emulation.setDeviceMetricsOverride", { width: 375, height: 900, deviceScaleFactor: 2, mobile: true });
  await sleep(300);
  const check2 = await send("Runtime.evaluate", {
    expression: `(() => {
      const all = Array.from(document.querySelectorAll('div, h2, h3'));
      const heading = all.find(el => el.textContent.trim() === 'カバー・パロディ');
      const rect = heading ? heading.getBoundingClientRect() : null;
      return JSON.stringify({ rect });
    })()`,
    returnByValue: true,
  });
  const info2 = JSON.parse(check2.result?.value || "{}");
  const y = Math.max(0, Math.floor((info2.rect?.top || 0)) - 220);
  const clip = { x: 0, y, width: 375, height: 700, scale: 1 };
  const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
  writeFileSync(OUT_FILE_1, Buffer.from(shot.data, "base64"));
  console.log("保存:", OUT_FILE_1);
}

async function shootIto(send) {
  await send("Page.navigate", { url: URL_ITO });
  await waitComplete(send);
  await sleep(SETTLE_MS);

  const check = await send("Runtime.evaluate", {
    expression: `(() => {
      const iframes = document.querySelectorAll('iframe[src*="youtube"]');
      const imgs = document.querySelectorAll('img[src*="ytimg"], img[src*="youtube"]');
      return JSON.stringify({ iframeCount: iframes.length, imgCount: imgs.length });
    })()`,
    returnByValue: true,
  });
  console.log("実測(糸):", check.result?.value);

  await send("Emulation.setDeviceMetricsOverride", { width: 375, height: 900, deviceScaleFactor: 2, mobile: true });
  await sleep(300);
  const clip = { x: 0, y: 0, width: 375, height: 900, scale: 1 };
  const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
  writeFileSync(OUT_FILE_2, Buffer.from(shot.data, "base64"));
  console.log("保存:", OUT_FILE_2);
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  const port = 9900 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "oni-656-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=375,900",
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
    await send("Emulation.setDeviceMetricsOverride", { width: 375, height: 900, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });

    await shootLately(send);
    await shootIto(send);

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
