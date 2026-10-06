#!/usr/bin/env node
// 1851号【お金の確認ボタンは代行禁止の関所】2026-10-01
//
// たまごさん（スマホから・3回言わせている）：
//   「会話中の『やってみて』だけでは発車しない——ボタン操作が必須。」
//
// ■ 背景（案件#676で既に入っている仕組み）
//   costsMoney が立ったタスクは tools/auto_launcher.py が絶対に自動発車せず、
//   status/dispatch_outbox.jsonl へ確認を出す。たまごさんが進捗表の💴「OKで発車を許可」
//   ボタンを押すと command_ingest.py の queue_cost_ok() が costApproved を立てる。
//   ＝ここまでは既存実装（README.md「お金がかかるタスクの確認」節）で動いている。
//
// ■ ここで塞ぐ穴
//   AIセッション（Dispatch・子セッション）が、会話中の「やってみて」という
//   ひとことだけを根拠に、たまごさんの代わりにボタン操作を成立させてしまう経路。
//     ① Bashで queue_cost_ok(...) を直接呼び出す／command_ingest.py へのワンライナー
//     ② Bashや編集で costApproved を直接 true/True にする
//     ③ status/inbox/*.md へ {"action":"queue_cost_ok", ...} を自分で書いて処理させる
//   これらを検知した瞬間に exit 2 で拒否する。
//   ※ コードの読み書き（command_ingest.py の関数定義を直す等）は止めない。
//      止めるのは「実データ・実行」側（status/queue.json・status/inbox/・Bash実行）だけ。
//
// 外部AI（codex・白紙相談）の回答：「権限分離と明示承認ゲート。会話文・コマンド・
// 設定ファイルだけでは承認状態を変更できない設計にする」に沿っている（1184番の票：
// status/original_kinshi/hyo-1790787358.json）。
//
// 台帳：status/1851_okane_botan.jsonl
// OSには触らない。AppleScript / osascript / System Events は1行も使わない。

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "1851_okane_botan.jsonl");
const CONF = path.join(REPO, "status", "1851_okane_botan.json");

let CONFIG = { enabled: true };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

// ── 止める形（実行・実データだけを見る。コード定義そのものは見ない）────────
const RULES = [
  {
    name: "direct-call",
    rx: /queue_cost_ok\s*\(/,
    say: "queue_cost_ok() を直接呼び出そうとしている（進捗表のボタンを経由していない）",
  },
  {
    name: "cost-approved-assign",
    rx: /costApproved[^\n]{0,4}[:=]\s*(True|true)\b/,
    say: "costApproved を直接 true にしようとしている",
  },
  {
    name: "inbox-cost-ok-action",
    rx: /"action"\s*:\s*"queue_cost_ok"/,
    say: "queue_cost_ok を実行させる指示（inboxコマンド）を自分で作ろうとしている",
  },
];

// ── 見に行かないファイル（コードの読み書き・記録・関所自身）──────────────
const EXEMPT_PATH = [
  /\.(py|mjs|js|ts|sh)$/i,
  /stop_kanmon\/1851_/,
  /status\/1851_/,
];

// ── Write/Edit/MultiEditで実際に見にいく先（データ側だけ）────────────────
const DATA_PATH = /status\/queue\.json$|status\/inbox\//;

function write(rec) {
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
let input = {};
try {
  input = JSON.parse(stdin || "{}");
} catch {}

if (!CONFIG.enabled) process.exit(0);

const tool = String(input.tool_name || "");
const ti = input.tool_input || {};
const sid = String(input.session_id || "unknown");

let subject = "";
const fp = String(ti.file_path || "");
if (tool === "Bash") {
  subject = String(ti.command || "");
} else if (tool === "Write") {
  if (!DATA_PATH.test(fp)) process.exit(0);
  subject = String(ti.content || "");
} else if (tool === "Edit") {
  if (!DATA_PATH.test(fp)) process.exit(0);
  subject = String(ti.new_string || "");
} else if (tool === "MultiEdit") {
  if (!DATA_PATH.test(fp)) process.exit(0);
  subject = (ti.edits || []).map((e) => String(e?.new_string || "")).join("\n");
} else {
  process.exit(0);
}
if (!subject) process.exit(0);
if (fp && EXEMPT_PATH.some((rx) => rx.test(fp))) process.exit(0);

for (const r of RULES) {
  if (!r.rx.test(subject)) continue;
  write({ event: "okane_botan", decision: "block", session: sid, tool, file: fp, rule: r.name });
  console.error(
    [
      "★お金の確認は、たまごさん本人が進捗表の💴ボタンを押す操作でなければならない。拒否した。（1851号）",
      `　引っかかった形：${r.say}`,
      "",
      "たまごさん（スマホから・3回言わせている）：",
      "　「会話中の『やってみて』だけでは発車しない——ボタン操作が必須。」",
      "",
      "なぜ：ここを素通りさせると、会話の中の軽い同意ひとことで課金が発火してしまう",
      "　　　（2026-09-08にfalで15ドル溶けた事故と同じ構造）。",
      "",
      "正しい経路：",
      "　・tools/auto_launcher.py が costsMoney を検知して dispatch_outbox.jsonl へ確認を出す",
      "　・たまごさんが進捗表（PWA）の💴「OKで発車を許可」ボタンを実際にタップする",
      "　・その操作だけが command_ingest.py の queue_cost_ok() を正規に動かす",
      "",
      "会話で『やってみて』が来た時は、ボタンを押してもらうよう伝えるだけにして、",
      "AI側でcostApprovedやqueue_cost_okを代行しないこと。",
      "",
      "★この関所を外す道は用意していない。外すならたまごさん自身の判断で",
      "　status/1851_okane_botan.json に {\"enabled\": false} を書く。",
      "（台帳：status/1851_okane_botan.jsonl）",
    ].join("\n"),
  );
  process.exit(2);
}

process.exit(0);
