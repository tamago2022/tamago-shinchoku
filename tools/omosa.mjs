#!/usr/bin/env node
/**
 * 1028番【物差し】ごきげん補給所の「重さ」を実測する。
 *
 * ■ なぜ要るか（2026-09-23・たまごさんの注文）
 *   「とにかく重いんだ。軽くしてくれるだけでもいい。」
 *   ところが **今、重さを測る物差しが無い。** だから誰かが「軽くしました」と言っても、
 *   本当かどうか分からない。動いているのに何も取れていない“嘘の緑”を今日だけで何件も見た。
 *   → 直す前に、まず物差しを作る。これはその物差し。**直さない。測るだけ。**
 *
 * ■ 測る4つ（全部、実測の数字）
 *   1. トップページが何バイト送ってくるか（HTML/JS/CSS/画像/フォントの内訳＋一番でかい1つ）
 *   2. 棚編集を押してから動くまで何秒か（最初の変化まで／落ち着くまで／画面が固まった最長）
 *   3. URLを貼って落ちる確率（runs回やって何回落ちたか。落ちた中身も残す）
 *   4. スマホ幅(375px)で同じ4つ ＋ 横に流れていないか
 *
 * ■ やらないこと（安全のため）
 *   ・GETだけ。書き込みボタン（保存・削除・送信）は押さない。
 *   ・たまごさんの普段のChromeには触らない（毎回その場限りの一時プロファイル、使用後SIGKILL）。
 *   ・課金0。外部AIを1回も呼ばない。
 *
 * ■ 使い方
 *   node tools/omosa.mjs                      … 設定(tools/omosa_target.json)どおり全部測る
 *   node tools/omosa.mjs --runs 5             … 落ち率の試行回数だけ変える（速く回したいとき）
 *   node tools/omosa.mjs --width 375          … その幅だけ
 *   node tools/omosa.mjs --recon              … DOMの下見だけ（押す物・貼る所を探して名前を出す）
 *   結果 → status/omosa_last.json（最新）と status/omosa_log.jsonl（履歴・前回比に使う）
 */
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync, appendFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(__dirname, "..");
const CFG_PATH = join(__dirname, "omosa_target.json");
const OUT_LAST = join(REPO, "status", "omosa_last.json");
const OUT_LOG = join(REPO, "status", "omosa_log.jsonl");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
// ★「サイトが落ちた」と「こちらの測定装置がコケた」を混ぜないための印。
const MEASURE_FAIL = /デバッグ口が開きません|CDP接続失敗|ENOENT|EADDRINUSE|spawn/;

// ---------- 設定を読む ----------
const cfg = JSON.parse(readFileSync(CFG_PATH, "utf-8"));
const argv = process.argv.slice(2);
const argVal = (name, dflt) => {
  const i = argv.indexOf(name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};
const RECON_ONLY = argv.includes("--recon");
// ★2026-09-23：工場の runner に **1件90秒の打ち切り** が入った（status/gaibu_runner.log の「⏱ 打ち切り」）。
//   ＝ 全部を1回で測ろうとすると必ず殺される。**測る中身を小分けにして、1回90秒に収める。**
//   phase=bytes …① 何バイト送ってくるか（約30秒）
//   phase=edit  …② 棚編集が触れるようになるまで（約70秒）
//   phase=open  …③ URLを開いて落ちるか（runs回・1回約15秒）
//   結果は status/omosa_last.json に **上書きではなく足し込む**（前の phase の数字を消さない）。
const PHASE = argVal("--phase", "all");
const RUNS = Number(argVal("--runs", cfg.runs ?? 20));
const WIDTHS = argv.includes("--width") ? [Number(argVal("--width", 1280))] : (cfg.widths ?? [1280, 375]);
const URL_ARG = argVal("--url", cfg.url);
const SETTLE = cfg.settleMs ?? 2500;
const FREEZE_LIMIT = cfg.freezeLimitMs ?? 8000;

// ---------- CDP（events も拾える薄いラッパ） ----------
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
  const handlers = new Map();
  let dead = null;
  ws.addEventListener("message", (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const cb = pending.get(msg.id);
      pending.delete(msg.id);
      cb(msg);
    } else if (msg.method) {
      const hs = handlers.get(msg.method);
      if (hs) hs.forEach((h) => { try { h(msg.params); } catch { /* 無視 */ } });
    }
  });
  ws.addEventListener("close", () => { dead = dead || "WebSocketが閉じました（＝描画係が死んだ可能性）"; });
  const ready = new Promise((res, rej) => {
    ws.addEventListener("open", res);
    ws.addEventListener("error", (e) => rej(new Error(`CDP接続失敗: ${e?.message ?? e}`)));
  });
  // timeoutMs を超えたら「固まっている」とみなして投げる（＝落ちたの判定に使う）
  const send = (method, params = {}, timeoutMs = 30000) =>
    new Promise((resolve2, reject) => {
      if (dead) return reject(new Error(dead));
      const myId = ++id;
      const timer = setTimeout(() => {
        pending.delete(myId);
        reject(new Error(`FROZEN:${method} が ${timeoutMs}ms 返事をしません`));
      }, timeoutMs);
      pending.set(myId, (msg) => {
        clearTimeout(timer);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve2(msg.result);
      });
      try { ws.send(JSON.stringify({ id: myId, method, params })); }
      catch (e) { clearTimeout(timer); pending.delete(myId); reject(e); }
    });
  const on = (method, fn) => {
    if (!handlers.has(method)) handlers.set(method, []);
    handlers.get(method).push(fn);
  };
  return { ready, send, on, close: () => { try { ws.close(); } catch { /* 無視 */ } }, isDead: () => dead };
}

async function withChrome(width, height, mobile, fn) {
  const port = 9300 + Math.floor(Math.random() * 400);
  const profile = mkdtempSync(resolve(tmpdir(), "omosa-"));
  const chrome = spawn(CHROME, [
    "--headless=new",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    "--no-first-run", "--mute-audio",
    "--disable-features=Translate,MediaRouter",
    `--window-size=${width},${height}`,
    "about:blank",
  ], { stdio: "ignore" });
  try {
    const target = await findPage(port);
    const cdp = connect(target.webSocketDebuggerUrl);
    await cdp.ready;
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Log.enable").catch(() => {});
    await cdp.send("Network.enable", { maxTotalBufferSize: 100e6, maxResourceBufferSize: 50e6 });
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width, height, deviceScaleFactor: 1, mobile,
    });
    await cdp.send("Network.setCacheDisabled", { cacheDisabled: true }); // ★毎回まっさらで測る
    return await fn(cdp);
  } finally {
    chrome.kill("SIGKILL");
    try { rmSync(profile, { recursive: true, force: true }); } catch { /* 無視 */ }
  }
}

// ---------- 荷物（バイト）を数える係 ----------
function attachNetwork(cdp) {
  const byId = new Map();
  const done = [];
  cdp.on("Network.responseReceived", (p) => {
    byId.set(p.requestId, {
      url: p.response?.url || "", type: p.type || "Other",
      mime: p.response?.mimeType || "", status: p.response?.status || 0,
      fromCache: !!p.response?.fromDiskCache,
    });
  });
  cdp.on("Network.loadingFinished", (p) => {
    const r = byId.get(p.requestId);
    if (!r) return;
    done.push({ ...r, bytes: Math.max(0, p.encodedDataLength || 0) });
    byId.delete(p.requestId);
  });
  return done;
}

const KIND = (r) => {
  const u = (r.url || "").split("?")[0].toLowerCase();
  const m = (r.mime || "").toLowerCase();
  if (r.type === "Document" || m.includes("text/html")) return "HTML";
  if (r.type === "Script" || m.includes("javascript") || u.endsWith(".js") || u.endsWith(".mjs")) return "JS";
  if (r.type === "Stylesheet" || m.includes("text/css") || u.endsWith(".css")) return "CSS";
  if (r.type === "Image" || m.startsWith("image/")) return "画像";
  if (r.type === "Font" || m.includes("font") || /\.(woff2?|ttf|otf|eot)$/.test(u)) return "フォント";
  if (m.includes("json") || u.endsWith(".json")) return "データ(JSON)";
  if (r.type === "Media" || m.startsWith("video/") || m.startsWith("audio/")) return "動画音声";
  return "その他";
};

const shortName = (u) => {
  try { const x = new URL(u); return x.hostname + x.pathname; } catch { return String(u).slice(0, 120); }
};

// ---------- ページに仕込む見張り ----------
const WATCHER = `(() => {
  window.__om = { t0: performance.now(), mutFirst: null, mutLast: null, mutCount: 0,
                  maxGap: 0, lastFrame: performance.now(), errs: [] };
  try {
    new MutationObserver(() => {
      const n = performance.now();
      if (window.__om.mutFirst === null) window.__om.mutFirst = n;
      window.__om.mutLast = n; window.__om.mutCount++;
    }).observe(document.documentElement, { subtree: true, childList: true, attributes: true, characterData: true });
  } catch (e) {}
  (function loop(){
    const n = performance.now(), d = n - window.__om.lastFrame;
    if (d > window.__om.maxGap) window.__om.maxGap = d;
    window.__om.lastFrame = n;
    requestAnimationFrame(loop);
  })();
  window.addEventListener('error', e => window.__om.errs.push(String(e.message||e).slice(0,200)));
  window.addEventListener('unhandledrejection', e => window.__om.errs.push('promise:' + String(e.reason).slice(0,200)));
  return 1;
})()`;

const RESET_WATCHER = `(() => { const o=window.__om; if(!o) return 0;
  o.t0=performance.now(); o.mutFirst=null; o.mutLast=null; o.mutCount=0; o.maxGap=0; o.lastFrame=performance.now();
  return 1; })()`;

// 押す物・貼る所を探す（見つからなければ「見つからない」と正直に返す）
const FINDER = (texts) => `(() => {
  const want = ${JSON.stringify(texts)};
  const norm = s => (s||'').replace(/\\s+/g,'').trim();
  const clickable = [...document.querySelectorAll('button,a,summary,[role=button],[role=tab],input[type=button],input[type=submit],label')];
  const cand = [];
  for (const el of clickable) {
    const t = norm(el.innerText || el.value || el.getAttribute('aria-label') || el.title || '');
    if (!t) continue;
    for (let i=0;i<want.length;i++) if (t.includes(norm(want[i]))) { cand.push({ i, t: t.slice(0,40), el }); break; }
  }
  cand.sort((a,b)=> a.i-b.i || a.t.length-b.t.length);
  const hit = cand[0];
  if (hit) hit.el.setAttribute('data-omosa-edit','1');
  const inputs = [...document.querySelectorAll('input[type=text],input[type=url],input[type=search],input:not([type]),textarea,[contenteditable=true]')]
    .map(el => ({ el, hint: norm((el.placeholder||'')+(el.getAttribute('aria-label')||'')+(el.name||'')+(el.id||'')) }));
  // ★ここは一度間違えた所なので理由を残す（2026-09-23）
  //   最初「URLっぽい欄が無ければ最初の入力欄」にしていたら、どのページにも居る
  //   **足元のひとこと目安箱（感想を書く箱）**が毎回選ばれた。
  //   ＝ たまごさんが言っている「URLを貼る所」とは**別物**を20回叩くところだった。
  //   違うものを測って数字を出すのが一番たちが悪い。だから **URLっぽい欄が無ければ諦める。**
  const pri = inputs.find(x => /url|youtube|リンク|動画|http/i.test(x.hint));
  if (pri) pri.el.setAttribute('data-omosa-paste','1');
  return JSON.stringify({
    editFound: !!hit, editText: hit ? hit.t : null,
    pasteFound: !!pri, pasteHint: pri ? pri.hint.slice(0,60) : null,
    clickableSample: clickable.slice(0,40).map(e => norm(e.innerText||e.value||'').slice(0,24)).filter(Boolean),
    inputCount: inputs.length,
    inputHints: inputs.map(x => x.hint.slice(0,40)).slice(0,10)
  });
})()`;

const BOX = (sel) => `(() => { const el=document.querySelector(${JSON.stringify(sel)});
  if(!el) return '0'; el.scrollIntoView({block:'center'});
  const r=el.getBoundingClientRect();
  return JSON.stringify({x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2), w:Math.round(r.width), h:Math.round(r.height)}); })()`;

const READ_OM = `(() => { const o=window.__om||{};
  return JSON.stringify({ first: o.mutFirst===null?null:Math.round(o.mutFirst-o.t0),
    settled: o.mutLast===null?null:Math.round(o.mutLast-o.t0), count:o.mutCount,
    maxGap: Math.round(o.maxGap||0), errs:(o.errs||[]).slice(-5),
    bodyLen: (document.body?document.body.innerText.length:0),
    heapMB: (performance.memory? Math.round(performance.memory.usedJSHeapSize/1048576):null),
    scrollW: document.documentElement.scrollWidth, clientW: document.documentElement.clientWidth }); })()`;

async function ev(cdp, expr, timeoutMs = 30000) {
  const r = await cdp.send("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: false }, timeoutMs);
  return r.result?.value;
}

/**
 * ★ここは一度つまずいた所なので、理由を残す（2026-09-23 実測）
 *   最初 `readyState === 'complete'` になるまで待つ形にしたら **45秒待っても complete にならなかった。**
 *   犯人はトップの繰り返し動画 joy-relief-footer-loop.mp4（206で流れ続ける）。
 *   ＝「complete を待つ」形だと、測るたびに45秒持っていかれて20回も回せない。
 *   なので **「文字が出て触れるようになった(interactive)まで」を待ち時間として測り、
 *   complete が来たかどうかは別の数字として残す。** どちらも消さない。
 */
async function gotoAndWait(cdp, url, maxMs = 20000) {
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: WATCHER }).catch(() => {});
  const t0 = Date.now();
  let loadFired = 0;
  cdp.on("Page.loadEventFired", () => { loadFired = Date.now() - t0; });
  await cdp.send("Page.navigate", { url });
  let interactiveMs = null;
  while (Date.now() - t0 < maxMs) {
    await sleep(200);
    try {
      const st = await ev(cdp, "document.readyState", 8000);
      if ((st === "interactive" || st === "complete") && interactiveMs === null) interactiveMs = Date.now() - t0;
      if (st === "complete") break;
    } catch { /* ナビゲーション中 */ }
  }
  let st = null;
  try { st = await ev(cdp, "document.readyState", 8000); } catch { /* 無視 */ }
  return { loaded: st === "complete", readyState: st, interactiveMs,
           loadEventMs: loadFired || null, ms: Date.now() - t0 };
}

// ---------- 1枚ぶんの測定 ----------
/** ★固まっても測定ごと死なないようにする包み。固まったこと自体が測りたい数字なので、握りつぶさず記録する。 */
async function guard(out, label, fn, dflt = null) {
  try { return await fn(); }
  catch (e) {
    const msg = String(e?.message || e);
    (out.tsumazuki = out.tsumazuki || []).push({ label, why: msg.slice(0, 180), frozen: msg.startsWith("FROZEN") });
    return dflt;
  }
}

async function measureWidth(width) {
  const mobile = width < 700;
  const height = mobile ? 812 : 900;
  return await withChrome(width, height, mobile, async (cdp) => {
    const out = { width, mobile };
    const net = attachNetwork(cdp);
    const consoleErrs = [];
    cdp.on("Runtime.exceptionThrown", (p) => consoleErrs.push(String(p?.exceptionDetails?.text || "").slice(0, 200)));
    cdp.on("Log.entryAdded", (p) => { if (p?.entry?.level === "error") consoleErrs.push(String(p.entry.text || "").slice(0, 200)); });
    let crashed = false;
    cdp.on("Inspector.targetCrashed", () => { crashed = true; });

    // ---- ① 何バイト送ってくるか ----
    const nav = await guard(out, "読み込み",
      () => gotoAndWait(cdp, URL_ARG, PHASE === "bytes" ? 12000 : 20000), { ms: null, loaded: false });
    await sleep(PHASE === "bytes" ? 1500 : SETTLE);
    out.loadMs = nav.ms;
    out.loaded = nav.loaded;
    out.nav = nav;

    // 画面に見えていない後追いの読み込みも拾うため、もうひと呼吸待つ
    await sleep(PHASE === "bytes" ? 800 : 1200);
    const rows = net.filter((r) => r.bytes > 0);
    const byKind = {};
    for (const r of rows) { const k = KIND(r); byKind[k] = (byKind[k] || 0) + r.bytes; }
    const total = rows.reduce((a, r) => a + r.bytes, 0);
    const top = [...rows].sort((a, b) => b.bytes - a.bytes).slice(0, 12)
      .map((r) => ({ name: shortName(r.url), kind: KIND(r), bytes: r.bytes, status: r.status }));
    // 展開後の大きさ（gzip前）も取れるだけ取る
    const decoded = await guard(out, "展開後の大きさ", () => ev(cdp, `(() => { try { return JSON.stringify(
        performance.getEntriesByType('resource').map(e=>({n:e.name,t:e.transferSize,d:e.decodedBodySize}))
          .filter(x=>x.d>0).sort((a,b)=>b.d-a.d).slice(0,12)); } catch(e){ return '[]'; } })()`, 15000), "[]");
    out.bytes = { total, byKind, top, decodedTop: JSON.parse(decoded || "[]"), reqCount: rows.length };

    // ★90秒の打ち切りに収めるため、phase=bytes は「荷物の量」だけ測って帰る。
    //   （下見・棚編集のクリック・横はみ出しは別の便で測る）
    if (PHASE === "bytes") {
      const omB = JSON.parse(await guard(out, "横はみ出し", () => ev(cdp, READ_OM, 10000), "{}") || "{}");
      out.yoko = { scrollW: omB.scrollW ?? null, clientW: omB.clientW ?? null,
                   hamidashi: omB.scrollW && omB.clientW ? omB.scrollW > omB.clientW + 1 : null };
      out.heapMB = omB.heapMB ?? null;
      out.consoleErrors = [...new Set(consoleErrs)].slice(0, 8);
      out.crashedDuringLoad = crashed;
      return out;
    }

    // ---- 下見（押す物・貼る所） ----
    const found = JSON.parse(await guard(out, "下見", () => ev(cdp, FINDER(cfg.editText), 20000), "{}") || "{}");
    out.recon = found;
    if (RECON_ONLY) {
      out.consoleErrors = [...new Set(consoleErrs)].slice(0, 8);
      out.crashedDuringLoad = crashed;
      out.bodyPeek = await guard(out, "画面の中身", () => ev(cdp,
        `(document.body?document.body.innerText:'').slice(0,400)`, 15000), null);
      return out;
    }

    // ---- ② 棚編集を押してから動くまで ----
    out.edit = { found: !!found.editFound, label: found.editText || null };
    if (found.editFound) {
      const boxRaw = await guard(out, "押す物の位置", () => ev(cdp, BOX("[data-omosa-edit]"), 20000), "0");
      if (boxRaw && boxRaw !== "0") {
        const b = JSON.parse(boxRaw);
        await sleep(200);
        await guard(out, "見張りの仕切り直し", () => ev(cdp, RESET_WATCHER, 20000));
        const t0 = Date.now();
        await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: b.x, y: b.y, button: "left", clickCount: 1 });
        await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: b.x, y: b.y, button: "left", clickCount: 1 });
        let frozen = false;
        await sleep(3500);
        let om = null;
        try { om = JSON.parse(await ev(cdp, READ_OM, FREEZE_LIMIT) || "{}"); }
        catch (e) { frozen = String(e.message).startsWith("FROZEN"); }
        out.edit = {
          ...out.edit, wallMs: Date.now() - t0, frozen,
          firstChangeMs: om?.first ?? null, settledMs: om?.settled ?? null,
          changes: om?.count ?? null, maxFreezeMs: om?.maxGap ?? null, heapMB: om?.heapMB ?? null,
        };
      }
    }

    // ---- ④ 横に流れていないか（375pxのとき効く） ----
    const om2 = JSON.parse(await guard(out, "横はみ出し", () => ev(cdp, READ_OM, 20000), "{}") || "{}");
    out.yoko = { scrollW: om2.scrollW ?? null, clientW: om2.clientW ?? null,
                 hamidashi: om2.scrollW && om2.clientW ? om2.scrollW > om2.clientW + 1 : null };
    out.heapMB = om2.heapMB ?? null;
    out.consoleErrors = [...new Set(consoleErrs)].slice(0, 8);
    out.crashedDuringLoad = crashed;
    return out;
  });
}

// ---------- ② 棚編集：開いてから触れるようになるまで何秒か ----------
/**
 * ★なぜ「ボタンを押してから」ではなく「開いてから」なのか（2026-09-23 実測でそうなった）
 *   棚編集は /admin/shelves という1枚の画面。押すボタンではなかった。
 *   鍵なしで開いても画面は出る（ログイン壁は無い）。ただし中身が「読み込み中…」のまま来ない。
 *   ＝ たまごさんの「棚編集が重い」は、押した後の反応ではなく **開いた後ずっと待たされること。**
 *   だから「読み込み中…が消えるまで何秒か」を数字にする。消えなければ「◯秒でも消えない」と書く。
 */
async function measureEdit(width) {
  const mobile = width < 700;
  const height = mobile ? 812 : 900;
  const EDIT_URL = cfg.editUrl;
  const LOADING = cfg.editLoadingText || "読み込み中";
  const WAIT = cfg.editWaitMs || 90000;
  if (!EDIT_URL) return { skipped: "設定に editUrl がありません" };
  return await withChrome(width, height, mobile, async (cdp) => {
    const out = { width, url: EDIT_URL };
    const net = attachNetwork(cdp);
    const errs = [];
    cdp.on("Runtime.exceptionThrown", (p) => errs.push(String(p?.exceptionDetails?.text || "").slice(0, 200)));
    cdp.on("Log.entryAdded", (p) => { if (p?.entry?.level === "error") errs.push(String(p.entry.text || "").slice(0, 200)); });
    let crashed = false;
    cdp.on("Inspector.targetCrashed", () => { crashed = true; });

    const nav = await guard(out, "棚編集を開く", () => gotoAndWait(cdp, EDIT_URL), { ms: null });
    out.nav = nav;
    const t0 = Date.now();
    let readyMs = null;
    while (Date.now() - t0 < WAIT) {
      const st = await guard(out, "読み込み中の見張り", () => ev(cdp,
        `(() => { const t=document.body?document.body.innerText:''; return JSON.stringify({
           loading: t.includes(${JSON.stringify(LOADING)}),
           len: t.length,
           inputs: document.querySelectorAll('input,textarea,select').length }); })()`, 12000), null);
      if (st) {
        const s = JSON.parse(st);
        out.lastPeek = s;
        if (!s.loading) { readyMs = Date.now() - t0; break; }
      }
      await sleep(1000);
    }
    out.readyMs = readyMs;
    out.gaveUpAfterMs = readyMs === null ? WAIT : null;
    out.stillLoading = readyMs === null;
    const rows = net.filter((r) => r.bytes > 0);
    out.bytes = { total: rows.reduce((a, r) => a + r.bytes, 0), reqCount: rows.length,
      top: [...rows].sort((a, b) => b.bytes - a.bytes).slice(0, 6)
        .map((r) => ({ name: shortName(r.url), kind: KIND(r), bytes: r.bytes, status: r.status })) };
    const om = await guard(out, "画面の様子", () => ev(cdp, READ_OM, 12000), null);
    if (om) { const o = JSON.parse(om); out.maxFreezeMs = o.maxGap; out.heapMB = o.heapMB;
      out.yoko = { scrollW: o.scrollW, clientW: o.clientW, hamidashi: o.scrollW > o.clientW + 1 }; }
    // 失敗している通信（棚編集が待っている相手）を名指しする
    out.failedReq = net.filter((r) => r.status >= 400).slice(0, 6).map((r) => ({ name: shortName(r.url), status: r.status }));
    out.consoleErrors = [...new Set(errs)].slice(0, 8);
    out.crashed = crashed;
    return out;
  });
}

// ---------- ③-b URLを開いて落ちる回数（1回ぶん） ----------
/**
 * ★たまごさんの「URL貼っても落ちる」は2通りに読める。両方とも測る（決めつけない）。
 *   (あ) 棚編集の中の入力欄にYouTubeのURLを貼る … pasteOnce()
 *   (い) 曲ページのURLをブラウザに貼って開く   … これ。openOnce()
 *   「毎回じゃないけど落ちる」＝回数で出さないと意味がないので、runs回まわして数える。
 * 落ちた＝描画係が死んだ／◯秒返事をしない／中身が空のまま／画面が3秒以上止まった、のどれか。
 */
async function openOnce(width, n, pageUrl) {
  const mobile = width < 700;
  const height = mobile ? 812 : 900;
  const r = { n, width, url: pageUrl, ochita: false, why: null, errs: [], ms: 0, maxFreezeMs: null, heapMB: null };
  const t0 = Date.now();
  try {
    await withChrome(width, height, mobile, async (cdp) => {
      const errs = [];
      cdp.on("Runtime.exceptionThrown", (p) => errs.push(String(p?.exceptionDetails?.text || "").slice(0, 160)));
      cdp.on("Log.entryAdded", (p) => { if (p?.entry?.level === "error") errs.push(String(p.entry.text || "").slice(0, 160)); });
      let crashed = false;
      cdp.on("Inspector.targetCrashed", () => { crashed = true; });
      await gotoAndWait(cdp, pageUrl, 12000);
      await sleep(1500);
      let om = null;
      try { om = JSON.parse(await ev(cdp, READ_OM, FREEZE_LIMIT) || "{}"); }
      catch (e) {
        r.ochita = true;
        r.why = String(e.message).startsWith("FROZEN")
          ? `画面が${FREEZE_LIMIT}ms返事をしない` : "描画係との線が切れた";
      }
      if (crashed) { r.ochita = true; r.why = "描画係が落ちた(targetCrashed)"; }
      if (!r.ochita && om) {
        r.maxFreezeMs = om.maxGap ?? null;
        r.heapMB = om.heapMB ?? null;
        r.bodyLen = om.bodyLen ?? null;
        if ((om.bodyLen || 0) < 30) { r.ochita = true; r.why = "画面の中身が出てこない(真っ白)"; }
        else if ((om.maxGap || 0) > 3000) { r.ochita = true; r.why = `画面が${Math.round(om.maxGap)}ms止まった`; }
      }
      r.errs = [...new Set(errs)].slice(0, 4);
    });
  } catch (e) {
    const msg = String(e.message || e);
    // ★ここを分けないと嘘になる（2026-09-23 実測でやらかしかけた）
    //   「Chromeのデバッグ口が開きませんでした」は**こちらの測定装置が起動に失敗した**だけで、
    //   ごきげん補給所が落ちたのではない。これを「落ちた」に数えると、
    //   **サイトのせいではない回数を混ぜた落ち率**という新しい嘘が出来る。
    //   測定失敗は測定失敗として別に数え、分母からも外す。
    if (MEASURE_FAIL.test(msg)) { r.sokuteiShippai = true; r.why = `測定装置の失敗: ${msg.slice(0, 120)}`; }
    else if (msg.startsWith("FROZEN")) { r.ochita = true; r.why = "画面が固まって返事をしない"; }
    else { r.ochita = true; r.why = `例外: ${msg.slice(0, 120)}`; }
  }
  r.ms = Date.now() - t0;
  return r;
}

// ---------- ③ URLを貼って落ちる回数（1回ぶん） ----------
async function pasteOnce(width, n, pageUrl = URL_ARG, waitReadyMs = 0) {
  const mobile = width < 700;
  const height = mobile ? 812 : 900;
  const r = { n, width, url: pageUrl, ochita: false, why: null, errs: [], ms: 0, maxFreezeMs: null, heapMB: null };
  const t0 = Date.now();
  try {
    await withChrome(width, height, mobile, async (cdp) => {
      const errs = [];
      cdp.on("Runtime.exceptionThrown", (p) => errs.push(String(p?.exceptionDetails?.text || "").slice(0, 160)));
      cdp.on("Log.entryAdded", (p) => { if (p?.entry?.level === "error") errs.push(String(p.entry.text || "").slice(0, 160)); });
      let crashed = false;
      cdp.on("Inspector.targetCrashed", () => { crashed = true; });

      await gotoAndWait(cdp, pageUrl);
      await sleep(SETTLE);
      // 棚編集の画面のときは「読み込み中…」が消えるまで待ってから貼る
      if (waitReadyMs > 0) {
        const t1 = Date.now();
        while (Date.now() - t1 < waitReadyMs) {
          const t = await ev(cdp, `(document.body?document.body.innerText:'')`, 12000).catch(() => "");
          if (t && !t.includes(cfg.editLoadingText || "読み込み中")) break;
          await sleep(1000);
        }
        r.waitedMs = Date.now() - t1;
      }

      const found = JSON.parse(await ev(cdp, FINDER(cfg.editText)) || "{}");
      // 棚編集があるなら開いてから貼る（貼り先はたいてい編集の中にある）
      if (found.editFound) {
        const boxRaw = await ev(cdp, BOX("[data-omosa-edit]"));
        if (boxRaw && boxRaw !== "0") {
          const b = JSON.parse(boxRaw);
          await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: b.x, y: b.y, button: "left", clickCount: 1 });
          await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: b.x, y: b.y, button: "left", clickCount: 1 });
          await sleep(1200);
          await ev(cdp, FINDER(cfg.editText)); // 開いた後の画面で貼り先を探し直す
        }
      }
      const hasPaste = await ev(cdp, `!!document.querySelector('[data-omosa-paste]')`);
      if (!hasPaste) { r.why = "貼る所が見つからない"; r.skipped = true; return; }

      const boxRaw2 = await ev(cdp, BOX("[data-omosa-paste]"));
      if (!boxRaw2 || boxRaw2 === "0") { r.why = "貼る所が見つからない"; r.skipped = true; return; }
      const pb = JSON.parse(boxRaw2);
      await cdp.send("Input.dispatchMouseEvent", { type: "mousePressed", x: pb.x, y: pb.y, button: "left", clickCount: 1 });
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseReleased", x: pb.x, y: pb.y, button: "left", clickCount: 1 });
      await ev(cdp, RESET_WATCHER);

      // 「貼る」を人と同じ形で起こす：本物のpasteイベント＋文字入力
      await ev(cdp, `(() => { const el=document.querySelector('[data-omosa-paste]'); if(!el) return 0;
        el.focus();
        try { const dt=new DataTransfer(); dt.setData('text/plain', ${JSON.stringify(cfg.pasteUrl)});
          el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true})); } catch(e){}
        return 1; })()`);
      await cdp.send("Input.insertText", { text: cfg.pasteUrl });
      await ev(cdp, `(() => { const el=document.querySelector('[data-omosa-paste]'); if(!el) return 0;
        el.dispatchEvent(new Event('input',{bubbles:true}));
        el.dispatchEvent(new Event('change',{bubbles:true}));
        return 1; })()`).catch(() => {});

      // 貼った後、しばらく様子を見る（ここで固まる／消えるのを捕まえる）
      await sleep(4000);
      let om = null;
      try { om = JSON.parse(await ev(cdp, READ_OM, FREEZE_LIMIT) || "{}"); }
      catch (e) {
        if (String(e.message).startsWith("FROZEN")) { r.ochita = true; r.why = `画面が${FREEZE_LIMIT}ms固まって返事をしない`; }
        else { r.ochita = true; r.why = "描画係との線が切れた"; }
      }
      if (crashed) { r.ochita = true; r.why = "描画係が落ちた(targetCrashed)"; }
      if (!r.ochita && om) {
        r.maxFreezeMs = om.maxGap ?? null;
        r.heapMB = om.heapMB ?? null;
        if ((om.bodyLen || 0) < 30) { r.ochita = true; r.why = "画面の中身が消えた(真っ白)"; }
        else if ((om.maxGap || 0) > 3000) { r.ochita = true; r.why = `画面が${Math.round(om.maxGap)}ms止まった`; }
      }
      r.errs = [...new Set(errs)].slice(0, 4);
    });
  } catch (e) {
    const msg = String(e.message || e);
    if (MEASURE_FAIL.test(msg)) { r.sokuteiShippai = true; r.why = `測定装置の失敗: ${msg.slice(0, 120)}`; }
    else if (msg.startsWith("FROZEN")) { r.ochita = true; r.why = "画面が固まって返事をしない"; }
    else { r.ochita = true; r.why = `例外: ${msg.slice(0, 120)}`; }
  }
  r.ms = Date.now() - t0;
  return r;
}

// ---------- 本体 ----------
/**
 * ★自分が前に起動した headless Chrome の生き残りを片付ける。
 *   実測（2026-09-23）：打ち切られた測定が Chrome を残し、次の測定が
 *   「Chromeのデバッグ口が開きませんでした」で全滅した。
 *   ★殺すのは **--user-data-dir に omosa- を含むものだけ**＝この道具が作った一時プロファイル。
 *     たまごさんが普段使っている Chrome には絶対に触らない。
 */
function souji() {
  try {
    const out = execFileSync("/usr/bin/pgrep", ["-f", "user-data-dir=.*omosa-"], { encoding: "utf-8" });
    const pids = out.split("\n").map((x) => x.trim()).filter(Boolean);
    for (const pid of pids) { try { process.kill(Number(pid), "SIGKILL"); } catch { /* 既に居ない */ } }
    if (pids.length) process.stderr.write(`[omosa] 前回の生き残りChromeを${pids.length}個片付けました\n`);
    return pids.length;
  } catch { return 0; }
}

async function main() {
  const started = new Date();
  souji();
  const result = {
    measuredAt: started.toISOString().replace("T", " ").slice(0, 19),
    url: URL_ARG, runs: RUNS, widths: WIDTHS, reconOnly: RECON_ONLY, byWidth: {},
  };
  for (const w of WIDTHS) {
    process.stderr.write(`[omosa] ${w}px を測っています… (phase=${PHASE})\n`);
    let m;
    try { m = (PHASE === "all" || PHASE === "bytes" || RECON_ONLY) ? await measureWidth(w) : { width: w }; }
    catch (e) { m = { width: w, sokutei_shippai: String(e?.message || e).slice(0, 300) }; }
    if (!RECON_ONLY && (PHASE === "all" || PHASE === "edit")) {
      // ② 棚編集：開いてから触れるまで
      process.stderr.write(`[omosa] ${w}px 棚編集を開いています…\n`);
      try { m.tanaHenshu = await measureEdit(w); }
      catch (e) { m.tanaHenshu = { error: String(e?.message || e).slice(0, 300) }; }
    }
    if (!RECON_ONLY && (PHASE === "all" || PHASE === "paste")) {

      // ③ URLを貼って落ちる回数。まず棚編集の画面で。貼る所が出てこなければトップで。
      const runPaste = async (pageUrl, waitMs, basho) => {
        const trials = [];
        for (let i = 1; i <= RUNS; i++) {
          const one = await pasteOnce(w, i, pageUrl, waitMs);
          trials.push(one);
          process.stderr.write(`[omosa] ${w}px 貼り ${i}/${RUNS} (${basho}) … ${one.skipped ? "貼る所なし" : one.ochita ? "落ちた(" + one.why + ")" : "無事"}\n`);
          if (one.skipped && i >= 2) break; // 貼る所が無いのに20回やっても意味がない
        }
        const done = trials.filter((t) => !t.skipped && !t.sokuteiShippai);
        const ko = done.filter((t) => t.ochita);
        return {
          basho, url: pageUrl, tried: done.length, ochita: ko.length,
          skipped: trials.length - done.length,
          skipWhy: trials.find((t) => t.skipped)?.why || null,
          rate: done.length ? Math.round((ko.length / done.length) * 1000) / 10 : null,
          whys: [...new Set(ko.map((t) => t.why))],
          errs: [...new Set(done.flatMap((t) => t.errs))].slice(0, 6),
          maxFreezeMs: done.map((t) => t.maxFreezeMs).filter((x) => x != null).sort((a, b) => b - a)[0] ?? null,
          heapMB: done.map((t) => t.heapMB).filter((x) => x != null).sort((a, b) => b - a)[0] ?? null,
          trials: done.map((t) => ({ n: t.n, ochita: t.ochita, why: t.why, ms: t.ms })),
        };
      };
      m.paste = await runPaste(cfg.editUrl || URL_ARG, 20000, "棚編集の画面のURL入力欄");
    }
    if (!RECON_ONLY && (PHASE === "all" || PHASE === "open")) {
      // ③-b URLを開いて落ちるか。こちらは鍵なしでも runs 回まわせる。
      const opens = [];
      const list = cfg.openUrls && cfg.openUrls.length ? cfg.openUrls : [URL_ARG];
      for (let i = 1; i <= RUNS; i++) {
        const u = list[(i - 1) % list.length];
        const one = await openOnce(w, i, u);
        opens.push(one);
        process.stderr.write(`[omosa] ${w}px 開き ${i}/${RUNS} … ${one.ochita ? "落ちた(" + one.why + ")" : "無事"}\n`);
      }
      // ★測定装置がコケた回は分母から外す（サイトのせいではないので）
      const valid = opens.filter((t) => !t.sokuteiShippai);
      const ko2 = valid.filter((t) => t.ochita);
      m.open = {
        tried: valid.length, ochita: ko2.length, sokuteiShippai: opens.length - valid.length,
        rate: valid.length ? Math.round((ko2.length / valid.length) * 1000) / 10 : null,
        whys: [...new Set(ko2.map((t) => t.why))],
        errs: [...new Set(valid.flatMap((t) => t.errs))].slice(0, 6),
        maxFreezeMs: valid.map((t) => t.maxFreezeMs).filter((x) => x != null).sort((a, b) => b - a)[0] ?? null,
        heapMB: valid.map((t) => t.heapMB).filter((x) => x != null).sort((a, b) => b - a)[0] ?? null,
        msAvg: Math.round(valid.reduce((a, t) => a + t.ms, 0) / (valid.length || 1)),
        trials: opens.map((t) => ({ n: t.n, url: shortName(t.url), ochita: !!t.ochita,
          sokuteiShippai: !!t.sokuteiShippai, why: t.why, ms: t.ms })),
      };
    }
    result.byWidth[String(w)] = m;
  }
  result.elapsedSec = Math.round((Date.now() - started.getTime()) / 1000);
  mkdirSync(dirname(OUT_LAST), { recursive: true });
  // ★小分けにしたので、前の phase が入れた数字を消さないように足し込む。
  let merged = result;
  if (PHASE !== "all" && existsSync(OUT_LAST)) {
    try {
      const old = JSON.parse(readFileSync(OUT_LAST, "utf-8"));
      if (old.url === result.url) {
        merged = { ...old, ...result, byWidth: { ...(old.byWidth || {}) } };
        for (const k of Object.keys(result.byWidth || {})) {
          merged.byWidth[k] = { ...(old.byWidth?.[k] || {}), ...result.byWidth[k] };
        }
        merged.phases = [...new Set([...(old.phases || []), PHASE])];
      }
    } catch { /* 読めなければそのまま上書き */ }
  } else if (PHASE !== "all") { merged.phases = [PHASE]; }
  writeFileSync(OUT_LAST, JSON.stringify(merged, null, 1));
  // ★下見(--recon)は履歴に足さない。足すと「前回より重い／軽い」の比べる相手が
  //   別のページになって、嘘の赤・嘘の緑が出る（2026-09-23に実際そうなりかけた）。
  if (!RECON_ONLY) appendFileSync(OUT_LOG, JSON.stringify(result) + "\n");
  process.stdout.write(JSON.stringify(result, null, 1));
}

main().catch((e) => {
  const bad = { error: String(e?.stack || e).slice(0, 1500), measuredAt: new Date().toISOString() };
  process.stdout.write(JSON.stringify(bad, null, 1));
  process.exitCode = 1;
});
