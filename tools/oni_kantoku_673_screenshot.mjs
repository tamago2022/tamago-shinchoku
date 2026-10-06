#!/usr/bin/env node
/**
 * 案件#673：進捗表(index.html)「1 今すぐ」カードの1文字ずつ縦崩れ修正・トグル既定畳みの証拠スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_655_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 1枚目：スマホ幅375px、本番の「発車待ち」セクションを開いた状態（縦崩れが無いことの証拠）
 * 2枚目：横長デスクトップ幅1400px、同セクション（同上）
 * さらに、全<details>要素が初期状態でopen=falseであること（トグル既定畳み）をJS側で実測してログに出す。
 *
 * 使い方: node tools/oni_kantoku_673_screenshot.mjs
 * 出力: share/check/img/673-mobile-fixed.png, share/check/img/673-desktop-fixed.png
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");
const OUT_FILE_MOBILE = join(OUT_DIR, "673-mobile-fixed.png");
const OUT_FILE_DESKTOP = join(OUT_DIR, "673-desktop-fixed.png");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = "https://tamago2022.github.io/tamago-shinchoku/index.html";
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

async function measureAndOpenQueue(send) {
  // トグル既定畳みの実測：全<details>のopen状態を数える
  const toggleCheck = await send("Runtime.evaluate", {
    expression: `(() => {
      const all = Array.from(document.querySelectorAll('details'));
      const openCount = all.filter(d => d.open).length;
      return JSON.stringify({ total: all.length, openCount });
    })()`,
    returnByValue: true,
  });
  console.log("トグル初期状態:", toggleCheck.result?.value);

  // 「次に発車」セクションを開き、1文字縦崩れが起きていないか .qt要素の実測幅を取る
  const openAndMeasure = await send("Runtime.evaluate", {
    expression: `(() => {
      const sec = document.getElementById('queueSec');
      if (sec && !sec.open) sec.open = true;
      const rows = Array.from(document.querySelectorAll('.qrow'));
      const first = rows[0];
      if (!first) return JSON.stringify({ rowCount: rows.length });
      const qt = first.querySelector('.qt');
      const qbody = first.querySelector('.qbody');
      const rect = qt ? qt.getBoundingClientRect() : null;
      const bodyRect = qbody ? qbody.getBoundingClientRect() : null;
      const rowRect = first.getBoundingClientRect();
      return JSON.stringify({
        rowCount: rows.length,
        qtWidth: rect ? Math.round(rect.width) : null,
        qtHeight: rect ? Math.round(rect.height) : null,
        qbodyWidth: bodyRect ? Math.round(bodyRect.width) : null,
        rowHeight: Math.round(rowRect.height),
      });
    })()`,
    returnByValue: true,
  });
  console.log("1行目の実測:", openAndMeasure.result?.value);
  await sleep(400);
}

async function shoot(send, width, height, outFile) {
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 2, mobile: width < 500 });
  await sleep(300);
  // 「1 今すぐ」箱（queueSecの中の最初のqbox）の位置までスクロールしてから撮る
  const posInfo = await send("Runtime.evaluate", {
    expression: `(() => {
      const box = document.querySelector('.qbox');
      if (!box) return JSON.stringify({ found: false });
      const rect = box.getBoundingClientRect();
      return JSON.stringify({ found: true, top: rect.top + window.scrollY });
    })()`,
    returnByValue: true,
  });
  const pos = JSON.parse(posInfo.result?.value || "{}");
  const y = pos.found ? Math.max(0, Math.floor(pos.top) - 40) : 0;
  const clip = { x: 0, y, width, height, scale: 1 };
  const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile, "y=", y);
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-673-shot-"));
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

    await send("Page.navigate", { url: URL });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    await measureAndOpenQueue(send);
    await shoot(send, 375, 1400, OUT_FILE_MOBILE);

    await send("Emulation.setDeviceMetricsOverride", { width: 1400, height: 1400, deviceScaleFactor: 1, mobile: false });
    await sleep(500);
    await shoot(send, 1400, 1400, OUT_FILE_DESKTOP);

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
