#!/usr/bin/env node
/**
 * 1163番【投稿前の関所：曲ページを機械で数える】
 *
 * たまごさんの言葉（2026-09-26）:
 *   「投稿予定のものにメインの動画がないなんてことはあり得ない」
 *   「投稿前にページを1個ずつ全部作っていかないとダメ。関連も最低4つは欲しい」
 *
 * 数えるもの（本番URLを1本ずつ開いて数える。推定しない）:
 *   ① HTTPコード（200か）
 *   ② 本人の動画（一番大きい動画）があるか
 *   ③ 関連が4つ以上あるか
 *   ④ コピー（本文）が空でないか
 *
 * 方式は tools/verify_click.mjs と同じ：headless Chrome・一時プロファイル・
 * 使用後にSIGKILL。**たまごさんの通常ブラウザ／Braveには一切触れない。
 * claude-in-chrome も内蔵ブラウザも使わない＝許可ダイアログを出さない。**
 *
 * 使い方: node tools/1163_page_sekisho.mjs <URLを1行ずつ書いたファイル> <出力JSON>
 */
import { spawn } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve } from "node:path";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LIST_FILE = process.argv[2];
const OUT_JSON = process.argv[3] ? resolve(process.argv[3]) : null;
// 重いページ（曲数の多いアーティスト）は6秒では見出しすら出ず、
// 「関連が0本」と誤判定していた（2026-09-26 実測：Scarborough Fair）。
// 環境変数 SEKISHO_SETTLE_MS で伸ばせるようにし、既定も伸ばす。
const SETTLE_MS = Number(process.env.SEKISHO_SETTLE_MS || 14000);
const LOAD_TIMEOUT_MS = 30000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

if (!LIST_FILE || !OUT_JSON) {
  console.error("使い方: node tools/1163_page_sekisho.mjs <URL一覧> <出力JSON>");
  process.exit(1);
}
const urls = readFileSync(LIST_FILE, "utf8").split("\n").map((s) => s.trim()).filter(Boolean);

async function findPage(port) {
  for (let i = 0; i < 300; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page;
    } catch { /* 起動待ち */ }
    await sleep(300);
  }
  throw new Error("Chromeのデバッグ口が開きませんでした");
}

function connect(wsUrl, onEvent) {
  const ws = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const cb = pending.get(msg.id);
      pending.delete(msg.id);
      cb(msg);
    } else if (msg.method && onEvent) onEvent(msg.method, msg.params);
  });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error("CDP接続失敗")));
  });
  const send = (method, params = {}) =>
    new Promise((res2, rej) => {
      const myId = ++id;
      pending.set(myId, (m) => (m.error ? rej(new Error(JSON.stringify(m.error))) : res2(m.result)));
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}

// ★ページの中の「動画」を、見えている大きさごと全部数える式。
//   YouTubeの動画は iframe(embed) か サムネイル画像(i.ytimg.com) のどちらかで出る。
const COUNT_EXPR = `JSON.stringify((() => {
  const vid = (s) => {
    if (!s) return null;
    let m = s.match(/(?:embed\\/|vi\\/|v=|youtu\\.be\\/)([A-Za-z0-9_-]{11})/);
    return m ? m[1] : null;
  };
  const items = [];
  document.querySelectorAll('iframe').forEach((el) => {
    const r = el.getBoundingClientRect();
    const id = vid(el.src || el.getAttribute('data-src') || '');
    if (id) items.push({ kind: 'iframe', id, w: Math.round(r.width), h: Math.round(r.height) });
  });
  document.querySelectorAll('img').forEach((el) => {
    const r = el.getBoundingClientRect();
    const id = vid(el.src || el.getAttribute('data-src') || '');
    if (id) items.push({ kind: 'thumb', id, w: Math.round(r.width), h: Math.round(r.height), alt: (el.alt||'').slice(0,60) });
  });
  document.querySelectorAll('a[href*="youtu"]').forEach((el) => {
    const id = vid(el.getAttribute('href') || '');
    const r = el.getBoundingClientRect();
    if (id) items.push({ kind: 'link', id, w: Math.round(r.width), h: Math.round(r.height), text: (el.innerText||'').trim().slice(0,60) });
  });
  document.querySelectorAll('[style*="ytimg"],[data-youtube-id],[data-video-id]').forEach((el) => {
    const r = el.getBoundingClientRect();
    const id = el.getAttribute('data-youtube-id') || el.getAttribute('data-video-id') || vid(el.getAttribute('style')||'');
    if (id && /^[A-Za-z0-9_-]{11}$/.test(id)) items.push({ kind: 'style', id, w: Math.round(r.width), h: Math.round(r.height) });
  });
  const seen = new Map();
  for (const it of items) {
    const p = seen.get(it.id);
    const area = it.w * it.h;
    if (!p || area > p.w * p.h) seen.set(it.id, it);
  }
  const uniq = Array.from(seen.values()).sort((a, b) => b.w * b.h - a.w * a.h);
  const txt = (document.body.innerText || '');
  return {
    title: document.title,
    h1: (document.querySelector('h1')?.innerText || '').trim().slice(0, 120),
    textLen: txt.length,
    text_head: txt.slice(0, 900),
    lines: txt.split('\\n').map(s => s.trim()),
    kanren_midashi: /この曲の関連動画/.test(txt),
    kanren_honsuu: (txt.match(/この曲の関連動画\\s*(\\d+)\\s*本/) || [null, null])[1],
    videos: uniq,
    videos_all: items.length,
    headings: Array.from(document.querySelectorAll('h2,h3')).map(e => (e.innerText||'').trim().slice(0,60)).filter(Boolean).slice(0, 25),
  };
})())`;

async function main() {
  const port = 9700 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(resolve(tmpdir(), "sekisho1163-"));
  const chrome = spawn(CHROME, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio", "--window-size=1280,2400",
    "--disable-features=Translate,MediaRouter", "about:blank",
  ], { stdio: "ignore", detached: true });
  chrome.unref();

  const out = { at: new Date().toISOString(), rows: [] };
  let page, cdp;
  try {
    page = await findPage(port);
    const statuses = new Map();
    let errs = [];
    cdp = connect(page.webSocketDebuggerUrl, (method, params) => {
      if (method === "Network.responseReceived" && params?.type === "Document") {
        statuses.set(params.response.url, params.response.status);
      }
      if (method === "Network.loadingFailed") {
        errs.push("loadingFailed: " + (params?.errorText || "") + " " + (params?.type || ""));
      }
      if (method === "Runtime.exceptionThrown") {
        errs.push("JS例外: " + String(params?.exceptionDetails?.text || "").slice(0, 200));
      }
      if (method === "Runtime.consoleAPICalled" && params?.type === "error") {
        errs.push("console.error: " + (params.args || []).map((a) => String(a.value || a.description || "")).join(" ").slice(0, 200));
      }
    });
    await cdp.ready;
    await cdp.send("Page.enable");
    await cdp.send("Network.enable");
    await cdp.send("Runtime.enable");

    for (const url of urls) {
      const row = { url };
      errs = [];
      try {
        await cdp.send("Page.navigate", { url });
        const t0 = Date.now();
        while (Date.now() - t0 < LOAD_TIMEOUT_MS) {
          await sleep(400);
          const r = await cdp.send("Runtime.evaluate", { expression: "document.readyState", returnByValue: true });
          if (r.result?.value === "complete") break;
        }
        // ★実測(2026-09-26)：6秒では本文が描かれず textLen=52（footerだけ）だった。
        //   このサイトは coverGuide を遅延読み込みするので、**中身が出るまで待つ**。
        //   出ないままなら「出なかった」と書く（推定しない）。
        let data = null;
        const tEnd = Date.now() + 75000;
        while (Date.now() < tEnd) {
          await cdp.send("Runtime.evaluate", { expression: "window.scrollTo(0, document.body.scrollHeight)" });
          await sleep(1500);
          await cdp.send("Runtime.evaluate", { expression: "window.scrollTo(0, 0)" });
          const r = await cdp.send("Runtime.evaluate", { expression: COUNT_EXPR, returnByValue: true });
          data = JSON.parse(r.result.value);
          if (data.textLen > 400 && data.videos.length > 0) break;
          await sleep(1500);
        }
        row.data = data;
        row.waited_ms = 75000 - Math.max(0, tEnd - Date.now());
        row.http = statuses.get(url) || statuses.get(url + "/") || null;
      } catch (e) {
        row.error = String(e).slice(0, 300);
      }
      row.errors = errs.slice(0, 12);
      out.rows.push(row);
      console.log(`${url} → http=${row.http} 動画=${row.data?.videos?.length ?? "?"} 文字数=${row.data?.textLen ?? "?"}`);
    }
  } finally {
    try { cdp?.close(); } catch {}
    try { process.kill(-chrome.pid, "SIGKILL"); } catch {}
    try { chrome.kill("SIGKILL"); } catch {}
  }
  const d = dirname(OUT_JSON);
  if (!existsSync(d)) mkdirSync(d, { recursive: true });
  writeFileSync(OUT_JSON, JSON.stringify(out, null, 2));
  console.log("書いた: " + OUT_JSON);
}
main().catch((e) => { console.error("落ちた: " + e); process.exit(1); });
