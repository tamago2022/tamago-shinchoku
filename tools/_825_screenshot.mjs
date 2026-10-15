#!/usr/bin/env node
/**
 * 825番：「できたもの2」（日時＋カテゴリ＋1行＋ビフォーアフター＋URLだけ・詳細は畳む・検索）の証拠スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_740_screenshot.mjs 等）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作、使い終わったら必ずSIGKILLでプロセスごと消す
 *   - たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 使い方: node tools/_825_screenshot.mjs <before|after>
 * 出力: share/check/img/825-*.png
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
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 2500;
const PROD_URL = "https://tamago2022.github.io/tamago-shinchoku/index.html";
const WIDTH = 375;

const mode = process.argv[2] || "before";

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

async function shoot(send, width, height, outFile, top = 0) {
  width = Math.round(width);
  height = Math.round(height);
  await send("Emulation.setDeviceMetricsOverride", { width, height: height + top, deviceScaleFactor: 2, mobile: true });
  await sleep(250);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: top, width, height, scale: 1 } });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function withPage(fn) {
  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-825-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      `--window-size=${WIDTH},1400`,
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );
  try {
    const page = await findPage(port);
    const { ready, send, close } = connect(page.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", { width: WIDTH, height: 1400, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: page.id });
    await send("Page.navigate", { url: PROD_URL + "?nc=" + Date.now() });
    await waitComplete(send);
    await sleep(SETTLE_MS);
    await fn(send);
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

async function shootBefore() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
  await withPage(async (send) => {
    // できたもの棚を開く（旧UI：種類フィルタ動画/音/記事/ページ/資料/修正・新しく作った/直したタブ・日付タブ）
    const opened = await evalJs(
      send,
      `(() => {
        const el = document.getElementById("dekitaSec");
        if (!el) return "no-section";
        el.querySelector("summary").click();
        return "opened:" + el.open;
      })()`,
    );
    console.log("dekitaSec:", opened);
    await sleep(1800);
    const top = await evalJs(
      send,
      `(() => { const el = document.getElementById("dekitaSec"); el.scrollIntoView({behavior:"instant",block:"start"}); return window.scrollY; })()`,
    );
    await sleep(400);
    const scrollHeight = await evalJs(send, "document.body.scrollHeight");
    const remaining = Math.max(700, Math.min(1600, (scrollHeight || 900) - (top || 0)));
    await shoot(send, WIDTH, remaining, join(OUT_DIR, "825-before-old-ui.png"), top || 0);
  });
}

async function shootAfter() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
  // ①既定表示（日時＋カテゴリ＋1行＋ビフォーアフター＋URL・5件・くわしくは畳んだまま）
  await withPage(async (send) => {
    const opened = await evalJs(
      send,
      `(() => {
        const el = document.getElementById("dekitaSec");
        if (!el) return "no-section";
        el.querySelector("summary").click();
        return "opened:" + el.open;
      })()`,
    );
    console.log("dekitaSec:", opened);
    await sleep(2500); // before/after画像のfetchCheckPageBeforeAfterが走る時間を確保
    const top = await evalJs(
      send,
      `(() => { const el = document.getElementById("dekitaSec"); el.scrollIntoView({behavior:"instant",block:"start"}); return window.scrollY; })()`,
    );
    await sleep(600);
    const scrollHeight = await evalJs(send, "document.body.scrollHeight");
    const remaining = Math.max(900, Math.min(2000, (scrollHeight || 900) - (top || 0)));
    await shoot(send, WIDTH, remaining, join(OUT_DIR, "825-after-default5.png"), top || 0);
  });
  // ②検索「fal」で絞り込んだ状態
  await withPage(async (send) => {
    await evalJs(send, `document.getElementById("dekitaSec").querySelector("summary").click()`);
    await sleep(2000);
    const typed = await evalJs(
      send,
      `(() => {
        const inp = document.getElementById("dkq");
        if (!inp) return "no-input";
        inp.value = "fal";
        inp.dispatchEvent(new Event("input", {bubbles:true}));
        return "typed";
      })()`,
    );
    console.log("search:", typed);
    await sleep(1200);
    const top = await evalJs(
      send,
      `(() => { const el = document.getElementById("dekitaSec"); el.scrollIntoView({behavior:"instant",block:"start"}); return window.scrollY; })()`,
    );
    await sleep(400);
    const count = await evalJs(send, `document.querySelectorAll("#dekita .dkrow2").length`);
    console.log("fal件数(表示中):", count);
    const scrollHeight = await evalJs(send, "document.body.scrollHeight");
    const remaining = Math.max(700, Math.min(2000, (scrollHeight || 900) - (top || 0)));
    await shoot(send, WIDTH, remaining, join(OUT_DIR, "825-after-search-fal.png"), top || 0);
  });
  // ③カテゴリ「お金」で絞り込んだ状態
  await withPage(async (send) => {
    await evalJs(send, `document.getElementById("dekitaSec").querySelector("summary").click()`);
    await sleep(2000);
    const clicked = await evalJs(
      send,
      `(() => {
        const b = document.querySelector('#dkfilters [data-dkcat="お金"]');
        if (!b) return "no-button";
        b.click();
        return "clicked";
      })()`,
    );
    console.log("category-click:", clicked);
    await sleep(1500);
    const top = await evalJs(
      send,
      `(() => { const el = document.getElementById("dekitaSec"); el.scrollIntoView({behavior:"instant",block:"start"}); return window.scrollY; })()`,
    );
    await sleep(400);
    const scrollHeight = await evalJs(send, "document.body.scrollHeight");
    const remaining = Math.max(700, Math.min(2000, (scrollHeight || 900) - (top || 0)));
    await shoot(send, WIDTH, remaining, join(OUT_DIR, "825-after-category-okane.png"), top || 0);
  });
}

async function main() {
  if (mode === "before") await shootBefore();
  else await shootAfter();
  console.log("完了:", mode);
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
