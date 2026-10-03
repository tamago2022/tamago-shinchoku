#!/usr/bin/env node
/**
 * 1264番：1046-live2d.html が「canvasに何も描けていない」の実測確認用。
 * tools/_1371_screenshot.mjs の複製（cp）をベースに、holdSec固有ロジックだけを
 * 「読み込んで動かすボタンを押す→canvasに非透明ピクセルが出たか」の確認へ差し替えた。
 * 安全な方式（headless・一時プロファイル・使用後SIGKILL）はそのまま。
 *
 * 使い方: node tools/_1264_l2d_check.mjs <URL> <出力PNGパス>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const URL_ARG = process.argv[2];
const OUT_FILE = resolve(process.argv[3]);
if (!URL_ARG || !OUT_FILE) {
  console.error("使い方: node tools/_1371_screenshot.mjs <URL> <出力PNGパス>");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 2000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch {}
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
    } catch {}
  }
  return false;
}

async function main() {
  const outDir = dirname(OUT_FILE);
  if (!existsSync(outDir)) mkdirSync(outDir, { recursive: true });

  const port = 9900 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(resolve(tmpdir(), "1371-shot-"));
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
    await send("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-color-scheme", value: "light" }],
    });
    await send("Target.activateTarget", { targetId: target.id });

    await send("Page.navigate", { url: URL_ARG });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    // 「読み込んで動かす」(#go)を押す
    const clicked = await send("Runtime.evaluate", {
      expression: `(() => { const b = document.getElementById('go'); if(!b) return 'no-button'; b.click(); return 'clicked'; })()`,
      returnByValue: true,
    });
    console.log("click:", clicked.result?.value);

    // CDN取得＋WebGL初期化の時間を確保（長めに取って「いずれ終わるのか」を見る）
    await sleep(25000);

    const check = await send("Runtime.evaluate", {
      expression: `(() => {
        const cv = document.getElementById('cv');
        const ph = document.getElementById('ph');
        const log = document.getElementById('log');
        let pixelInfo = null;
        try {
          if (cv && cv.width && cv.height) {
            const ctx = cv.getContext('webgl2') || cv.getContext('webgl');
            if (ctx) {
              const w = Math.min(cv.width, 60), h = Math.min(cv.height, 60);
              const px = new Uint8Array(w*h*4);
              ctx.readPixels(0, Math.floor(cv.height/2)-Math.floor(h/2), w, h, ctx.RGBA, ctx.UNSIGNED_BYTE, px);
              let nonZero = 0;
              for (let i=0;i<px.length;i+=4) { if (px[i+3] !== 0) nonZero++; }
              pixelInfo = { sampledNonTransparentPixels: nonZero, sampledTotal: w*h };
            } else {
              pixelInfo = { error: 'no gl context readable on canvas' };
            }
          }
        } catch(e) { pixelInfo = { error: String(e) }; }
        return JSON.stringify({
          cvWidth: cv ? cv.width : null,
          cvHeight: cv ? cv.height : null,
          cvDisplay: cv ? getComputedStyle(cv).display : null,
          phDisplay: ph ? getComputedStyle(ph).display : null,
          phText: ph ? ph.textContent : null,
          logText: log ? log.textContent : null,
          hasPIXI: typeof window.PIXI,
          hasPIXILive2d: (typeof window.PIXI !== 'undefined' && !!window.PIXI.live2d),
          hasCubismCore: typeof window.Live2DCubismCore,
          modelLoaded: typeof window.__m,
          pixelInfo
        });
      })()`,
      returnByValue: true,
    });
    console.log("実測:", check.result?.value);
    const info = JSON.parse(check.result?.value || "{}");

    const stageRect = await send("Runtime.evaluate", {
      expression: `(() => { const s = document.getElementById('stage'); const r = s ? s.getBoundingClientRect() : null; return JSON.stringify(r); })()`,
      returnByValue: true,
    });
    const rect = JSON.parse(stageRect.result?.value || "null") || { x: 0, y: 0, width: 430, height: 600 };
    const clip = {
      x: Math.max(0, Math.floor(rect.x)),
      y: Math.max(0, Math.floor(rect.y)),
      width: Math.max(1, Math.ceil(rect.width)),
      height: Math.max(1, Math.ceil(rect.height)),
      scale: 1,
    };
    const shot = await send("Page.captureScreenshot", { format: "png", clip, captureBeyondViewport: true });
    writeFileSync(OUT_FILE, Buffer.from(shot.data, "base64"));
    console.log("保存:", OUT_FILE);
    close();
  } finally {
    chrome.kill("SIGKILL");
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {}
  }
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
