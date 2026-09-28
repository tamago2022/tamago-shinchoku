#!/usr/bin/env node
// 1184号【オリジナル禁止の関所】2026-09-29
//
// たまごさん（2026-09-29・恒久ルール／憲法）：
//   「一流に倣って、先人に倣って、常に。オリジナル禁止、憲法で禁止です。」
//   「書いておく」では効かない。書き物は読まれない。だから関所にする。
//   （既知の教訓＝「リンクは読まれない。絶対に守るものは索引の本文に書く」）
//
// ■ 何を止めるか（＝「新しいやり方を実装した瞬間」だけ）
//   Write で **新しく** 実行物を作るときだけ止める。
//     .py .mjs .js .cjs .ts .tsx .sh .bash .rb .go .rs
//   既にあるファイルの Edit は止めない（直しは新方式ではない）。
//   Read / Grep / Glob / 調べ物 / .md / .json / .txt / .html も止めない。
//   ＝「調べる」ことは一切邪魔せず、「自分で発明する」ところだけを塞ぐ。
//
// ■ 通り方（5段階を順に埋めるまで通れない）
//   ① 公式ドキュメントの目次を通しで読んだか（★特に「MCPはあるか」を毎回確認）
//   ② 公式サンプルをそのまま移植できないか
//   ③ 優れた実例（金をかけずに同じことをやっている人）をお手本にできないか
//   ④ 外部AIに **白紙で** 聞いたか（こちらの結論を見せずに）
//   ⑤ ①〜④が全部✕だった証拠があるときだけ、自分で考えてよい
//
//   python3 tools/1184_kanmon.py shirabe \
//     --nani  "<何を作ろうとしているか>" \
//     --koushiki "<①公式ドキュメントの目次で見たこと>" \
//     --mcp   "<①MCPを探した結果。無いなら『探して無かった』と書く>" \
//     --sample "<②公式サンプル：あるならそのまま移植／無いなら無い>" \
//     --jitsurei "<③金をかけずに同じことをやっている実例>" \
//     --gaibu "<④外部AIに白紙で聞いた結果>" \
//     --ketsuron sonomama|tsukaenai
//
// ■ 「似せる」は不合格、「そのまま」が合格
//   ketsuron=sonomama（＝公式か実例をそのまま使う）が本線。
//   ketsuron=tsukaenai（＝自分で考える）は、①〜④の全部に「✕だった証拠」が要る。
//
// ■ 人質にしない
//   設定で切ってある／記録が壊れている／形が違う → 黙って通す（exit 0）。
//   ＝この関所が壊れても仕事は止まらない。
//
// 票：status/original_kinshi/*.json ／ 台帳：status/1184_kanmon.jsonl
// 設定：status/1184_kanmon.json（{"enabled":false} で切れる）
// OSには触らない。AppleScript / osascript / System Events は1行も使わない。

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const ST = path.join(REPO, "status");
const DAICHO = path.join(ST, "1184_kanmon.jsonl");
const CONF = path.join(ST, "1184_kanmon.json");
const HYO_DIR = path.join(ST, "original_kinshi");

let CONFIG = { enabled: true, ttlSec: 86400 };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

// 新しい「やり方」が生まれる拡張子だけ
const JISSOU = /\.(py|mjs|cjs|js|ts|tsx|sh|bash|rb|go|rs)$/i;

function log(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", {
      flag: "a",
    });
  } catch {}
}

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 3000);
});

let inp = {};
try {
  inp = JSON.parse(stdin || "{}");
} catch {
  process.exit(0); // 形が違う＝人質にしない
}

if (CONFIG.enabled === false) process.exit(0);

const tool = String(inp.tool_name || "");
const ti = inp.tool_input || {};
const sid = String(inp.session_id || "nosession");
const fp = String(ti.file_path || "");

// ── 発動条件：Write で、まだ無いファイルを、実行物の拡張子で作るとき ──────
if (tool !== "Write") process.exit(0);
if (!JISSOU.test(fp)) process.exit(0);
if (existsSync(fp)) process.exit(0); // 既存の作り直しは「新しいやり方」ではない
// 関所自身と、関所を通るための道具は塞がない（自分で自分を閉じ込めない）
if (/1184_/.test(path.basename(fp))) process.exit(0);
if (/\/status\/oneshot\//.test(fp)) process.exit(0); // 心臓へ渡す一発物

// ── 票があるか（5段階が埋まっているか） ───────────────────────────
const NEED = ["koushiki", "mcp", "sample", "jitsurei", "gaibu"];

function findHyo() {
  try {
    if (!existsSync(HYO_DIR)) return null;
    const now = Date.now() / 1000;
    const names = readdirSync(HYO_DIR).filter((n) => n.endsWith(".json")).sort().reverse();
    for (const n of names) {
      let o;
      try {
        o = JSON.parse(readFileSync(path.join(HYO_DIR, n), "utf8"));
      } catch {
        continue;
      }
      if (now - Number(o.at || 0) > (CONFIG.ttlSec || 86400)) continue;
      if (!NEED.every((k) => String(o[k] || "").trim().length >= 4)) continue;
      if (!["sonomama", "tsukaenai"].includes(String(o.ketsuron || ""))) continue;
      return { name: n, ...o };
    }
  } catch {}
  return null;
}

const hyo = findHyo();
if (hyo) {
  log({ ev: "pass", tool, sid, file: fp, hyo: hyo.name, ketsuron: hyo.ketsuron });
  process.exit(0);
}

log({ ev: "block", tool, sid, file: fp });
console.error(
  [
    "【1184号の関所】オリジナル禁止。新しいやり方を実装する前に、先人を5段階で当たること。",
    "",
    "たまごさん：「一流に倣って、先人に倣って、常に。オリジナル禁止、憲法で禁止です。」",
    "",
    "止めた手：Write（新規）" + (fp ? " → " + fp : ""),
    "",
    "順に埋める（1行ずつ。飛ばせない）：",
    "  ① 公式ドキュメントの目次を通しで読んだか ★特に『MCPはあるか』を毎回",
    "  ② 公式サンプルをそのまま移植できないか",
    "  ③ 優れた実例（金をかけずに同じことをやっている人）をお手本にできないか",
    "  ④ 外部AIに **白紙で** 聞いたか（こちらの結論を見せずに）",
    "  ⑤ ①〜④が全部✕だった証拠があるときだけ、自分で考えてよい",
    "",
    "★「似せる」は不合格。「そのまま」が合格。",
    "",
    "通し方（1回流すだけ。心臓経由なら status/oneshot/pending/*.sh に置く）：",
    "  python3 tools/1184_kanmon.py shirabe \\",
    '    --nani "<何を作ろうとしているか>" \\',
    '    --koushiki "<①目次で見たこと>" --mcp "<①MCPを探した結果>" \\',
    '    --sample "<②公式サンプル>" --jitsurei "<③実例>" --gaibu "<④白紙で聞いた結果>" \\',
    "    --ketsuron sonomama     # そのまま使う（本線）",
    "    # 自分で考えるなら --ketsuron tsukaenai（①〜④の✕の証拠が要る）",
    "",
    "（票：status/original_kinshi/ ／ 台帳：status/1184_kanmon.jsonl）",
  ].join("\n"),
);
process.exit(2);
