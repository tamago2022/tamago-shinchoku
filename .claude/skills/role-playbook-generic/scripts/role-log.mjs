#!/usr/bin/env node
/**
 * 巡回の実行ログを1件追記する
 *
 *   npm run role:log -- --role つなげる担当 --done "..." --wait "..." --issue "..."
 *   npm run role:log -- --role 見回り担当 --done "現在地メモを作った" --next "詰まり見回りの停止監視を確認"
 *
 * 書き先は `.claude/role-sweep-log.md`（新しいものが上）。
 *
 * ## なぜログをファイルに残すか
 *
 * 定期実行は「毎回まっさらなセッション」から呼ばれる。**前回何をやったかを覚えている
 * 主体が存在しない。** 覚えているのはファイルだけ。ここが空だと、毎回同じ担当の
 * 同じ次の一手を掘り返して永遠に前へ進まない。
 *
 * 記録は店主の指示どおり **完了／問題／判断待ち** の3分類だけ。
 * ルーティンな途中経過は書かない（読む人の時間を奪うため）。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const LOG = path.join(REPO, ".claude/role-sweep-log.md");

const HEADER = `# 巡回の実行ログ

\`npm run role -- 全担当チェック\` → 1件進める → ここへ1行残す、の記録。**新しいものが上。**

このファイルは**次に巡回が動いた時の唯一の引き継ぎ元**。定期実行は毎回まっさらな
セッションから呼ばれるので、前回を覚えている主体はここしかない。

分類は3つだけ。**完了**＝終わって検証済み／**問題**＝壊れているが手が出せる／
**判断待ち**＝店主の判断が要る（不可逆な操作・公開・削除・課金・好みの判断）。

---
`;

function arg(name) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : null;
}

const today = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

const role = arg("role") ?? "（担当不明）";
const done = arg("done");
const issue = arg("issue");
const wait = arg("wait");
const next = arg("next");
const commit = arg("commit");

if (!done && !issue && !wait) {
  console.error(
    "使い方: npm run role:log -- --role <担当名> [--done <完了>] [--issue <問題>] [--wait <判断待ち>] [--next <次の一手>] [--commit <ID>]",
  );
  process.exit(1);
}

const lines = [`## ${today()}　${role}`, ""];
if (done) lines.push(`- **完了**：${done}${commit ? `（\`${commit}\`）` : ""}`);
if (issue) lines.push(`- **問題**：${issue}`);
if (wait) lines.push(`- **判断待ち**：${wait}`);
if (next) lines.push(`- 次回ここから：${next}`);
lines.push("");

let body = fs.existsSync(LOG) ? fs.readFileSync(LOG, "utf8") : HEADER;
if (!body.startsWith("# 巡回の実行ログ")) body = HEADER + body;

const marker = "---\n";
const at = body.indexOf(marker) + marker.length;
const updated = body.slice(0, at) + "\n" + lines.join("\n") + body.slice(at);

fs.writeFileSync(LOG, updated, "utf8");
console.log(`記録した → .claude/role-sweep-log.md（${role}）`);
