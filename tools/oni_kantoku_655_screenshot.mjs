#!/usr/bin/env node
/**
 * 案件#655：進捗表「発車待ち」ボタン改修（お金は赤・完了/取消・下げる）の証拠スクショを2枚取得する。
 *
 * 既存の安全な方式（tools/oni_kantoku_616_screenshot.mjs）をそのまま流用：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 1枚目：本番の「発車待ち」セクション（優先順位の色帯・順番ボタン・完了/取り消し/⬇️最後尾ボタン）
 * 2枚目：waiting項目の1件にブラウザ内メモリ上だけ一時的に costsMoney:true を注入し、
 *        題名が赤字＋💴になることを確認（queue.json自体は書き換えない・保存もしない）
 *
 * 使い方: node tools/oni_kantoku_655_screenshot.mjs
 * 出力: share/check/img/655-queue-buttons.png, share/check/img/655-costs-money.png
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");
const OUT_FILE_1 = join(OUT_DIR, "655-queue-buttons.png");
const OUT_FILE_2 = join(OUT_DIR, "655-costs-money.png");

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

async function main() {
  if (!existsSync(OUT_DIR)) mkdirSync(OUT_DIR, { recursive: true });

  const port = 9900 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "oni-655-shot-"));
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
    await send("Page.navigate", { url: URL });
    await waitComplete(send);
    await sleep(SETTLE_MS);

    // 「発車待ち」(#queue)が実際に描画され、ボタンが入っているか確認する
    const check = await send("Runtime.evaluate", {
      expression: `(() => {
        const box = document.getElementById('queue');
        const rows = box ? box.querySelectorAll('.qrow').length : 0;
        const hasQp = box ? box.querySelectorAll('[data-qp]').length : 0;
        const hasQdone = box ? box.querySelectorAll('[data-qdone]').length : 0;
        const hasQbottom = box ? box.querySelectorAll('[data-qbottom]').length : 0;
        const rect = box ? box.getBoundingClientRect() : null;
        return JSON.stringify({ rows, hasQp, hasQdone, hasQbottom, rect });
      })()`,
      returnByValue: true,
    });
    console.log("実測(1枚目):", check.result?.value);
    const info = JSON.parse(check.result?.value || "{}");
    if (!info.rows || !info.hasQp || !info.hasQdone || !info.hasQbottom) {
      throw new Error("発車待ちの行・ボタンが描画されていない、または0件のためスクショを撮っても証拠にならない: " + check.result?.value);
    }

    // 1枚目：発車待ちセクション（qbox見出し行から数行分が収まる高さ）。
    //   #queue自体はページのかなり下にあるので、その位置からクリップする（y:0からだと映らない）。
    const clip1 = { x: 0, y: Math.max(0, Math.floor(info.rect.top) - 10), width: 430, height: 700, scale: 1 };
    const shot1 = await send("Page.captureScreenshot", { format: "png", clip: clip1 });
    writeFileSync(OUT_FILE_1, Buffer.from(shot1.data, "base64"));
    console.log("保存:", OUT_FILE_1);

    // 2枚目：waiting項目の先頭1件へブラウザ内メモリ上だけ costsMoney:true を注入して再描画
    //   （queue.json自体は書き換えない・保存しない。表示ロジックの実証用）
    const inject = await send("Runtime.evaluate", {
      expression: `(() => {
        const items = (window.__queue && window.__queue.items) || [];
        const w = items.find(it => (it.status || "waiting") === "waiting");
        if (!w) return JSON.stringify({ ok:false, reason:"waiting項目が無い" });
        w.costsMoney = true;
        try { renderQueue(); } catch(e) { return JSON.stringify({ ok:false, reason:String(e) }); }
        const box = document.getElementById('queue');
        const moneyRow = box ? box.querySelector('.qt.money') : null;
        const rect = moneyRow ? moneyRow.closest('.qrow, .qbox').getBoundingClientRect() : null;
        return JSON.stringify({ ok: !!moneyRow, n: w.n, rect });
      })()`,
      returnByValue: true,
    });
    console.log("実測(2枚目・注入):", inject.result?.value);
    const info2 = JSON.parse(inject.result?.value || "{}");
    if (!info2.ok) {
      throw new Error("costsMoney注入後も赤字クラスが見つからない: " + inject.result?.value);
    }
    await sleep(300);
    const y2 = Math.max(0, Math.floor((info2.rect?.top || 0)) - 200);
    const clip2 = { x: 0, y: y2, width: 430, height: 400, scale: 1 };
    const shot2 = await send("Page.captureScreenshot", { format: "png", clip: clip2 });
    writeFileSync(OUT_FILE_2, Buffer.from(shot2.data, "base64"));
    console.log("保存:", OUT_FILE_2);

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
