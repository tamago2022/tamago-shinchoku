#!/usr/bin/env node
/**
 * 769番：LINEスタンプ申請機（tools/line_stamp_pipeline.py）が生成した
 * 貼るだけシートの証拠スクショを撮る汎用版。742番の安全な方式
 * （headless Chromeを一時プロファイルで起動・CDPで操作・使い終わったら
 * 必ずSIGKILLでプロセスごと消す）をそのまま流用し、URL/出力先だけ引数化した。
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。
 *
 * 使い方: node tools/line_stamp_shot.mjs <URL> <出力ファイル絶対パス> [expectText]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, mkdirSync, existsSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname } from "node:path";
import { join } from "node:path";

const [, , URL, OUT_FILE, EXPECT_TEXT] = process.argv;
if (!URL || !OUT_FILE) {
  console.error("使い方: node tools/line_stamp_shot.mjs <URL> <出力ファイル絶対パス> [expectText]");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 2500;

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
  await sleep(250);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width, height, scale: 1 } });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function main() {
  const outDir = dirname(OUT_FILE);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "line-stamp-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=390,900",
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
    await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 900, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: target.id });

    await send("Page.navigate", { url: URL });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    const info = await evalJs(send, `(() => {
      const has = (t) => t ? document.body.innerText.includes(t) : true;
      return JSON.stringify({
        hasExpect: has(${JSON.stringify(EXPECT_TEXT || "")}),
        scrollHeight: document.body.scrollHeight,
      });
    })()`);
    console.log("ページ状態:", info);
    const j = JSON.parse(info);
    if (EXPECT_TEXT && !j.hasExpect) throw new Error("本文に期待する文字列が無い（描画失敗の疑い）: " + EXPECT_TEXT);

    // 1600px capだと①Display Information節だけで埋まり、②Sticker Images
    // （画像検品結果=検出枚数・規格OK枚数）以降が写らないことがある
    // （769番5回目でスクショが変化前後で完全一致するバグとして発覚）。
    // ②まで確実に含める高さへ引き上げる。
    await shoot(send, 390, Math.min(2800, j.scrollHeight), OUT_FILE);

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
