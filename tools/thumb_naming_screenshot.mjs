#!/usr/bin/env node
/**
 * 案件#622：サムネイルの大きさに共通の呼び名をつける（スクショ付き1枚）用の
 * スクリーンショット取得ツール。
 *
 * 既存の鬼監督 関門①（tools/oni_kantoku_badge_ratio.mjs）と同じ安全な方式を流用する：
 *   - headless Chromeをローカルの一時プロファイルで起動（--mute-audio・画面には一切出ない）
 *   - CDP(Chrome DevTools Protocol)で操作
 *   - 使い終わったら必ずSIGKILLでプロセスごと消す
 * たまごさんの通常ブラウザ(Brave等)には一切触れない。タブも増えない。
 *
 * 対象4種と、実際のコード上の実装箇所（joy-relief-stationリポジトリで確認済み）：
 *   主役: src/routes/cover-guide.tsx のメイン動画iframeの親 `.aspect-video.bg-black`
 *   半分: src/components/NextUpCard.tsx（「オリジナルはこちら」セクション内の1枚目）
 *   棚札: src/components/ShelfCardView.tsx の `.aspect-square`（棚グリッド1枚目）
 *   豆　: src/components/SpokesHubCoversSection.tsx の `img.w-36.aspect-video`（名カバー1枚目）
 *
 * 使い方: node tools/thumb_naming_screenshot.mjs
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
const LOAD_TIMEOUT_MS = 20000;
const SETTLE_MS = 1200;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const TARGETS = [
  {
    name: "shuyaku",
    label: "主役",
    url: "https://joy-relief-station.lovable.app/cover-guide?artist=akiko&song=love-theme-from-spartacus",
    selector: 'iframe[src*="youtube.com/embed"]',
    useParent: true, // iframeの親(aspect-video.bg-black)を撮る
    pad: 16,
  },
  {
    name: "hanbun",
    label: "半分",
    url: "https://joy-relief-station.lovable.app/cover-guide?artist=akiko&song=love-theme-from-spartacus",
    selector: 'button.group.block.w-full',
    nth: 0,
    pad: 16,
  },
  {
    name: "tanafuda",
    label: "棚札",
    url: "https://joy-relief-station.lovable.app/shelf/music/asia",
    selector: 'div.relative.aspect-square.w-full',
    nth: 0,
    pad: 16,
  },
  {
    name: "mame",
    label: "豆",
    url: "https://joy-relief-station.lovable.app/cover-guide?artist=akiko&song=love-theme-from-spartacus",
    selector: 'img.w-36.aspect-video',
    nth: 0,
    pad: 12,
    clickOpenText: "名カバー",
  },
];

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
  const profile = mkdtempSync(join(tmpdir(), "thumb-naming-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=1280,1400",
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  const results = [];
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Target.activateTarget", { targetId: target.id });

    for (const t of TARGETS) {
      try {
        await send("Page.navigate", { url: t.url });
        await waitComplete(send);
        await sleep(SETTLE_MS);

        if (t.clickOpenText) {
          // 「名カバー」等、折りたたみを開くボタンをテキストで探してクリック
          const clickExpr = `
            (function(){
              var btns = Array.from(document.querySelectorAll('button'));
              var b = btns.find(function(x){ return x.textContent.includes(${JSON.stringify(t.clickOpenText)}); });
              if (b) { b.click(); return true; }
              return false;
            })()`;
          await send("Runtime.evaluate", { expression: clickExpr, returnByValue: true });
          await sleep(800);
        }

        const rectExpr = `
          (function(){
            var els = document.querySelectorAll(${JSON.stringify(t.selector)});
            var el = els[${t.nth ?? 0}];
            if (!el) return null;
            var target = el;
            if (${t.useParent ? "true" : "false"} && el.parentElement) target = el.parentElement;
            var r = target.getBoundingClientRect();
            return JSON.stringify({ x: r.x, y: r.y, width: r.width, height: r.height, found: els.length });
          })()`;
        const r = await send("Runtime.evaluate", { expression: rectExpr, returnByValue: true });
        const rect = r.result?.value ? JSON.parse(r.result.value) : null;

        if (!rect) {
          results.push({ ...t, error: `セレクタで要素が見つからない: ${t.selector}` });
          continue;
        }

        const pad = t.pad ?? 0;
        const clip = {
          x: Math.max(0, rect.x - pad),
          y: Math.max(0, rect.y - pad),
          width: rect.width + pad * 2,
          height: rect.height + pad * 2,
          scale: 1,
        };

        const shot = await send("Page.captureScreenshot", {
          format: "png",
          clip,
          fromSurface: true,
          captureBeyondViewport: true,
        });
        const outPath = join(OUT_DIR, `622-${t.name}.png`);
        writeFileSync(outPath, Buffer.from(shot.data, "base64"));
        results.push({ ...t, rect, outPath, ok: true });
      } catch (e) {
        results.push({ ...t, error: e.message });
      }
    }
    close();
  } finally {
    chrome.kill("SIGKILL");
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* noop */
    }
  }

  for (const r of results) {
    if (r.ok) {
      console.log(`[OK] ${r.label}(${r.name}) → ${r.outPath} rect=${JSON.stringify(r.rect)}`);
    } else {
      console.log(`[NG] ${r.label}(${r.name}) → ${r.error}`);
    }
  }
  const failed = results.filter((r) => !r.ok);
  process.exit(failed.length > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error("実行時エラー:", e);
  process.exit(2);
});
