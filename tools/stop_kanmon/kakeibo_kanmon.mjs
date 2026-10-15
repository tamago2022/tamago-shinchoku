#!/usr/bin/env node
// 家計簿の関所（2026-10-11）PreToolUse：Bash / Write / Edit / MultiEdit
//
// たまごさん：「案件ごとのコストを家計簿みたいに全部つけて。把握したい」
// 決まり：fal・Gemini・xAI を叩くときは、必ず案件名をつけて status/kakeibo.jsonl に1行書く。案件名が無い呼び出しは止める。
//
// 止めるもの（判定の正本は tools/kakeibo.py の check_text。ここは呼ぶだけ＝基準を2か所に持たない）
//   ① Bash：コマンドそのものが fal / Gemini / xAI を叩く（curl 等）のに kakeibo を通していない
//   ② Bash：node / python3 / bash で走らせるファイルが、家計簿（kakeibo か yosan.mitsumori）を通さずに叩く
//   ③ Write / Edit / MultiEdit：書き上がるコードが、家計簿を通さずに叩く
// 通るもの：中に kakeibo / yosan.mitsumori がある・「# kakeibo: 課金なし（理由）」の印がある
// 記録が読めない・形が違う → 黙って通す（exit 0）。人質にしない。台帳：status/kakeibo_kanmon.jsonl
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const KAKEIBO = path.join(REPO, "tools", "kakeibo.py");
const DAICHO = path.join(REPO, "status", "kakeibo_kanmon.jsonl");
const EXEMPT = [/\.(md|txt|json|jsonl|log|html|css|csv)$/i, /tools\/kakeibo\.py$/, /stop_kanmon\/kakeibo_kanmon\.mjs$/];

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 3000);
});
let input = {};
try { input = JSON.parse(stdin || "{}"); } catch { process.exit(0); }
const tool = String(input.tool_name || "");
const ti = input.tool_input || {};

function check(text) {
  try {
    const r = spawnSync("python3", [KAKEIBO, "--check-stdin"], { input: text, encoding: "utf8", timeout: 15000 });
    return JSON.parse(r.stdout || "[]");
  } catch { return []; }
}
function block(hits, file) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), tool, file, why: hits.map((h) => h.why) }) + "\n", { flag: "a" });
  } catch {}
  console.error([
    "★案件名のない外部API呼び出しは禁止。拒否した。（家計簿の関所・2026-10-11）",
    `　引っかかった所：${file || "(コマンド)"}`,
    ...hits.map((h) => "　・" + h.why),
    "",
    "直し方：叩く前に  import kakeibo; anken = kakeibo.anken_hissu()  （案件名は TAMAGO_ANKEN=\"水彩トーン v2\" で渡す）",
    "　叩いた後に  kakeibo.kiroku(anken, \"fal\", モデル, \"1枚\", usd=..., kakutei=\"推定\")  で1行。",
    "　予算の栓を使うなら yosan.mitsumori(財布, 円, 何に, anken=案件名)。",
    "　お金がかからない確認だけなら、その行の上に「# kakeibo: 課金なし（理由）」。",
    "家計簿：https://tamago2022.github.io/tamago-shinchoku/share/check/kakeibo.html ／ 試験：python3 tools/kakeibo.py --self-test",
  ].join("\n"));
  process.exit(2);
}

let file = String(ti.file_path || "");
if (file && EXEMPT.some((rx) => rx.test(file))) process.exit(0);

if (tool === "Bash") {
  const cmd = String(ti.command || "");
  const hit = check(cmd);
  if (hit.length) block(hit, "");
  const files = [...cmd.matchAll(/\b(?:node|python3?|bash|sh|zsh)\s+(?:-[\w-]+\s+)*["']?([^\s"';|&]+\.(?:mjs|js|cjs|py|sh))/g)].map((m) => m[1]);
  for (const f of files) {
    const p = path.isAbsolute(f) ? f : path.resolve(String(input.cwd || process.cwd()), f);
    if (!existsSync(p) || EXEMPT.some((rx) => rx.test(p))) continue;
    let src = "";
    try { src = readFileSync(p, "utf8"); } catch { continue; }
    const bad = check(src);
    if (bad.length) block(bad, p);
  }
  process.exit(0);
}

let after = "";
if (tool === "Write") after = String(ti.content || "");
else if (tool === "Edit" || tool === "MultiEdit") {
  let cur = "";
  try { cur = readFileSync(file, "utf8"); } catch {}
  const edits = tool === "Edit" ? [ti] : ti.edits || [];
  after = cur;
  for (const e of edits) {
    const o = String(e?.old_string || ""), n = String(e?.new_string || "");
    after = o && after.includes(o) ? (e.replace_all ? after.split(o).join(n) : after.replace(o, n)) : after + "\n" + n;
  }
} else process.exit(0);
if (!after || !/\.(py|mjs|js|cjs|ts|sh|command)$/.test(file)) process.exit(0);
const bad = check(after);
if (bad.length) block(bad, file);
process.exit(0);
