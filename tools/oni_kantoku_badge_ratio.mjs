#!/usr/bin/env node
/**
 * 鬼監督 関門①：バッジの比率を「自己申告」ではなく実測で自動判定する。
 *
 * 案件#606（2026-09-07）：たまごさんの言葉「鬼監督、自動で突き返さないと」を受けて、
 * 「作った本人が読んで自己採点するチェックリスト」だった鬼監督を、
 * 「本番のページを実際に開いて、数字で測って、外れていたら自動で落とす」機械へ変える。
 * 最初の1項目としてバッジ（コンシェルジュ推し／グッドカバー）の比率だけを対象にする。
 *
 * **なぜ「HTMLのCSSを読むだけ」ではダメか（実際にハマった罠）：**
 * 直前の案件#602は「本番JSバンドルに13.8という定数がある」ことを確認して
 * PASSとしていたが、それは「コードにそう書いてある」ことの確認に過ぎない。
 * 本番の実バンドルを読むと、バッジの高さは`13.8cqh`というCSSコンテナクエリ単位で
 * 指定されており、これは「祖先要素にcontainer-typeが設定されているか」に応じて
 * 挙動が変わりうる（container-typeが無ければブラウザは代替値へフォールバックする）。
 * コード上の数字が正しくても、実際のレンダリング結果が同じ比率になっている保証にはならない。
 * このスクリプトは、実際にヘッドレスChromeでページを開き、
 * `getBoundingClientRect()`で「本当にブラウザが描画した後のpx数」を測る。
 * これなら container-type の有無・CSS計算経路に関わらず、見た目の真実だけを見る。
 *
 * 使い方：
 *   node tools/oni_kantoku_badge_ratio.mjs                      # 既定の対象URL一式を検査
 *   node tools/oni_kantoku_badge_ratio.mjs <url> [<url> ...]    # 指定URLだけ検査
 *   node tools/oni_kantoku_badge_ratio.mjs --mobile              # スマホ幅(390x844)で検査
 *   node tools/oni_kantoku_badge_ratio.mjs --self-test           # 逆テスト（合格/不合格を両方作って確認）
 *
 * 判定基準：
 *   お手本＝akiko「Love Theme From "Spartacus"」の本番ページで実測した比率（2026-09-07実測：13.8%）。
 *   他ページのバッジ比率が「お手本 ± 2ポイント」を外れたら不合格。
 *   1ページに複数バッジがあれば、そのうち1つでも外れたら不合格。
 *   バッジが1つも無いページは「対象外（このページにはバッジが無い）」として合否をつけない
 *   （バッジの掲載可否は店主の判断領域であり、無いこと自体は鬼監督の仕事ではないため）。
 *
 * 終了コード：0=全ページ合格（対象外のみも含む）／1=1件以上不合格／2=実行時エラー。
 */
import { spawn } from "node:child_process";
import { mkdtempSync, rmSync, appendFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");

const LOG_PATH = process.env.ONI_KANTOKU_BADGE_LOG || join(REPO_ROOT, "status/oni_kantoku_log.jsonl");
const LATEST_PATH =
  process.env.ONI_KANTOKU_BADGE_LATEST || join(REPO_ROOT, "status/oni_kantoku_badge_ratio_latest.json");

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const REF_RATIO = 13.8; // お手本(akiko)の実測値。基準を変える時はREADMEコメントと一緒にここも更新する。
const TOLERANCE = 2; // ポイント（%）
const LOAD_TIMEOUT_MS = 20000;
const BADGE_WAIT_MS = 20000;
const SETTLE_MS = 900;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export const DEFAULT_TARGETS = [
  // お手本そのもの。ここが外れたら「お手本が壊れた」という最重大の不合格。
  "https://joy-relief-station.lovable.app/cover-guide?artist=akiko&song=love-theme-from-spartacus",
];

function nowJst() {
  const now = new Date();
  const jst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${jst.getUTCFullYear()}-${pad(jst.getUTCMonth() + 1)}-${pad(jst.getUTCDate())}T${pad(jst.getUTCHours())}:${pad(jst.getUTCMinutes())}:${pad(jst.getUTCSeconds())}+09:00`;
}

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

// ページ内で実行するJS。バッジ画像(/badges/配下)を全部拾い、
// offsetParent（position:absoluteの基準＝実サムネ枠）との比率を計算する。
const MEASURE_EXPR = `
JSON.stringify(Array.from(document.querySelectorAll('img[src*="/badges/"]')).map(function(b) {
  var r = b.getBoundingClientRect();
  var op = b.offsetParent;
  var cr = op ? op.getBoundingClientRect() : null;
  var shortSide = cr ? Math.min(cr.width, cr.height) : null;
  var ratio = (cr && shortSide) ? (r.height / shortSide * 100) : null;
  var corner = null;
  if (cr) {
    var nearTop = (r.top - cr.top) < cr.height * 0.25;
    var nearBottom = (cr.bottom - r.bottom) < cr.height * 0.25;
    var nearLeft = (r.left - cr.left) < cr.width * 0.25;
    var nearRight = (cr.right - r.right) < cr.width * 0.25;
    corner = (nearTop ? "top" : nearBottom ? "bottom" : "middle") + "-" + (nearLeft ? "left" : nearRight ? "right" : "middle");
  }
  return {
    src: b.src,
    badge_h: Math.round(r.height * 10) / 10,
    badge_w: Math.round(r.width * 10) / 10,
    container_w: cr ? Math.round(cr.width) : null,
    container_h: cr ? Math.round(cr.height) : null,
    shortSide: shortSide ? Math.round(shortSide) : null,
    ratioPercent: ratio !== null ? Math.round(ratio * 100) / 100 : null,
    corner: corner
  };
}))`;

/** 1つのChromeプロセスの中で複数URLを検査し、必ずkillしてから返す。 */
export async function measureUrls(urls, { mobile = false } = {}) {
  const port = 9700 + Math.floor(Math.random() * 200);
  const profile = mkdtempSync(join(tmpdir(), "oni-kantoku-badge-"));
  const windowSize = mobile ? "390,844" : "1280,900";
  const chrome = spawn(
    CHROME,
    [
      "--headless=new",
      `--remote-debugging-port=${port}`,
      `--user-data-dir=${profile}`,
      "--no-first-run",
      "--mute-audio",
      `--window-size=${windowSize}`,
      "--disable-features=Translate,MediaRouter",
      "about:blank",
    ],
    { stdio: "ignore" },
  );

  const outputs = [];
  try {
    const target = await findPage(port);
    const { ready, send, close } = connect(target.webSocketDebuggerUrl);
    await ready;
    await send("Page.enable");
    await send("Runtime.enable");
    await send("Target.activateTarget", { targetId: target.id });

    for (const url of urls) {
      try {
        await send("Page.navigate", { url });
        // readyState=complete を待つ（load完了）
        const start = Date.now();
        let complete = false;
        while (Date.now() - start < LOAD_TIMEOUT_MS) {
          await sleep(400);
          try {
            const r = await send("Runtime.evaluate", {
              expression: "document.readyState",
              returnByValue: true,
            });
            if (r.result?.value === "complete") {
              complete = true;
              break;
            }
          } catch {
            /* ナビゲーション中は評価に失敗することがある。無視して待つ */
          }
        }
        // バッジ画像が現れるまで追加で待つ（DBフェッチ後に描画されるため）
        const badgeStart = Date.now();
        let sawBadge = false;
        while (Date.now() - badgeStart < BADGE_WAIT_MS) {
          const r = await send("Runtime.evaluate", {
            expression: 'document.querySelectorAll(\'img[src*="/badges/"]\').length',
            returnByValue: true,
          });
          if ((r.result?.value ?? 0) > 0) {
            sawBadge = true;
            break;
          }
          await sleep(500);
        }
        await sleep(SETTLE_MS);
        const r = await send("Runtime.evaluate", { expression: MEASURE_EXPR, returnByValue: true });
        const badges = JSON.parse(r.result?.value ?? "[]");
        outputs.push({ url, complete, sawBadge, badges, error: null });
      } catch (e) {
        outputs.push({ url, complete: false, sawBadge: false, badges: [], error: e.message });
      }
    }
    close();
  } finally {
    chrome.kill("SIGKILL");
    try {
      rmSync(profile, { recursive: true, force: true });
    } catch {
      /* 消せなくても致命的ではない */
    }
  }
  return outputs;
}

/** 1ページ分の測定結果から合否を出す。 */
export function judgePage({ url, badges, error }) {
  if (error) return { url, verdict: "ERROR", reason: error, badges: [] };
  if (!badges || badges.length === 0) {
    return { url, verdict: "NO_BADGE", reason: "このページにはバッジ画像が無い（対象外・不合格ではない）", badges: [] };
  }
  const bad = badges.filter(
    (b) => b.ratioPercent === null || Math.abs(b.ratioPercent - REF_RATIO) > TOLERANCE,
  );
  if (bad.length > 0) {
    return {
      url,
      verdict: "FAIL",
      reason: `お手本${REF_RATIO}%±${TOLERANCE}を外れたバッジが${bad.length}/${badges.length}件（${bad
        .map((b) => `${b.ratioPercent}%`)
        .join(", ")}）`,
      badges,
    };
  }
  return {
    url,
    verdict: "PASS",
    reason: `全${badges.length}件が${REF_RATIO}%±${TOLERANCE}以内（実測: ${badges
      .map((b) => `${b.ratioPercent}%`)
      .join(", ")}）`,
    badges,
  };
}

export async function runCheck(urls, opts = {}) {
  const raw = await measureUrls(urls, opts);
  return raw.map(judgePage);
}

function appendLog(entries, task) {
  const ts = nowJst();
  const lines = entries.map((e) => ({ ts, task, url: e.url, verdict: e.verdict, reason: e.reason }));
  for (const line of lines) {
    appendFileSync(LOG_PATH, `${JSON.stringify(line)}\n`);
  }
}

function writeLatest(entries) {
  const dir = dirname(LATEST_PATH);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(
    LATEST_PATH,
    JSON.stringify({ checkedAt: nowJst(), refRatio: REF_RATIO, tolerance: TOLERANCE, results: entries }, null, 2) +
      "\n",
  );
}

async function selfTest() {
  // 逆テスト：合格するはず(お手本そのもの)と、意図的に壊した比率(わざと5%)の
  // 両方を判定関数へ通し、緑・赤が正しく出ることを確認する。コードだけを見て
  // 「多分いける」で済ませない、というこのスクリプト自身の原則を自分にも適用する。
  const good = judgePage({ url: "TEST_GOOD", badges: [{ ratioPercent: 13.9 }, { ratioPercent: 12.1 }] });
  const bad = judgePage({ url: "TEST_BAD_TOO_SMALL", badges: [{ ratioPercent: 5.0 }] });
  const bad2 = judgePage({ url: "TEST_BAD_TOO_BIG", badges: [{ ratioPercent: 35.0 }] });
  const none = judgePage({ url: "TEST_NO_BADGE", badges: [] });
  const results = [good, bad, bad2, none];
  console.log(JSON.stringify(results, null, 2));
  const ok =
    good.verdict === "PASS" && bad.verdict === "FAIL" && bad2.verdict === "FAIL" && none.verdict === "NO_BADGE";
  console.log(ok ? "\n逆テスト: OK（合格/不合格/対象外が正しく分かれた）" : "\n逆テスト: NG（判定ロジックが壊れている）");
  process.exit(ok ? 0 : 2);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--self-test")) {
    await selfTest();
    return;
  }
  const mobile = args.includes("--mobile");
  const urls = args.filter((a) => a.startsWith("http"));
  const targets = urls.length > 0 ? urls : DEFAULT_TARGETS;

  console.log(`鬼監督 関門①（バッジ比率）: ${targets.length}件を検査します（${mobile ? "スマホ幅390x844" : "PC幅1280x900"}）`);
  const results = await runCheck(targets, { mobile });
  for (const r of results) {
    console.log(`[${r.verdict}] ${r.url}\n  ${r.reason}`);
  }
  appendLog(results, "606-oni-kantoku-badge-ratio");
  writeLatest(results);

  const fails = results.filter((r) => r.verdict === "FAIL" || r.verdict === "ERROR");
  if (fails.length > 0) {
    console.log(`\n不合格: ${fails.length}件。自己申告では通っても、ここで自動的に突き返します。`);
    process.exit(1);
  }
  console.log("\n全件合格（または対象外）。");
  process.exit(0);
}

const isMain = process.argv[1] && import.meta.url === `file://${process.argv[1]}`;
if (isMain) {
  main().catch((e) => {
    console.error("実行時エラー:", e);
    process.exit(2);
  });
}
