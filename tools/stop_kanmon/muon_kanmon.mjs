#!/usr/bin/env node
// 無音の関所（2026-10-10）PreToolUse：Bash / Write / Edit / MultiEdit
//
// 起きたこと：status/_v1oc/v2.mjs が Playwright の WebKit（iPhoneのふり）で YouTube を音ありで再生し、
//   たまごさんのMacから急に音が鳴った（17:00〜17:02・fix_and_test.log に playingWithSound:true が2件）。
// 決まり：音を鳴らす操作は禁止。確認はデータで行う（tools/session_preamble.md の先頭）。
//
// 止めるもの（判定の正本は tools/muon.py の check_text。ここは呼ぶだけ＝基準を2か所に持たない）
//   ① Bash：afplay / ffplay / mpg123 / mplayer / mpv / say を使うコマンド
//   ② Bash：node / python3 / bash で走らせるファイルが、無音の指定なしにブラウザを起動する
//   ③ Write / Edit / MultiEdit：書き上がるファイルが、無音の指定なしにブラウザを起動する
// 無音の指定：Chromium＝--mute-audio／WebKit＝tools/muon.mjs の muonContext（muon.py の INIT_JS）／
//             Firefox＝media.volume_scale=0。既存Chromeへ繋ぐだけのものは「// muon: 接続のみ」。
// 記録が読めない・形が違う → 黙って通す（exit 0）。人質にしない。台帳：status/muon_kanmon.jsonl
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const MUON = path.join(REPO, "tools", "muon.py");
const DAICHO = path.join(REPO, "status", "muon_kanmon.jsonl");
const EXEMPT = [/\.(md|txt|json|jsonl|log|html|css|csv)$/i, /tools\/muon\.(py|mjs)$/, /stop_kanmon\/muon_kanmon\.mjs$/];

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

function check(text, name) {
  try {
    const r = spawnSync("python3", [MUON, "--check-stdin", name], { input: text, encoding: "utf8", timeout: 15000 });
    return JSON.parse(r.stdout || "[]");
  } catch { return []; }
}
function block(why, file) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), tool, file, why }) + "\n", { flag: "a" });
  } catch {}
  console.error([
    "★音を鳴らす操作は禁止。確認はデータで行う。拒否した。（無音の関所・2026-10-10）",
    `　引っかかった所：${file || "(コマンド)"}`,
    ...why.map((w) => "　・" + w),
    "",
    "直し方：Chromium は args に \"--mute-audio\"／WebKit は tools/muon.mjs の muonContext(ctx) を通す／",
    "　Firefox は firefoxUserPrefs に media.volume_scale=\"0.0\"。Python は tools/muon.py の CHROMIUM_ARGS / INIT_JS。",
    "　音声ファイルの確認は ffprobe（長さ・音量のデータ）で行う。afplay / ffplay / say で鳴らさない。",
    "点検：python3 tools/muon.py（全部）／python3 tools/muon.py --self-test",
  ].join("\n"));
  process.exit(2);
}

let file = String(ti.file_path || "");
if (file && EXEMPT.some((rx) => rx.test(file))) process.exit(0);

if (tool === "Bash") {
  const cmd = String(ti.command || "");
  const hit = check(cmd, "cmd.sh").filter((x) => x.engine === "sound");
  if (hit.length) block(hit.map((x) => x.why), "");
  const files = [...cmd.matchAll(/\b(?:node|python3?|bash|sh|zsh)\s+(?:-[\w-]+\s+)*["']?([^\s"';|&]+\.(?:mjs|js|cjs|py|sh))/g)].map((m) => m[1]);
  for (const f of files) {
    const p = path.isAbsolute(f) ? f : path.resolve(String(input.cwd || process.cwd()), f);
    if (!existsSync(p) || EXEMPT.some((rx) => rx.test(p))) continue;
    let src = "";
    try { src = readFileSync(p, "utf8"); } catch { continue; }
    const bad = check(src, p);
    if (bad.length) block(bad.map((x) => x.why), p);
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
const bad = check(after, file);
if (bad.length) block(bad.map((x) => x.why), file);
process.exit(0);
