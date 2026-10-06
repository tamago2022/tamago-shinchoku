#!/usr/bin/env node
// 1180号【読まずに始められない関所】2026-09-28
//
// たまごさん：
//   「担当が変わっても同じ脳みそからスタートしたい。前回は散々言ったのに半分も伝わってなくて、
//     後ろを振り返りながら進むことになった。また俺が説明するのかと思うと担当を変えるのも気が重い」
//
// ■ 何をするか
//   **その会話の最初のツール使用の前に**、status/hikitsugi_ima.md を読ませる。
//   読んだ形跡（今日の合言葉）が無ければ、仕事の道具を1つも使わせない（exit 2）。
//   924番の「抜き打ち7問」は *お願い* だった（プロンプトに書いてあるだけ）。これは *関所* にする。
//   作りは 1401_iru_ka.mjs（ブラウザの関所）に揃えてある。
//
// ■ 通る道は2つ（どちらでもよい）
//   A) 端末が使える担当：
//        python3 tools/1180_hikitsugi_kanmon.py --yonda <合言葉>
//   B) 端末が無い担当（Cowork等・Write以外の実行手段が無い）：
//        status/1180_yonda/<session_id>.txt に合言葉を1行書く（Writeは通してある）
//   ★合言葉は status/hikitsugi_ima.md の 0章と
//     https://tamago2022.github.io/tamago-shinchoku/share/1180-hikitsugi-ima.html にしか無い。
//     日付から機械で決まるので、当てずっぽうでは入らない。
//
// ■ 通す道具（これが無いと読むことすらできなくなる＝自分で自分を閉じ込める）
//   Read / Grep / Glob / LS / TodoWrite / Task系、
//   Write（status/1180_yonda/ 配下だけ）、Bash（1180_hikitsugi を含む行だけ）。
//
// ■ 人質にしない
//   設定で切ってある・記録が壊れている・形が違う → 黙って通す（exit 0）。
//
// 台帳：status/1180_kanmon.jsonl ／ 設定：status/1180_kanmon.json
// OSには触らない。AppleScript / osascript / System Events は1行も使わない。

import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const ST = path.join(REPO, "status");
const DAICHO = path.join(ST, "1180_kanmon.jsonl");
const CONF = path.join(ST, "1180_kanmon.json");
const AIKOTOBA = path.join(ST, "1180_aikotoba.json");
const YONDA_DIR = path.join(ST, "1180_yonda");
const IMA_MD = path.join(ST, "hikitsugi_ima.md");
const URL_HTML =
  "https://tamago2022.github.io/tamago-shinchoku/share/1180-hikitsugi-ima.html";

let CONFIG = { enabled: true };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

const PASS_TOOLS = new Set([
  "Read", "Grep", "Glob", "LS", "NotebookRead",
  "TodoWrite", "TaskCreate", "TaskUpdate", "TaskList", "TaskGet",
  "ToolSearch", "Skill", "ExitPlanMode",
]);

function log(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", {
      flag: "a",
    });
  } catch {}
}

function today() {
  // JSTの日付。合言葉は日付で決まる。
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}

function expected() {
  try {
    const a = JSON.parse(readFileSync(AIKOTOBA, "utf8"));
    if (a.date === today() && a.aikotoba) return String(a.aikotoba);
  } catch {}
  return null;
}

function alreadyRead(sessionId, want) {
  // ① Pythonの窓口が書いた記録
  try {
    const p = path.join(YONDA_DIR, "_passed.json");
    if (existsSync(p)) {
      const j = JSON.parse(readFileSync(p, "utf8"));
      const r = (j.sessions || {})[sessionId];
      if (r && r.date === today() && r.aikotoba === want) return true;
    }
  } catch {}
  // ② 担当が自分でWriteした札（端末が無い担当のための道）
  try {
    if (!existsSync(YONDA_DIR)) return false;
    for (const n of readdirSync(YONDA_DIR)) {
      if (!n.endsWith(".txt")) continue;
      const body = readFileSync(path.join(YONDA_DIR, n), "utf8").trim();
      if (!body.includes(want)) continue;
      // セッションid入りの札が本命。名前が合わなくても当日の合言葉が書けている札は通す
      // （ここを厳しくすると、読んだのに進めない＝一番たちの悪い詰まり方になる）。
      // 2026-09-30（1713番）★ここが緩くて関所が死んでいた。
      // 逆テストで①④⑤が全部「通ってしまった」＝誰か1人が今日の札を置くと、
      // 以後その日は**全員**が読まずに通れていた（= 新担当が読まずに始められる）。
      // 直し方：札はその担当（session_id）のものだけ有効にする。
      // 「読んだのに進めない」を作らないための逃げ道は、止めたときのメッセージに
      //  書いてある `status/1180_yonda/<session_id>.txt` の1手だけ（Writeは通してある）。
      const stem = n.slice(0, -4);
      if (stem === sessionId) return true;
    }
  } catch {}
  return false;
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

const tool = inp.tool_name || "";
const ti = inp.tool_input || {};
const sid = String(inp.session_id || "nosession");

// --- 通す道具 ---------------------------------------------------------------
if (PASS_TOOLS.has(tool)) process.exit(0);
if (tool.startsWith("Task")) process.exit(0);
if (tool === "Write" || tool === "Edit") {
  const fp = String(ti.file_path || "");
  if (fp.includes("1180_yonda")) process.exit(0);
}
if (tool === "Bash" || tool.endsWith("__bash")) {
  const c = String(ti.command || "");
  if (c.includes("1180_hikitsugi")) process.exit(0);
}

const want = expected();
if (!want) {
  // 合言葉がまだ作られていない（心臓が回っていない等）＝止める理由にしない
  log({ ev: "pass_no_aikotoba", tool, sid });
  process.exit(0);
}

if (alreadyRead(sid, want)) {
  log({ ev: "pass", tool, sid });
  process.exit(0);
}

log({ ev: "block", tool, sid });
console.error(
  [
    "【1180号の関所】まだ引き継ぎを読んでいないので、道具を使わせません。",
    "",
    "たまごさんは前回、散々言ったことが半分も伝わっていない状態で仕事が始まり、",
    "後ろを振り返りながら進むことになりました。同じことを二度させない関所です。",
    "",
    "1) まずこれを読む（Readは通してあります）:",
    "     " + IMA_MD,
    "   スマホなら: " + URL_HTML,
    "",
    "2) 0章に書いてある『今日の合言葉』を、次のどちらかで置く:",
    "   A) 端末が使えるなら:",
    "        python3 tools/1180_hikitsugi_kanmon.py --yonda <合言葉>",
    "   B) 端末が無いなら（Write は通してあります）:",
    "        status/1180_yonda/" + sid + ".txt に合言葉を1行書く",
    "",
    "3) そのあと、いま止められた作業をもう一度やり直してください。",
    "",
    "※ 合言葉は当てられません。引き継ぎを開くしか道はありません。",
  ].join("\n"),
);
process.exit(2);
