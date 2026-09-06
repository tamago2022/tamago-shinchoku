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
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
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

const PERF_JS = `(() => {
  const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
  const last = lcpEntries.length ? lcpEntries[lcpEntries.length - 1] : null;
  const lcp = last ? Math.round(last.renderTime || last.loadTime) : null;
  const paintEntries = performance.getEntriesByType('paint');
  const fcpEntry = paintEntries.find((e) => e.name === 'first-contentful-paint');
  const fcp = fcpEntry ? Math.round(fcpEntry.startTime) : null;
  return { lcp, fcp };
})()`;

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
    const wsUrl = await findWs(port);
    let loadFired = false;
    const { ready, send, close } = connect(wsUrl, (msg) => {
      if (msg.method === "Page.loadEventFired") loadFired = true;
    });
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");

    const results = [];
    for (const page of pages) {
      loadFired = false;
      await send("Page.navigate", { url: page.url });
      const start = Date.now();
      while (!loadFired && Date.now() - start < LOAD_TIMEOUT_MS) {
        await sleep(300);
      }
      // load完了後もLCPが確定するまで待つ（固定待ちではなく、LCPが出るたびに早期終了するポーリング方式）。
      // 2026-09-06実測：Mac側の同時実行数が多い時間帯はCPUが取り合いになり、
      // loadイベント後20秒待ってもpaintエントリが0件のままのケースを確認した
      // （headless Chrome起動自体は成功・visibilityState='visible'も確認済みで、
      //   純粋にレンダリングへCPU時間が回ってきていないだけ）。そのため最大待ち時間を伸ばし、
      // 出た時点ですぐ評価へ進めるポーリングに変更。
      const settleStart = Date.now();
      let lcpReady = false;
      while (!lcpReady && Date.now() - settleStart < POST_LOAD_MAX_WAIT_MS) {
        await sleep(1000);
        const probe = await send("Runtime.evaluate", {
          expression: "performance.getEntriesByType('largest-contentful-paint').length > 0",
          returnByValue: true,
        });
        if (probe?.result?.value) lcpReady = true;
      }
      const evalResult = await send("Runtime.evaluate", { expression: PERF_JS, returnByValue: true });
      const value = evalResult?.result?.value ?? {};
      results.push({ key: page.key, url: page.url, lcp_ms: value.lcp ?? null, fcp_ms: value.fcp ?? null });
      console.log(`[perf_watch] ${page.key}: LCP=${value.lcp}ms FCP=${value.fcp}ms`);
    }
    close();
    return results;
  } finally {
    chrome.kill("SIGKILL");
    rmSync(profile, { recursive: true, force: true });
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
  return { written };
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
if (isMain) {
  main().catch((e) => {
    console.error("[perf_watch] ERROR", e);
    process.exit(1);
  });
}
