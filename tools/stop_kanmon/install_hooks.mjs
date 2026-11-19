#!/usr/bin/env node
// 1168号：関所の配り屋。
//
// たまごさん（2026-09-27）：
//   「使ってないタブが開きっぱなしなのは非常に不愉快。出したらしまうを徹底して。」
//   ＝同じ指摘が消えない真因は「フックが tamago-shinchoku 1か所にしか無い」こと。
//     子セッションが joy-relief-station などで走ると、関所を素通りして終われる。
//
// これは何をするか：
//   tools/stop_kanmon/hooks_fragment.json（正本）を読み、
//   渡された各リポジトリの .claude/settings.json に **足りない分だけ足す**。
//   既にあるものは触らない（$kanmon の印で同じ関所かを見分ける）。
//   permissions や他のフックは一切消さない。上書きしない。追記だけ。
//
// 使い方（bashが生きているとき）：
//   node /Users/mac/tamago/tamago-shinchoku/tools/stop_kanmon/install_hooks.mjs \
//     /Users/mac/tamago/tamago-shinchoku \
//     /Users/mac/Desktop/joy-relief-station \
//     ~/.claude            ← ★ここに入れると全リポジトリに効く（真の根治）
//   --dry を付けると書かずに差分だけ出す。
//
// OSには一切触らない（AppleScript / osascript / System Events 全面禁止）。

import { readFileSync, writeFileSync, mkdirSync, existsSync, copyFileSync } from "node:fs";
import path from "node:path";
import os from "node:os";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const FRAGMENT = path.join(HERE, "hooks_fragment.json");

const args = process.argv.slice(2);
const DRY = args.includes("--dry");
let targets = args.filter((a) => !a.startsWith("--"));

// 既定の配り先。ここを増やせば配り先が増える。
if (targets.length === 0) {
  targets = [
    "/Users/mac/tamago/tamago-shinchoku",
    "/Users/mac/Desktop/joy-relief-station",
    path.join(os.homedir(), ".claude"), // ユーザー全体（全リポジトリに効く）
  ];
}

const frag = JSON.parse(readFileSync(FRAGMENT, "utf8"));
const EVENTS = ["PreToolUse", "Stop", "SubagentStop"];

/** その関所が既に入っているか。$kanmon の印か、コマンド文字列のファイル名で見分ける */
function alreadyHas(list, entry) {
  if (!Array.isArray(list)) return false;
  const wantFile = path.basename(
    String(entry.hooks?.[0]?.command || "").split(/\s+/).pop() || "",
  );
  return list.some((e) => {
    if (e?.$kanmon && entry.$kanmon && e.$kanmon === entry.$kanmon) return true;
    const cmds = (e?.hooks || []).map((h) => String(h?.command || ""));
    return cmds.some((c) => wantFile && c.includes(wantFile));
  });
}

let added = 0;
const report = [];

for (const t of targets) {
  // ~/.claude はそれ自体が設定ディレクトリ。リポジトリなら .claude を足す。
  const dir = path.basename(t) === ".claude" ? t : path.join(t, ".claude");
  const file = path.join(dir, "settings.json");
  const repoRoot = path.basename(t) === ".claude" ? path.dirname(t) : t;

  if (!existsSync(repoRoot)) {
    report.push(`- ${t} … 無い（飛ばした）`);
    continue;
  }

  let json = {};
  if (existsSync(file)) {
    try {
      json = JSON.parse(readFileSync(file, "utf8"));
    } catch (e) {
      report.push(`- ${file} … 壊れたJSONなので触らない（${e.message}）`);
      continue;
    }
  }
  json.hooks ||= {};

  const put = [];
  for (const ev of EVENTS) {
    for (const entry of frag[ev] || []) {
      json.hooks[ev] ||= [];
      if (alreadyHas(json.hooks[ev], entry)) continue;
      json.hooks[ev].push(JSON.parse(JSON.stringify(entry)));
      put.push(`${ev}:${entry.$kanmon}`);
    }
  }

  if (put.length === 0) {
    report.push(`- ${file} … 既に入っている（変更なし）`);
    continue;
  }

  if (DRY) {
    report.push(`- ${file} … 足す予定: ${put.join(", ")}`);
    continue;
  }

  mkdirSync(dir, { recursive: true });
  if (existsSync(file)) copyFileSync(file, file + ".bak"); // 消さない。必ず控えを取る
  writeFileSync(file, JSON.stringify(json, null, 2) + "\n");
  added += put.length;
  report.push(`- ${file} … 足した: ${put.join(", ")}`);
}

console.log(
  [
    DRY ? "【下見だけ・書いていない】" : "【配った】",
    ...report,
    ``,
    `足した関所の数: ${added}`,
    `確かめ方: 各リポジトリで空のセッションを1回終わらせ、`,
    `  status/1154_stop_kanmon.jsonl に event:"tab" の行が増えることを見る。`,
    `  タブを1枚開いて閉じずに終わろうとすると exit 2 で止まる＝効いている。`,
  ].join("\n"),
);
