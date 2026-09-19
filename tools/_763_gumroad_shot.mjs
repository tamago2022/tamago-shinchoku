#!/usr/bin/env node
/**
 * 763番：eggypop.gumroad.com（既存Gumroadストア、ログイン不要の公開ページ）の
 * 実在確認用スクショ。ログインもクリックも一切しない、ただページを開いて撮るだけ。
 * 既存手法（oni_kantoku_725_screenshot.mjs）のheadless Chrome + CDPをそのまま流用。
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
const URL = "https://eggypop.gumroad.com/";
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
async function evalJs(send, expr) {
  const r = await send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
  return r.result?.value;
}
async function shootFull(send, outFile) {
  const shot = await send("Page.captureScreenshot", { format: "png" });
  writeFileSync(outFile, Buffer.from(shot.data, "base64"));
  console.log("保存:", outFile);
}

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });
  const port = 31000 + Math.floor(Math.random() * 3000);
  const profile = mkdtempSync(join(tmpdir(), "oni-763-shot-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=1280,900",
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
    await send("Emulation.setDeviceMetricsOverride", { width: 1280, height: 900, deviceScaleFactor: 2, mobile: false });
    await send("Target.activateTarget", { targetId: target.id });
    await send("Page.navigate", { url: URL });
    await sleep(6000);
    const title = await evalJs(send, "document.title");
    const bodyLen = await evalJs(send, "document.body.innerText.length");
    const bodyPreview = await evalJs(send, "document.body.innerText.slice(0,300)");
    console.log("title:", title, "bodyLen:", bodyLen);
    console.log("preview:", bodyPreview);
    await shootFull(send, join(OUT_DIR, "763-gumroad-store.png"));
    close();
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  }
}

main().catch((e) => {
  console.error("失敗:", e.message);
  process.exitCode = 1;
});
