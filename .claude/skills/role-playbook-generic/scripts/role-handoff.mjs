#!/usr/bin/env node
/**
 * 引き継ぎ雛形（ループの Complete 側）
 *
 *   npm run role:handoff -- 気分診断            雛形を表示するだけ
 *   npm run role:handoff -- 気分診断 --create   プレイブックが無い時だけ作る
 *   npm run role:handoff -- 気分診断 --stamp    「最終更新」を今日に打ち直す
 *
 * セッションは必ず切れる。切れる前に「今の方針・直近の決定・次にやること」の3点だけ
 * 現在地メモへ落としておけば、次のセッションは店主に説明させずに再開できる。
 *
 * 安全のため、既存ファイルを上書きしない（--create は無い時だけ作る。--stamp は日付行1行だけ書き換える）。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const REGISTRY = path.join(REPO, ".claude/playbooks/roles.json");
// 日本時間の今日（toISOString はUTCなので、朝9時前だと前日になってしまう）
const TODAY = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

const norm = (s) =>
  String(s ?? "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[ー・\s　_/-]/g, "")
    .replace(/(担当|たんとう|係|がかり|さん)$/g, "");

const registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
const args = process.argv.slice(2);
const query = args.filter((a) => !a.startsWith("--")).join(" ");
const doCreate = args.includes("--create");
const doStamp = args.includes("--stamp");

if (!query) {
  console.error("使い方: npm run role:handoff -- <担当名> [--create|--stamp]");
  process.exit(1);
}

const q = norm(query);
const role =
  registry.roles.find((r) => [r.id, r.name, ...(r.aliases ?? [])].map(norm).includes(q)) ??
  registry.roles.find((r) => [r.id, r.name, ...(r.aliases ?? [])].map(norm).some((k) => k.includes(q) || q.includes(k)));

if (!role) {
  console.error(`「${query}」に当たる担当が見つかりません。\`npm run role -- --list\` で一覧が出ます。`);
  process.exit(1);
}

const rel = role.playbook ?? `.claude/playbooks/${role.name}.md`;
const abs = path.join(REPO, rel);

const template = `# ${role.name}・現在地

最終更新：${TODAY}

**恒久ルールの正本は${(role.manuals ?? []).map((n) => `\`.claude/manuals/${n}-*\``).join("／") || "`AGENTS.md`／`CLAUDE.md`"}。ここには複製しない。** このファイルは「今の方針・直近の決定・次にやること」だけの現在地メモ。

> **書き方の絶対ルール：確かめていないことを書かない。**
> 分からない項目は空欄にせず **「未確認・要更新」** と正直に書く。推測を書くなら
> 「推測：〜（未確認）」と明示する。**推測すること自体は禁止しない。推測を確認済みと偽ることを禁止する。**
> ここは次のセッションが事実として信じて動く場所なので、間違った既成事実は事故に直結する。

## この担当は何をする人か

${role.mission}

## 今の方針

- 未確認・要更新（前回の方針を確かめてから書く。変わっていなければ「前回から変更なし」でよい）

## 直近の決定・実装（${TODAY}）

- 未確認・要更新（何をどこまでmainへ入れたか。**コミットIDか実URLで裏を取ってから書く**）

## 次にやること

1. 未確認・要更新（次のセッションが読んで、そのまま着手できる粒度で）

## 引っかかった穴（次の担当が同じ穴に落ちないように）

- 未確認・要更新（**実際に踏んだ穴だけ**。原因と、なぜ起きたかを1行ずつ。詳細は \`.claude/GOOD_PATTERNS.md\` 側へ）

## 辞める担当の自己評価（このセッションが去る前に自分で書く）

- 成績：（◎/○/△/✗のいずれかを自分で付ける。理由を1行）
- 何をどこまで進めたか（1〜2行。想像で盛らない、実際にmainへ入った分だけ）
- 次の代へ伝えたいこと（無ければ「特になし」でよい。省略はしない）

## 次の代（ここは書かない。次にこの担当へ就いたセッションが着任時に埋める欄）

- 着任日：未記入
- 引き継ぎ（上の「辞める担当の自己評価」含む）を読んだか：未記入
- 着任時に気づいたこと：未記入
`;

if (doCreate) {
  if (fs.existsSync(abs)) {
    console.error(`✗ すでにある。上書きしない → ${rel}\n  中身を足すなら直接編集するか --stamp を使う。`);
    process.exit(1);
  }
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, template, "utf8");
  console.log(`作成した → ${rel}`);
  console.log(`次: この中身を今日の作業で埋め、roles.json の "${role.id}" の playbook を "${rel}" にし、README.md の一覧にも1行足す。`);
  console.log(`確認: npm run role:check`);
  process.exit(0);
}

if (doStamp) {
  if (!fs.existsSync(abs)) {
    console.error(`✗ まだ無い → ${rel}（--create で作る）`);
    process.exit(1);
  }
  const text = fs.readFileSync(abs, "utf8");
  if (!/最終更新[：:]\s*[0-9]{4}-[0-9]{2}-[0-9]{2}/.test(text)) {
    console.error(`✗ 「最終更新：YYYY-MM-DD」の行が無いので打ち直せない → ${rel}`);
    process.exit(1);
  }
  fs.writeFileSync(abs, text.replace(/最終更新[：:]\s*[0-9]{4}-[0-9]{2}-[0-9]{2}/, `最終更新：${TODAY}`), "utf8");
  console.log(`最終更新を ${TODAY} にした → ${rel}`);
  process.exit(0);
}

console.log(`# ${role.name} の引き継ぎ（${fs.existsSync(abs) ? "既存: " : "未作成: "}${rel}）\n`);
console.log("終わる前にやること（3つだけ）:");
console.log(`  1. ${rel} の「次にやること」を書き換える`);
console.log(`  2. .claude/ACTIVE_WORK.md の自分の行を更新または削除する`);
console.log(`  3. 新しい事故・恒久ルールがあれば .claude/playbooks/roles.json の traps に1行足す`);
console.log(`\n--- 雛形（${fs.existsSync(abs) ? "参考。既存ファイルは上書きしない" : "--create で作れる"}）---\n`);
console.log(template);
