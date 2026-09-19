#!/usr/bin/env node
/**
 * 【946番・2026-09-19】バッジの「上の余白px ＝ 左の余白px」を実機で数える物差し。
 *
 * たまごさん：「見た目で判断しない。数字で確かめる。」「不快は悪。」
 *
 * 依存を足さない（playwright は joy-relief-station に入っていない実測あり）。
 * tools/_759_screenshot.mjs と同じ「使い捨てプロファイルの headless Chrome ＋ 生CDP」で、
 * バッジ画像の矩形と、その親のサムネ枠の矩形を読み、差をpxで出す。
 *
 * 使い方:
 *   node tools/_946_measure_badges.mjs <URL> [幅] [出力JSONパス]
 */
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const URL_ARG = process.argv[2];
const WIDTH = Number(process.argv[3] || 1440);
const OUT_JSON = process.argv[4] ? resolve(process.argv[4]) : null;
if (!URL_ARG) {
  console.error("使い方: node tools/_946_measure_badges.mjs <URL> [幅] [出力JSONパス]");
  process.exit(1);
}

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function findPage(port) {
  for (let i = 0; i < 160; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch { /* 起動待ち */ }
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
    if (msg.id && pending.has(msg.id)) { const cb = pending.get(msg.id); pending.delete(msg.id); cb(msg); }
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  const send = (method, params = {}) => new Promise((ok, ng) => {
    const myId = ++id;
    pending.set(myId, (msg) => (msg.error ? ng(new Error(JSON.stringify(msg.error))) : ok(msg.result)));
    ws.send(JSON.stringify({ id: myId, method, params }));
  });
  return { ready, send, close: () => ws.close() };
}

/** 16:9の大枠（プレイヤー）を、バッジが乗っているかどうかも含めて列挙する。 */
const FRAMES = `(() => {
  const out = [];
  for (const el of document.querySelectorAll('[class*="aspect-video"], [class*="aspect-square"]')) {
    const r = el.getBoundingClientRect();
    if (r.width < 200) continue;
    out.push({
      cls: (el.getAttribute('class') || '').slice(0, 90),
      box: Math.round(r.width) + 'x' + Math.round(r.height),
      badges: el.querySelectorAll('img[src*="/badges/"]').length,
      imgs: el.querySelectorAll('img').length,
      iframes: el.querySelectorAll('iframe').length,
      html: el.innerHTML.slice(0, 160),
    });
  }
  return JSON.stringify(out);
})()`;

/** ページの中で走らせる本体。バッジ画像ごとに「枠」と「余白px」を返す。 */
const PROBE = `(() => {
  const out = [];
  const imgs = [...document.querySelectorAll('img[src*="/badges/"]')];
  for (const img of imgs) {
    const chain = [];
    let el = img.parentElement, depth = 0, container = null, frame = null;
    while (el && depth < 9) {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      chain.push({
        d: depth, tag: el.tagName.toLowerCase(),
        cls: (el.getAttribute('class') || '').slice(0, 80),
        pos: cs.position, ct: cs.containerType,
        pad: cs.paddingTop + '|' + cs.paddingLeft,
        box: Math.round(r.width) + 'x' + Math.round(r.height),
      });
      if (!container && cs.containerType && cs.containerType !== 'normal') container = el;
      if (container && !frame && el !== container) frame = el;
      el = el.parentElement; depth++;
    }
    const fEl = frame || img.offsetParent;
    if (!fEl) continue;
    const f = fEl.getBoundingClientRect();
    const i = img.getBoundingClientRect();
    out.push({
      src: (img.getAttribute('src') || '').split('/').pop(),
      frameW: Math.round(f.width), frameH: Math.round(f.height),
      left: Math.round((i.left - f.left) * 10) / 10,
      top: Math.round((i.top - f.top) * 10) / 10,
      badgeW: Math.round(i.width), badgeH: Math.round(i.height),
      chain,
    });
  }
  return JSON.stringify(out);
})()`;

async function main() {
  const port = 9600 + Math.floor(Math.random() * 300);
  const profile = mkdtempSync(resolve(tmpdir(), "946-measure-"));
  const chrome = spawn(CHROME, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--no-first-run", "--no-default-browser-check", "--mute-audio",
    `--window-size=${WIDTH},1400`,
    "--disable-features=Translate,MediaRouter",
    "about:blank",
  ], { stdio: "ignore" });

  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Emulation.setDeviceMetricsOverride", {
      width: WIDTH, height: 1400, deviceScaleFactor: 1, mobile: WIDTH < 768,
    });
    await send("Page.navigate", { url: URL_ARG });
    for (let i = 0; i < 60; i++) {
      await sleep(500);
      const r = await send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
      if (r.result?.value === "complete") break;
    }
    // バッジは画像の読み込み後に不透明度が変わるだけで、矩形は先に決まる。念のため待つ。
    await sleep(6000);
    const r = await send("Runtime.evaluate", { expression: PROBE, returnByValue: true });
    const rows = JSON.parse(r.result?.value || "[]");

    console.log(`\n## ${URL_ARG}  （幅 ${WIDTH}px）`);
    if (!rows.length) console.log("   バッジ画像が見つかりませんでした");
    for (const x of rows) {
      const diff = Math.round((x.left - x.top) * 10) / 10;
      const verdict = Math.abs(diff) <= 1 ? "✅ 揃っている" : `❌ ズレ ${diff}px`;
      console.log(`  ${x.src}  枠 ${x.frameW}x${x.frameH}  バッジ ${x.badgeW}x${x.badgeH}  →  上 ${x.top}px / 左 ${x.left}px  ${verdict}`);
      for (const c of x.chain.slice(0, 4)) {
        console.log(`      d${c.d} ${c.tag} ${c.box} pos=${c.pos} ct=${c.ct} pad(上|左)=${c.pad} | ${c.cls}`);
      }
    }
    const fr = await send("Runtime.evaluate", { expression: FRAMES, returnByValue: true });
    const frames = JSON.parse(fr.result?.value || "[]");
    console.log("  -- 大きい枠（200px超）の一覧 --");
    for (const f of frames) {
      console.log(`      ${f.box} バッジ${f.badges} img${f.imgs} iframe${f.iframes} | ${f.cls}`);
    }

    if (OUT_JSON) {
      if (!existsSync(dirname(OUT_JSON))) mkdirSync(dirname(OUT_JSON), { recursive: true });
      writeFileSync(OUT_JSON, JSON.stringify({ url: URL_ARG, width: WIDTH, rows, frames }, null, 1));
      const shot = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
      if (shot?.data) writeFileSync(OUT_JSON.replace(/\.json$/, ".png"), Buffer.from(shot.data, "base64"));
    }
    close();
  } catch (e) {
    console.log(`## ${URL_ARG} （幅 ${WIDTH}px） → NG ${e.message}`);
  } finally {
    try { chrome.kill("SIGKILL"); } catch { /* 既に死んでいる */ }
  }
}
main();
