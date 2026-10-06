#!/usr/bin/env node
/**
 * 734番：写真（静止画）2件を棚に入れる実験の証拠スクショ。
 *
 * 既存の安全な方式（tools/oni_kantoku_742_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 使い方: node tools/oni_kantoku_734_screenshot.mjs
 * 出力: share/check/img/734-*.png （4枚）
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
const SETTLE_MS = 3000;

const TARGETS = [
  {
    url: "https://joy-relief-station.lovable.app/world/food#shelf-photo-test-room",
    out: "734-4-world-food-shelves.png",
    width: 390,
    label: "食べ物ワールド棚表示（横並び/cards表示・新設2棚を含む）",
    scrollToId: "shelf-photo-test-room",
  },
  {
    url: "https://joy-relief-station.lovable.app/world/food#shelf-omiyage",
    out: "734-5-world-food-shelves-omiyage.png",
    width: 390,
    label: "食べ物ワールド棚表示（お土産棚）",
    scrollToId: "shelf-omiyage",
  },
];

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
  await send("Emulation.setDeviceMetricsOverride", { width, height: height + top, deviceScaleFactor: 2, mobile: width < 500 });
  await sleep(250);
  const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: top, width, height, scale: 1 } });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function shootOne(target) {
  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-734-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      `--window-size=${target.width},1400`,
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
    await send("Emulation.setDeviceMetricsOverride", { width: target.width, height: 1400, deviceScaleFactor: 2, mobile: true });
    await send("Target.activateTarget", { targetId: page.id });

    await send("Page.navigate", { url: target.url + (target.url.includes("?") ? "&" : "?") + "nc=" + Date.now() });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    let top = 0;
    if (target.scrollToId) {
      // ハッシュ自動スクロールが効かない場合に備え、対象要素を直接中央〜上寄せへ持っていく。
      const found = await evalJs(
        send,
        `(() => {
          const el = document.getElementById(${JSON.stringify(target.scrollToId)});
          if (!el) return JSON.stringify({ found: false });
          el.scrollIntoView({ behavior: "instant", block: "start" });
          return JSON.stringify({ found: true });
        })()`,
      );
      console.log(`[${target.out}] scrollToId=${target.scrollToId} ->`, found);
      await sleep(1200);
      top = await evalJs(send, "window.scrollY");
    }

    const scrollHeight = await evalJs(send, "document.body.scrollHeight");
    console.log(`[${target.out}] scrollHeight=${scrollHeight} top=${top}`);

    const remaining = Math.max(600, (scrollHeight || 900) - (top || 0));
    await shoot(send, target.width, Math.min(2200, remaining), join(OUT_DIR, target.out), top || 0);

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
  for (const target of TARGETS) {
    console.log("撮影中:", target.label, target.url);
    await shootOne(target);
  }
  console.log("完了");
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
