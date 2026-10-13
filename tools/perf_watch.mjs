#!/usr/bin/env node
/**
 * 案件429番：「ごきげん補給所」が重くなったことに、店主より先に気づく見張り。
 *
 * 本番3ページ（トップ／世界の音楽／カバーガイド）をヘッドレスChromeで毎晩1回開き、
 * LCP（最大コンテンツの描画完了時間）とFCP（最初の描画時間）を実測して
 * status/perf_history.jsonl に積み上げる。前回（本日より前）の記録よりLCPが
 * 10%以上悪化していたら status/dispatch_outbox.jsonl へ通知を1行書く。
 *
 * 安全性最優先：
 *   - 画面には何も表示されない（--headless=new）
 *   - 音は絶対に鳴らさない（--mute-audio）
 *   - 使い終わったChromeプロセスと一時プロファイルは必ず消す（try/finally）
 * 参考にした既存の実績パターン：
 *   /Users/mac/Desktop/joy-relief-station/scripts/patrol/measure-admin-panel-open.mjs
 *   （ヘッドレスChrome起動→CDP接続→計測→必ずkill、の流れをそのまま踏襲）
 *
 * 使い方：
 *   node tools/perf_watch.mjs            # 通常実行（本日分が既にあればスキップ）
 *   node tools/perf_watch.mjs --force    # 本日分が既にあっても強制的に追加計測
 *   node tools/perf_watch.mjs --dry-run  # ファイルへは一切書き込まず、結果と判定だけ表示
 *
 * 冪等性の注意（status/failures.md の教訓を踏まえた設計）：
 *   「処理済み」判定は、切り詰めた末尾配列などではなく status/perf_history.jsonl の
 *   全件を毎回読み直して判定する（配列を`[-N:]`等で削ると古い判定が消えて
 *   同じ処理が繰り返される事故が過去にあったため、このファイルは切り詰めない）。
 *
 * 【2026-09-06 実測で判明した重大な不具合と修正】
 * 当初は `PerformanceObserver({type:'largest-contentful-paint', buffered:true})` を
 * JS側に仕込んで window.__lcp を読む方式で実装していたが、実機検証で
 * `performance.getEntriesByType('largest-contentful-paint')` が常に空配列になり、
 * lcp_ms が毎回 null になる不具合を発見した（FCPは同じ条件で正しく取れていた）。
 * 原因の切り分け：JS Performance APIのLCPエントリそのものがヘッドレスChromeの
 * このセッションでは一度も生成されていなかった（observerの実装ミスではなかった）。
 * 対策として、Lighthouse自身と同じ「Tracingドメインでブラウザ内部のトレースイベントを
 * 直接読む」方式に切り替えた（`largestContentfulPaint::Candidate` トレースイベントを
 * `NavigationTiming navigationStart` からの相対時間で計算）。実機で1回、実際に
 * LCP値の取得に成功したことを確認済み（1回目は失敗、2回目に成功＝Mac高負荷時は
 * トレースイベントの発火自体が遅れて計測ウィンドウ内に収まらないことがあるため、
 * 1ページにつき最大2回まで計測を試みるリトライを入れてある）。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, existsSync, readFileSync, appendFileSync } from "node:fs";
import os from "node:os";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");

// テスト時だけ環境変数で書き込み先を切り替えられるようにする（本物のstatus/を汚さずに逆テストするため）。
const HISTORY_PATH = process.env.PERF_WATCH_HISTORY_FILE || join(REPO_ROOT, "status/perf_history.jsonl");
const OUTBOX_PATH = process.env.PERF_WATCH_OUTBOX_FILE || join(REPO_ROOT, "status/dispatch_outbox.jsonl");
const SKIP_LOG_PATH = process.env.PERF_WATCH_SKIP_LOG_FILE || join(REPO_ROOT, "status/perf_watch_skip.log");

export const PAGES = [
  { key: "home", url: "https://joy-relief-station.lovable.app/" },
  { key: "world_music", url: "https://joy-relief-station.lovable.app/world/music" },
  { key: "cover_guide", url: "https://joy-relief-station.lovable.app/cover-guide" },
];

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const LOAD_TIMEOUT_MS = 9000;
const POST_LOAD_MAX_WAIT_MS = 25000; // Mac混雑時にLCPがなかなか確定しない実測を踏まえた上限
const LOADAVG_SKIP_THRESHOLD = 8;
const REGRESSION_THRESHOLD = 0.1; // 10%

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- JST日時ヘルパー ---------------------------------------------------

export function nowJst() {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  const y = jst.getUTCFullYear();
  const mo = pad(jst.getUTCMonth() + 1);
  const d = pad(jst.getUTCDate());
  const h = pad(jst.getUTCHours());
  const mi = pad(jst.getUTCMinutes());
  const s = pad(jst.getUTCSeconds());
  return { iso: `${y}-${mo}-${d}T${h}:${mi}:${s}+09:00`, date: `${y}-${mo}-${d}` };
}

// --- 記録ファイルの読み書き ----------------------------------------------

export function readHistory(path = HISTORY_PATH) {
  if (!existsSync(path)) return [];
  const text = readFileSync(path, "utf8");
  const records = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      records.push(JSON.parse(trimmed));
    } catch {
      // 壊れた行は無視して先へ進む（既存ログでも同様の防御をしている）
    }
  }
  return records;
}

export function appendHistory(record, path = HISTORY_PATH) {
  appendFileSync(path, `${JSON.stringify(record)}\n`);
}

export function appendOutbox(alert, path = OUTBOX_PATH) {
  appendFileSync(path, `${JSON.stringify(alert)}\n`);
}

export function isTodayFullyRecorded(records, today, pages = PAGES) {
  return pages.every((p) => records.some((r) => r.date === today && r.key === p.key));
}

// 「本日より前」の直近の記録を探す（--forceで同日中に複数回計測しても、
// 悪化判定は日をまたいだ比較として意味を保つため）。
export function findPrevRecord(records, key, today) {
  const candidates = records.filter(
    (r) => r.key === key && typeof r.date === "string" && r.date < today && typeof r.lcp_ms === "number",
  );
  if (candidates.length === 0) return null;
  candidates.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  return candidates[candidates.length - 1];
}

export function computeAlert({ key, url, prevLcpMs, newLcpMs }) {
  if (typeof prevLcpMs !== "number" || typeof newLcpMs !== "number" || prevLcpMs <= 0) return null;
  const ratio = (newLcpMs - prevLcpMs) / prevLcpMs;
  if (ratio < REGRESSION_THRESHOLD) return null;
  const pct = Math.round(ratio * 1000) / 10; // 小数1桁
  return {
    ts: nowJst().iso,
    n: 429,
    title: `軽さ見張り：LCP悪化を検知（${key}）`,
    ok: false,
    elapsedMin: 0,
    urls: [url],
    result: `【異常検知】${key}のLCPが前回${prevLcpMs}ms→今回${newLcpMs}ms（+${pct}%）に悪化。${url}`,
  };
}

// --- ヘッドレスChrome / CDP（measure-admin-panel-open.mjs の実績パターンを踏襲） ---

async function findWs(port) {
  // Mac負荷が高い夜はChrome自身の起動が遅れることがあるため、余裕を持って最大30秒待つ
  // （2026-09-06 実測：loadavg1=10台でヘッドレスChromeの起動デバッグ口が開くまで10秒超かかるケースを確認）。
  for (let i = 0; i < 120; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === "page");
      if (page?.webSocketDebuggerUrl) return page; // id と webSocketDebuggerUrl の両方を使う
    } catch {
      /* まだ起動中 */
    }
    await sleep(250);
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
      pending.get(msg.id)(msg.result ?? msg.error);
      pending.delete(msg.id);
    } else if (msg.method) onEvent(msg);
  });
  const ready = new Promise((res) => ws.addEventListener("open", res));
  const send = (method, params = {}) =>
    new Promise((res) => {
      const myId = ++id;
      pending.set(myId, res);
      ws.send(JSON.stringify({ id: myId, method, params }));
    });
  return { ready, send, close: () => ws.close() };
}

// Tracingドメインで拾うカテゴリ（Lighthouseが使う集合を踏襲。loadingカテゴリに
// firstContentfulPaint / largestContentfulPaint::Candidate / NavigationTiming navigationStart
// の各トレースイベントが乗る）。
const TRACE_CATEGORIES = "loading,rail,devtools.timeline,disabled-by-default-devtools.timeline";

// トレースイベント配列からFCP・LCPをミリ秒で算出する（navigationStartからの相対時間）。
// largestContentfulPaint::Candidate は描画のたびに複数回発火し、より大きい要素が
// 見つかるたびに上書きされる仕様のため、時刻順に並べて最後の1件を採用する。
export function parseTraceMetrics(events) {
  const navStart = events.find((e) => e.name === "NavigationTiming navigationStart");
  const fcpEvent = events.find((e) => e.name === "firstContentfulPaint");
  const lcpEvents = events
    .filter((e) => e.name === "largestContentfulPaint::Candidate")
    .sort((a, b) => a.ts - b.ts);
  const lastLcp = lcpEvents[lcpEvents.length - 1];
  const lcp = navStart && lastLcp ? Math.round((lastLcp.ts - navStart.ts) / 1000) : null;
  const fcp = navStart && fcpEvent ? Math.round((fcpEvent.ts - navStart.ts) / 1000) : null;
  return { lcp, fcp };
}

async function measureAllPages(pages = PAGES) {
  const port = 9800 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "perf-watch-"));
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      "--window-size=390,844",
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  try {
    const target = await findWs(port);
    let loadFired = false;
    const trace = { events: [], complete: false };
    const { ready, send, close } = connect(target.webSocketDebuggerUrl, (msg) => {
      if (msg.method === "Page.loadEventFired") loadFired = true;
      else if (msg.method === "Tracing.dataCollected") trace.events.push(...(msg.params.value || []));
      else if (msg.method === "Tracing.tracingComplete") trace.complete = true;
    });
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    // headless=newはタブが既定でhidden扱いのため、明示的にアクティブ化する。
    await send("Target.activateTarget", { targetId: target.id });

    async function measureOnce(url) {
      trace.events.length = 0;
      trace.complete = false;
      loadFired = false;
      await send("Tracing.start", { categories: TRACE_CATEGORIES, transferMode: "ReportEvents" });
      await send("Page.navigate", { url });
      const start = Date.now();
      while (!loadFired && Date.now() - start < LOAD_TIMEOUT_MS) {
        await sleep(300);
      }
      // load完了後もLCPが確定するまで一定時間待つ（Mac混雑時はレンダリングにCPU時間が
      // 回ってこず、load後もLCP候補の発火が遅れることを実測で確認済み）。
      await sleep(POST_LOAD_MAX_WAIT_MS);
      await send("Tracing.end");
      const endStart = Date.now();
      while (!trace.complete && Date.now() - endStart < 10000) {
        await sleep(200);
      }
      await sleep(300); // 最終dataCollectedメッセージの到着待ち
      return parseTraceMetrics(trace.events);
    }

    const results = [];
    for (const page of pages) {
      let metrics = await measureOnce(page.url);
      // 1回目でLCPが取れなかった場合のみ、もう一度だけ試す（Mac高負荷時のflaky対策）。
      if (metrics.lcp === null) {
        console.log(`[perf_watch] ${page.key}: 1回目でLCP未取得のため再計測します`);
        metrics = await measureOnce(page.url);
      }
      results.push({ key: page.key, url: page.url, lcp_ms: metrics.lcp, fcp_ms: metrics.fcp });
      console.log(`[perf_watch] ${page.key}: LCP=${metrics.lcp}ms FCP=${metrics.fcp}ms`);
    }
    close();
    return results;
  } finally {
    // 2026-09-06実測で判明：kill直後にrmSyncするとChromeが一時プロファイル内の
    // ロックファイルをまだ書いている途中でENOTEMPTYになることがある。
    // プロセスの実終了(exitイベントかタイムアウト)を待ってから消す。
    await new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        resolve();
      };
      chrome.once("exit", finish);
      chrome.kill("SIGKILL");
      setTimeout(finish, 3000);
    });
    rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

// --- メイン ---------------------------------------------------------------

export async function main(argv = process.argv.slice(2)) {
  const force = argv.includes("--force");
  const dryRun = argv.includes("--dry-run");

  const { date: today } = nowJst();
  const existing = readHistory();

  if (!force && isTodayFullyRecorded(existing, today)) {
    console.log(`[perf_watch] 本日(${today})分は既に3ページとも記録済みのためスキップします（--forceで強制実行可）`);
    return { skipped: "already_recorded" };
  }

  const load1 = os.loadavg()[0];
  // PERF_WATCH_IGNORE_LOAD=1 は「今すぐ手動で実測したい」時だけの検品用の逃げ道。
  // 深夜の自動実行(launchd)はこの環境変数を設定しないので、負荷が高い日は必ずスキップされる。
  if (load1 > LOADAVG_SKIP_THRESHOLD && process.env.PERF_WATCH_IGNORE_LOAD !== "1") {
    const line = `${nowJst().iso} loadavg1=${load1.toFixed(2)} のため今日は負荷が高いためスキップ\n`;
    if (!dryRun) appendFileSync(SKIP_LOG_PATH, line);
    console.log(`[perf_watch] Mac負荷が高い(loadavg1=${load1.toFixed(2)})ためスキップしました`);
    return { skipped: "high_load", loadavg1: load1 };
  }

  const results = await measureAllPages();
  const written = [];

  for (const r of results) {
    const record = { ts: nowJst().iso, date: today, key: r.key, url: r.url, lcp_ms: r.lcp_ms, fcp_ms: r.fcp_ms };
    const prev = findPrevRecord(existing, r.key, today);
    const alert = prev ? computeAlert({ key: r.key, url: r.url, prevLcpMs: prev.lcp_ms, newLcpMs: r.lcp_ms }) : null;

    if (dryRun) {
      console.log(`[dry-run] record=${JSON.stringify(record)}`);
      console.log(`[dry-run] prev=${prev ? JSON.stringify(prev) : "なし"} alert=${alert ? JSON.stringify(alert) : "なし"}`);
      written.push({ record, alert });
      continue;
    }

    appendHistory(record);
    existing.push(record);
    if (alert) {
      appendOutbox(alert);
      console.log(`[perf_watch] 悪化検知 → dispatch_outbox.jsonlへ追記: ${r.key}`);
    }
    written.push({ record, alert });
  }

  console.log(`[perf_watch] ${results.length}件のページを計測しました（${today}）${dryRun ? "（dry-run・未保存）" : ""}`);

  // 進捗表に貼る「直近7日の推移」画像を実測のたびに作り直す（④の要件）。
  // 失敗しても計測結果の保存自体は既に終わっているので、ここは握りつぶしてログだけ出す。
  if (!dryRun) {
    await new Promise((resolve) => {
      const chart = spawn("python3", [join(REPO_ROOT, "tools/perf_watch_chart.py")], { stdio: "inherit" });
      chart.on("exit", resolve);
      chart.on("error", (e) => {
        console.error("[perf_watch] グラフ生成に失敗（実測データ自体は保存済み）", e);
        resolve();
      });
    });
  }

  return { written };
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  main().catch((e) => {
    console.error("[perf_watch] ERROR", e);
    process.exit(1);
  });
}
