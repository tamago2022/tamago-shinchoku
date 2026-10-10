#!/usr/bin/env node
// Vault の関所（2026-10-11）PreToolUse：Bash / Write / Edit / MultiEdit / NotebookEdit
//
// たまごさん：「Obsidian が重くならないことが第一。特にスマホで読み込みが遅くなっているのは確か。
//   毎回書き込みが入るから、どうにかして」
// 判定の正本は tools/vault_kanmon.py（--hook）。ここは標準入力をそのまま渡すだけ＝基準を2か所に持たない。
//   ・Vault の外へ移した台帳・ログ（作業キュー.md 等・AI出力/仕入れ/）へ書こうとしたら exit 2（新しい場所を教える）
//   ・00_現在地.md は AI が直接書けるのは1日1回まで（それ以降は status/genzaichi_kouho.md へ）
//   ・それ以外の Vault への AI の書き込みは1日20回まで
// 判定が壊れていたら黙って通す（exit 0）。人質にしない。逆テスト：python3 tools/vault_kanmon.py --self-test
import { spawnSync } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const PY = path.join(REPO, "tools", "vault_kanmon.py");

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 3000);
});
if (!stdin.includes("tamago_brain")) process.exit(0);
try {
  const r = spawnSync("python3", [PY, "--hook"], { input: stdin, encoding: "utf8", timeout: 15000 });
  if (r.status === 2) {
    process.stderr.write(r.stderr || "★Vault への書き込みを止めた（Vault の関所）\n");
    process.exit(2);
  }
} catch {}
process.exit(0);
