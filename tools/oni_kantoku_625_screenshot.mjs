#!/usr/bin/env node
/**
 * 案件#625：「他AIの言いっぱなしをコピペ1回で工場に積める入口」の実機タップ確認。
 *
 * 既存の案件#616スクリプト（tools/oni_kantoku_616_screenshot.mjs）と同じ安全な方式を流用する：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。画面も奪わない。
 *
 * 追加の安全策：status/relay.json への実通信をCDPでブロックする。
 * これをブロックしないと window.__relay が実在の中継所URLで埋まり、
 * テスト用の貼り付けテキストが本物の発車待ち列(queue.json)へPOSTされてしまう危険があるため。
 *
 * 使い方: node tools/oni_kantoku_625_screenshot.mjs
 * 出力: share/check/img/625-before.png, share/check/img/625-after.png
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const OUT_DIR = join(REPO_ROOT, "share/check/img");
const OUT_BEFORE = join(OUT_DIR, "625-before.png");
const OUT_AFTER = join(OUT_DIR, "625-after.png");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const URL = "https://tamago2022.github.io/tamago-shinchoku/index.html";
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 2000;
const TEST_TEXT = "## テスト提案A\nこれはテストです。\n\n## テスト提案B\nこれもテストです。";

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

  const port = 9700 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "oni-625-shot-"));
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
    await send("Network.enable");
    // 安全策：中継所(relay.json/cmd)への実通信を止める。本物の発車待ち列を汚さないため。
    await send("Network.setBlockedURLs", { urls: ["*status/relay.json*", "*/cmd"] });
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

    // 貼り付け欄の位置を確認してスクロール
    const findRect = async () => {
      const r = await send("Runtime.evaluate", {
        expression: `(() => {
          const el = document.getElementById('pasteText');
          if(!el) return JSON.stringify(null);
          el.scrollIntoView({block:'center'});
          const rect = el.getBoundingClientRect();
          return JSON.stringify({top: rect.top, bottom: rect.bottom, exists: true});
        })()`,
        returnByValue: true,
      });
      return JSON.parse(r.result?.value || "null");
    };
    const rect1 = await findRect();
    if (!rect1 || !rect1.exists) {
      throw new Error("#pasteText が本番ページに見つかりません（未反映の可能性）");
    }
    await sleep(400);

    // before スクショ（貼り付け欄が空の状態）
    const shot1 = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(OUT_BEFORE, Buffer.from(shot1.data, "base64"));
    console.log("保存(before):", OUT_BEFORE);

    // 実機タップに近い形で：値を入れてinputイベントを発火し、ボタンをクリックする
    const tapResult = await send("Runtime.evaluate", {
      expression: `(() => {
        const ta = document.getElementById('pasteText');
        const btn = document.getElementById('pasteSend');
        const msgEl = document.getElementById('pasteMsg');
        if(!ta || !btn) return JSON.stringify({ok:false, reason:'element missing'});
        ta.value = ${JSON.stringify(TEST_TEXT)};
        ta.dispatchEvent(new Event('input', {bubbles:true}));
        btn.click();
        return JSON.stringify({ok:true, msgAfterClick: msgEl ? msgEl.textContent : null});
      })()`,
      returnByValue: true,
    });
    console.log("タップ実行:", tapResult.result?.value);
    await sleep(500);

    const after = await send("Runtime.evaluate", {
      expression: `(() => {
        const msgEl = document.getElementById('pasteMsg');
        const ta = document.getElementById('pasteText');
        const pendingRaw = localStorage.getItem('shinchoku_pending_cmds');
        return JSON.stringify({
          msg: msgEl ? msgEl.textContent : null,
          textareaClearedAfterSend: ta ? ta.value === '' : null,
          pendingCount: pendingRaw ? JSON.parse(pendingRaw).length : 0,
        });
      })()`,
      returnByValue: true,
    });
    const info = JSON.parse(after.result?.value || "{}");
    console.log("実測(送信後):", info);
    if (!info.msg || !/本受け取りました/.test(info.msg)) {
      throw new Error("送信後メッセージに『◯本受け取りました』が出ませんでした: " + JSON.stringify(info));
    }

    const shot2 = await send("Page.captureScreenshot", { format: "png" });
    writeFileSync(OUT_AFTER, Buffer.from(shot2.data, "base64"));
    console.log("保存(after):", OUT_AFTER);

    console.log("PASS: 実機タップで『" + info.msg + "』を確認。pending件数=" + info.pendingCount + "（relay.jsonはブロック済みのためqueue.jsonへの実送信はしていない＝テストデータ汚染なし）");
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
