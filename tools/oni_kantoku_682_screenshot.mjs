#!/usr/bin/env node
/**
 * 682番：優先度A〜E＋F・一括仕分け・ポップオーバー修正の証拠スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_676_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 撮る4枚：
 *   1) 発車待ち全体（凡例・A〜F箱ラベル）
 *   2) 「⋯順番」ポップオーバーを開いた状態（同時に1つだけ・閉じるボタン修正の証拠）
 *   3) チェックボックスを2件選んで一括仕分けバーが出た状態
 *   4) 「2番目へ」ボタンが見える行
 *
 * 使い方: node tools/oni_kantoku_682_screenshot.mjs
 * 出力: share/check/img/682-*.png
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
  const profile = mkdtempSync(join(tmpdir(), "oni-682-shot-"));
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

    // 発車待ちセクションを開く
    await evalJs(send, `(() => { const sec = document.getElementById('queueSec'); if (sec) sec.open = true; return true; })()`);
    await sleep(600);

    // 1) 全体像（凡例＋箱ラベルA〜F）
    const secTop = await evalJs(send, `document.getElementById('queueSec').getBoundingClientRect().top + window.scrollY`);
    await shoot(send, 390, 900, secTop, join(OUT_DIR, "682-queue-overview.png"));

    // 2) 「⋯順番」ポップオーバーを1つ開く
    const moreInfo = await evalJs(send, `(() => {
      const btn = document.querySelector('.qmore');
      if (!btn) return JSON.stringify({found:false});
      btn.click();
      const menu = document.getElementById('qJumpMenu');
      const openCount = document.querySelectorAll('.qjump-menu.open').length;
      const rect = btn.getBoundingClientRect();
      return JSON.stringify({found:true, openCount, top: rect.top + window.scrollY, displayStyle: menu ? menu.style.display : null});
    })()`);
    console.log("ポップオーバー:", moreInfo);
    await sleep(400);
    const moreTop = JSON.parse(moreInfo).top || secTop;
    await shoot(send, 390, 420, moreTop, join(OUT_DIR, "682-jumpmenu-open.png"));

    // 外側クリックで閉じることを検証してからチェックボックス操作へ
    const closedInfo = await evalJs(send, `(() => {
      document.getElementById('qJumpBackdrop')?.click();
      const openCount = document.querySelectorAll('.qjump-menu.open').length;
      const menu = document.getElementById('qJumpMenu');
      return JSON.stringify({openCount, displayStyle: menu ? menu.style.display : null});
    })()`);
    console.log("外側クリックで閉じた結果:", closedInfo);

    // 3) チェックボックスを2件選んで一括仕分けバーを出す
    const selInfo = await evalJs(send, `(() => {
      const boxes = Array.from(document.querySelectorAll('.qsel')).slice(0, 2);
      boxes.forEach(b => { b.checked = true; b.dispatchEvent(new Event('change', {bubbles:true})); });
      const bar = document.querySelector('.qbulkbar');
      const rect = bar ? bar.getBoundingClientRect() : null;
      return JSON.stringify({count: boxes.length, barFound: !!bar, top: rect ? rect.top + window.scrollY : null});
    })()`);
    console.log("一括選択:", selInfo);
    await sleep(400);
    const sel = JSON.parse(selInfo);
    await shoot(send, 390, 500, sel.top || secTop, join(OUT_DIR, "682-bulk-select.png"));

    // 選択を解除（本番のqueue.jsonへは何も送っていない選択状態だけの見た目なので、そのまま消して終わる）
    await evalJs(send, `(() => { document.querySelector('[data-bulkclear]')?.click(); return true; })()`);

    // 4) 「2番目へ」ボタンが見える行
    const secondInfo = await evalJs(send, `(() => {
      const btn = document.querySelector('.qsecond');
      if (!btn) return JSON.stringify({found:false});
      const row = btn.closest('.qrow');
      const rect = row.getBoundingClientRect();
      return JSON.stringify({found:true, top: rect.top + window.scrollY});
    })()`);
    console.log("2番目へボタン:", secondInfo);
    const second = JSON.parse(secondInfo);
    if (second.found) {
      await shoot(send, 390, 320, second.top, join(OUT_DIR, "682-second-button.png"));
    }

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
