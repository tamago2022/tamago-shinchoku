#!/usr/bin/env node
// 39685号【AppleScript / System Events / osascript 全面禁止の関所】2026-11-26
//
// たまごさん（スマホから・2026-10-02）：「AppleScript / System Events / osascript は禁止。」
// ★3回言わせている（止まらない係が自動で発車）。
//
// ■ 既存との違い
//   1186号（Chrome起動禁止・2026-09-29）には、ブラウザ2種を名指しした狙い撃ちルールが
//   既にあるが、それは「対象の2アプリを触る」場面だけを拒否する限定ルールだった。
//   TASK_BOARD.md に残っている実例（公開便の調査中に件のコマンドでブラウザの生死を
//   確認しようとした件）はこれでカバーできるが、たまごさんの発言は用途を問わない全面禁止。
//   ここではアプリ・用途を問わず、AppleScript / System Events / osascript の呼び出し
//   そのものを拒否する（Bash / Write / Edit / MultiEdit の中身を見る）。
//
// ■ 止めるもの
//   ① osascript コマンドそのもの（osascript -e "..." / <<EOF / 単体呼び出し）
//   ② AppleScript構文 tell application "..."
//   ③ System Events への言及（UI操作・キー送信・クリックの対象）
//   ④ Pythonからの呼び出し（appscript / py-applescript / applescript ライブラリ）
//   ⑤ Node/ObjCのネイティブAPI（NSAppleScript / NSAppleEventDescriptor）
//
// ■ 止めないもの
//   ・.md / .txt / .jsonl / .log / .html（記録・台帳・説明文。事実を書くのは自由）
//   ・この関所自身、既存の禁止コード（1186号・1161号・34483号等）
//   ・記録が読めない・形が違う → 黙って通す（exit 0）。人質にしない。
//
// 台帳：status/39685_osascript_kinshi.jsonl
// OSには触らない（この関所自身も、拒否対象にしているものを1行も使わない）。

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "39685_osascript_kinshi.jsonl");
const CONF = path.join(REPO, "status", "39685_osascript_kinshi.json");

let CONFIG = { enabled: true };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

const RULES = [
  {
    name: "osascript-call",
    rx: /\bosascript\b/i,
    say: "osascript を呼んでいる（AppleScript実行コマンド）",
  },
  {
    name: "applescript-tell-application",
    rx: /\btell\s+application\s+["']/i,
    say: "AppleScriptのtell application構文を書いている",
  },
  {
    name: "system-events",
    rx: /\bSystem\s+Events\b/i,
    say: "System Events（AppleScriptのUI操作・クリック・キー送信の対象）に触っている",
  },
  {
    name: "python-applescript-lib",
    rx: /\b(appscript|py-applescript)\b|^\s*import\s+applescript\b|from\s+applescript\s+import/im,
    say: "AppleScript実行用のPythonライブラリを使っている",
  },
  {
    name: "ns-applescript-api",
    rx: /\bNSAppleScript\b|\bNSAppleEventDescriptor\b/,
    say: "AppleEvent/AppleScriptのネイティブAPIを呼んでいる",
  },
];

const EXEMPT_PATH = [
  /\.(md|txt|jsonl|log|html)$/i,
  /stop_kanmon\/39685_/,
  /status\/39685_/,
  // 既存の禁止コード自身（自分を禁止語で誤検知させない）
  /stop_kanmon\/1186_/,
  /stop_kanmon\/1161_|stop_kanmon\/browser_kanmon\.mjs$|stop_kanmon\/tab_kanmon\.mjs$/,
  /stop_kanmon\/34483_/,
];

function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", {
      flag: "a",
    });
  } catch {}
}

function judge(subject, file) {
  if (file && EXEMPT_PATH.some((rx) => rx.test(file))) return null;
  if (!subject) return null;
  for (const r of RULES) {
    if (r.rx.test(subject)) return r;
  }
  return null;
}

function blockMessage(rule) {
  return [
    "★AppleScript / System Events / osascript は憲法で全面禁止。拒否した。（39685号）",
    `　引っかかった形：${rule.say}`,
    "",
    "たまごさん（2026-10-02・スマホから）：",
    "　「AppleScript / System Events / osascript は禁止。」",
    "",
    "なぜ：osascriptはたまごさんの画面に許可ダイアログを出し、AppleEventがタイムアウトすると",
    "　　　処理全体が詰まる。用途（特定アプリの操作に限らず）を問わず使わない。",
    "",
    "代わりに使うもの：",
    "　・画面を見る → 既に開いているタブを Chrome/内蔵ブラウザの MCP で読む（新しく開かない）",
    "　・プロセスの生死確認 → ps / pgrep / lsof（OSのAppleEvent層を経由しない）",
    "　・ファイル操作・自動化 → Node/Python標準ライブラリ、または既存の tools/ 配下の道具",
    "",
    "★この関所を外して通す道は用意していない。外すなら status/39685_osascript_kinshi.json に",
    "　{\"enabled\": false} を書く＝たまごさんが自分で判断したときだけ。",
    "（台帳：status/39685_osascript_kinshi.jsonl）",
  ].join("\n");
}

async function main() {
  if (process.argv.includes("--self-test")) {
    const cases = [
      { tool: "Bash", ti: { command: 'osascript -e \'tell application "Finder" to activate\'' }, want: "block" },
      { tool: "Bash", ti: { command: 'osascript -e \'tell application "System Events" to keystroke "a"\'' }, want: "block" },
      { tool: "Write", ti: { file_path: "/tmp/t.py", content: 'import subprocess\nsubprocess.run(["osascript", "-e", "x"])' }, want: "block" },
      { tool: "Write", ti: { file_path: "/tmp/t.py", content: "from appscript import app" }, want: "block" },
      { tool: "Bash", ti: { command: "ps aux | grep Finder" }, want: "pass" },
      { tool: "Write", ti: { file_path: "/tmp/t.md", content: "外部スクリプト言語の禁止を書いたメモ" }, want: "pass" },
      { tool: "Write", ti: { file_path: path.join(REPO, "tools/stop_kanmon/39685_osascript_zenmen_kinshi.mjs"), content: "この関所自身の内容" }, want: "pass" },
    ];
    let ok = 0;
    for (const c of cases) {
      let subject = "";
      const fp = String(c.ti.file_path || "");
      if (c.tool === "Bash") subject = String(c.ti.command || "");
      else if (c.tool === "Write") subject = String(c.ti.content || "");
      const rule = judge(subject, fp);
      const got = rule ? "block" : "pass";
      const pass = got === c.want;
      if (pass) ok++;
      console.log(`${pass ? "OK" : "NG"} tool=${c.tool} want=${c.want} got=${got}${rule ? " rule=" + rule.name : ""}`);
    }
    console.log(`self-test: ${ok}/${cases.length} 合格`);
    process.exit(ok === cases.length ? 0 : 1);
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

  if (!CONFIG.enabled) process.exit(0);

  const tool = String(input.tool_name || "");
  const ti = input.tool_input || {};
  const sid = String(input.session_id || "unknown");
  const fp = String(ti.file_path || "");

  let subject = "";
  if (tool === "Bash") {
    subject = String(ti.command || "");
  } else if (tool === "Write") {
    subject = String(ti.content || "");
  } else if (tool === "Edit") {
    subject = String(ti.new_string || "");
  } else if (tool === "MultiEdit") {
    subject = (ti.edits || []).map((e) => String(e?.new_string || "")).join("\n");
  } else {
    process.exit(0);
  }

  const rule = judge(subject, fp);
  if (rule) {
    write({ event: "osascript_kinshi", decision: "block", session: sid, tool, file: fp, rule: rule.name });
    console.error(blockMessage(rule));
    process.exit(2);
  }
  process.exit(0);
}

main();
