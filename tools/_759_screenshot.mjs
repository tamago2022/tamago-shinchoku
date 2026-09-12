#!/usr/bin/env node
/**
 * 案件#759：「できたもの」を新しく作った／直した で分けたビフォーアフターの証拠スクショ。
 * 既存の tools/oni_kantoku_616_screenshot.mjs と同じ安全な方式（headless Chrome・
 * 一時プロファイル・使用後SIGKILL・たまごさんの通常ブラウザには一切触れない）をそのまま流用する。
 *
 * 使い方: node tools/_759_screenshot.mjs <URL> <出力PNGパス> [クリックするセレクタ]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const URL_ARG = process.argv[2];
const OUT_FILE = resolve(process.argv[3]);
const CLICK_SEL = process.argv[4] || null;
if (!URL_ARG || !OUT_FILE) {
  console.error("使い方: node tools/_759_screenshot.mjs <URL> <出力PNGパス> [クリックするセレクタ]");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 1500;

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
    new Promise((resolve2, reject) => {
      const myId = ++id;
      pending.set(myId, (msg) => {
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve2(msg.result);
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

async function main() {
  const outDir = dirname(OUT_FILE);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const port = 9900 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(resolve(tmpdir(), "759-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=430,1400",
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
    await send("Emulation.setDeviceMetricsOverride", {
      width: 430,
      height: 1400,
      deviceScaleFactor: 2,
      mobile: true,
    });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    // できたもの棚を開く（<details>を明示的にopenへ）
    await send("Runtime.evaluate", {
      expression: `(() => { const sec = document.getElementById('dekitaSec'); if(sec) sec.open = true; })()`,
    });
    await sleep(300);

    if (CLICK_SEL) {
      await send("Runtime.evaluate", {
        expression: `(() => { const el = document.querySelector(${JSON.stringify(CLICK_SEL)}); if(el) el.click(); })()`,
      });
      await sleep(600);
    }

    const check = await send("Runtime.evaluate", {
      expression: `(() => {
        const sec = document.getElementById('dekitaSec');
        const box = document.getElementById('dekita');
        const rows = box ? box.querySelectorAll('.dkrow').length : 0;
        const rect = sec ? sec.getBoundingClientRect() : null;
        return JSON.stringify({ hasSec: !!sec, open: sec ? sec.open : false, rows, rect });
      })()`,
      returnByValue: true,
    });
    console.log("実測:", check.result?.value);
    const info = JSON.parse(check.result?.value || "{}");
    if (!info.hasSec) throw new Error("dekitaSecが見つからない: " + check.result?.value);

    const clip = { x: 0, y: 0, width: 430, height: Math.min(1400, Math.ceil((info.rect?.bottom || 900)) + 20), scale: 1 };
    const shot = await send("Page.captureScreenshot", { format: "png", clip });
    writeFileSync(OUT_FILE, Buffer.from(shot.data, "base64"));
    console.log("保存:", OUT_FILE);
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
