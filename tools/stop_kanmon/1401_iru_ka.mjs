#!/usr/bin/env node
// 1401号【上流の関所】2026-09-28
//   「この仕事はブラウザを使わずに済むか」を**タブを開く前に**機械が聞く。
//
// たまごさん：
//   「Chromeに使っていないタブが溜まり続けている。毎回手で消している。今回で終わらせる。」
//   「上流。この仕事はブラウザを使わずに済むかを先に判定する関所を作り、
//     web_fetch / API / ファイル+push で済むならブラウザ禁止にする。」
//
// ■ 何を止めるか
//   タブを**新しく作る**道具だけ。既に開いているタブを読む・押すのは止めない。
//     mcp__claude-in-chrome__tabs_create_mcp
//     mcp__claude-in-chrome__navigate（tabId を渡していない＝勝手に1枚作る呼び方）
//     mcp__Claude_Browser__tabs_create / preview_start
//
// ■ 止め方（2段）
//   ① 「ブラウザを使わずに済む先」なら**無条件で拒否**する。
//      ・静的なHTML/JSON/テキスト（GitHub raw・*.json・*.md・*.txt・robots.txt・sitemap）
//      ・API のURL（/api/ を含む、api.*.* ドメイン）
//      → web_fetch か curl で取れる。タブは1枚も要らない。
//   ② それ以外は「理由を宣言していれば通す」。
//      宣言は1行：
//        python3 tools/1401_kanmon.py declare --why "<なぜブラウザが要るのか>" --url "<開くURL>"
//      宣言すると同時に **978番の予約閉栓の票（chrome_reserve）が自動で置かれる**ので、
//      セッションが途中で死んでも、外側の掃除機がそのタブを閉じられる。
//      ＝「開く前に、閉じる約束をさせる」。これが今までどこにも無かった1手。
//
// ■ 人質にしない
//   記録が読めない・形が違う・宣言ファイルが壊れている → 黙って通す（exit 0）。
//
// 台帳：status/1401_iru_ka.jsonl
// OSには触らない。AppleScript / osascript / System Events は1行も使わない。

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "1401_iru_ka.jsonl");
const DECL = path.join(REPO, "status", "1401_sengen");
const CONF = path.join(REPO, "status", "1401_iru_ka.json");

let CONFIG = { enabled: true, declareTtlSec: 3600 };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

const OPENERS = new Set([
  "mcp__claude-in-chrome__tabs_create_mcp",
  "mcp__Claude_Browser__tabs_create",
  "mcp__Claude_Browser__preview_start",
]);

const NO_BROWSER = [
  /^https?:\/\/raw\.githubusercontent\.com/i,
  /^https?:\/\/api\./i,
  /\/api\//i,
  /\.(json|md|txt|xml|csv|ya?ml|rss|atom)(\?|$)/i,
  /\/robots\.txt$/i,
  /\/sitemap[^/]*\.xml$/i,
  /^https?:\/\/[^/]*\/\.well-known\//i,
];

function nowIso() {
  return new Date().toISOString();
}
function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: nowIso(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 3000);
});
let input = {};
try {
  input = JSON.parse(stdin || "{}");
} catch {}

const tool = String(input.tool_name || "");
const ti = input.tool_input || {};
const sid = String(input.session_id || "unknown");

if (!CONFIG.enabled) process.exit(0);

const isNavNoTab =
  (tool === "mcp__claude-in-chrome__navigate" || tool === "mcp__Claude_Browser__navigate") &&
  ti.url &&
  ti.tabId === undefined;
if (!OPENERS.has(tool) && !isNavNoTab) process.exit(0);

const url = String(ti.url || "");

function deny(lines, why) {
  write({ event: "iruka", decision: "block", session: sid, tool, url, why });
  console.error(lines.filter(Boolean).join("\n"));
  process.exit(2);
}

// ── ① ブラウザが要らないことが確定している先 ────────────────────────
if (url) {
  for (const rx of NO_BROWSER) {
    if (rx.test(url)) {
      deny(
        [
          "★この住所はブラウザを使わずに取れる。タブを開くことを拒否した。",
          `　住所：${url}`,
          "　代わりに使うもの：web_fetch（または Mac側で curl。心臓経由なら status/oneshot/pending/*.sh）。",
          "　理由：JavaScriptで組み立てる画面ではなく、そのまま本文が返る先だから。",
          "",
          "どうしてもブラウザでないと駄目な事情（ログインが要る／押さないと出ない）があるなら、",
          "先に1行だけ宣言してから開くこと：",
          `  python3 tools/1401_kanmon.py declare --why "<なぜブラウザが要るのか>" --url "${url}"`,
          "（台帳：status/1401_iru_ka.jsonl）",
        ],
        "static-fetchable",
      );
    }
  }
}

// ── ② 宣言があるか ──────────────────────────────────────────
function hasDeclaration() {
  try {
    if (!existsSync(DECL)) return null;
    const now = Date.now() / 1000;
    for (const n of readdirSync(DECL)) {
      if (!n.endsWith(".json")) continue;
      const p = path.join(DECL, n);
      let o;
      try {
        o = JSON.parse(readFileSync(p, "utf8"));
      } catch {
        continue;
      }
      const at = Number(o.at || statSync(p).mtimeMs / 1000);
      if (now - at > (CONFIG.declareTtlSec || 3600)) continue;
      return o;
    }
  } catch {}
  return null;
}

const d = hasDeclaration();
if (d) {
  write({ event: "iruka", decision: "pass", session: sid, tool, url, why: d.why || "" });
  process.exit(0);
}

deny(
  [
    "★タブを開く前に「本当にブラウザが要るのか」を1行で宣言すること。（1401号・上流の関所）",
    "",
    "まず考える順番（これが憲法）：",
    "  1. web_fetch で本文が取れるか → 取れるならブラウザは要らない",
    "  2. API / gh / curl で取れるか → 取れるならブラウザは要らない",
    "  3. ファイルを直接読む・書いて push で済むか → 済むならブラウザは要らない",
    "  4. どれも駄目（ログインが要る・押さないと出ない・描画を目で見る必要がある）→ ブラウザ",
    "",
    "4に当たるなら、開く前にこれを1回だけ流す：",
    `  python3 tools/1401_kanmon.py declare --why "<なぜブラウザが要るのか>" --url "${url || "<開くURL>"}"`,
    "",
    "★この宣言は同時に「予約閉栓の票」を置く。セッションが途中で死んでも、",
    "　外側の掃除機（launchd: com.tamago.chrome-tab-cdp）がそのタブを閉じる。",
    "　＝開く前に、閉じる約束をさせている。",
    "（台帳：status/1401_iru_ka.jsonl）",
  ],
  "no-declaration",
);
