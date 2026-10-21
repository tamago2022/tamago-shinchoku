#!/usr/bin/env node
/**
 * 担当台帳の見回り（ループの Verify 側）
 *
 *   npm run role:check
 *
 * 「担当別プレイブックの仕組みそのもの」が腐っていないかを機械で確かめる。
 * 人間が読む文書は、放っておくと必ず現物とズレる。ズレたまま次のセッションが読むと、
 * 店主がまた同じ説明をやり直すはめになる ＝ この仕組みの目的が壊れる。
 *
 * 落ちる（exit 1）のは「今すぐ直すべき壊れ」だけ。古さや未作成は警告に留める。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const PLAYBOOK_DIR = path.join(REPO, ".claude/playbooks");
const REGISTRY = path.join(PLAYBOOK_DIR, "roles.json");
const STALE_DAYS = 21;

const errors = [];
const warns = [];
const notes = [];

const exists = (rel) => fs.existsSync(path.join(REPO, rel));

/**
 * touch/doNotTouch は「src/lib/foo.ts（〜だけ）」「scripts/x.ts などの…」のような注記付き。
 * 空白・全角括弧・日本語の助詞で切って、パスらしい最初の1語だけを取り出す。
 */
function pathPart(entry) {
  const token = String(entry)
    .split(/[（(\s　]/)[0]
    .replace(/[のを、。]+$/, "")
    .trim();
  return token.includes("/") ? token : null;
}

function checkGlobish(rel) {
  if (!rel.includes("*")) return exists(rel);
  const dir = rel.slice(0, rel.lastIndexOf("/"));
  if (!exists(dir)) return false;
  return true; // ** 指定はディレクトリの存在まで見れば十分
}

/* ---------------------------------------------------------------- 台帳を読む */

let registry;
try {
  registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
} catch (e) {
  console.error(`✗ 台帳が読めない: ${path.relative(REPO, REGISTRY)}\n  ${e.message}`);
  process.exit(1);
}

/* ---------------------------------------------------------------- 1. 台帳 → 現物 */

const ids = new Set();
const declaredPlaybooks = new Set();

for (const role of registry.roles) {
  const where = `roles.json[${role.id}]`;

  if (!role.id || !role.name || !role.mission || !role.done) {
    errors.push(`${where}: id / name / mission / done は必須`);
  }
  if (ids.has(role.id)) errors.push(`${where}: idが重複している`);
  ids.add(role.id);

  if (role.playbook) {
    declaredPlaybooks.add(role.playbook);
    if (!exists(role.playbook)) {
      errors.push(`${where}: プレイブックが台帳に書かれているのに無い → ${role.playbook}`);
    } else {
      const text = fs.readFileSync(path.join(REPO, role.playbook), "utf8");
      const d = (text.match(/最終更新[：:]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/) || [])[1];
      if (!d) {
        warns.push(`${where}: プレイブックに「最終更新：YYYY-MM-DD」の行が無い`);
      } else {
        const days = Math.floor((Date.now() - Date.parse(d)) / 86400000);
        if (days > STALE_DAYS) notes.push(`${role.name}: 現在地メモが${days}日前のまま（${d}）。着手前に鮮度を確かめる`);
      }
      // 雛形のまま放置されていないか（作っただけで中身を埋めていない状態）。
      // 「未確認・要更新」だけを数えると、**正直に未確認と書いた良いメモ**まで誤検知する。
      // 雛形にしか無い言い回し（かっこ書きの説明文）が残っているかで判定する。
      const leftovers = [
        "（前回の方針を確かめてから書く",
        "（何をどこまでmainへ入れたか",
        "（次のセッションが読んで、そのまま着手できる粒度で）",
        "（**実際に踏んだ穴だけ**",
        "（1〜2行。想像で盛らない、実際にmainへ入った分だけ）",
        "（無ければ「特になし」でよい。省略はしない）",
      ].filter((s) => text.includes(s)).length;
      if (leftovers >= 2) {
        notes.push(`${role.name}: 現在地メモが雛形のまま（未記入 ${leftovers} 節）。想像で埋めず、mainと直近コミットから実態を確かめて書く`);
      }
    }
  } else {
    notes.push(`${role.name}: 現在地メモ未作成。作業したら \`npm run role:handoff -- ${role.id} --create\` で作る`);
  }

  for (const n of role.manuals ?? []) {
    const hit = fs.readdirSync(path.join(REPO, ".claude/manuals")).find((f) => f.startsWith(n + "-"));
    if (!hit) errors.push(`${where}: マニュアル ${n} が見つからない`);
  }
  for (const f of [...(role.docs ?? []), ...(role.skills ?? [])]) {
    if (!exists(f)) errors.push(`${where}: 参照先が無い → ${f}`);
  }
  for (const f of [...(role.touch ?? []), ...(role.doNotTouch ?? [])]) {
    const p = pathPart(f);
    if (p && !checkGlobish(p)) warns.push(`${where}: touch/doNotTouch の場所が無い → ${p}`);
  }
  for (const cmd of role.verify ?? []) {
    const script = (cmd.match(/(scripts\/[\w./-]+)/) || [])[1];
    if (script && !exists(script)) warns.push(`${where}: 検品コマンドの実体が無い → ${script}`);
  }
  if (!(role.aliases ?? []).length) {
    warns.push(`${where}: aliasesが空。店主は音声入力なので表記ゆれを1つ以上入れる`);
  }
}

for (const f of registry.alwaysRead ?? []) {
  if (!exists(f)) errors.push(`roles.json[alwaysRead]: 参照先が無い → ${f}`);
}

/* ---------------------------------------------------------------- 2. 現物 → 台帳 */

const actual = fs
  .readdirSync(PLAYBOOK_DIR)
  .filter((f) => f.endsWith(".md") && f !== "README.md")
  .map((f) => `.claude/playbooks/${f}`);

for (const f of actual) {
  if (!declaredPlaybooks.has(f)) {
    warns.push(`プレイブックが台帳に載っていない → ${f}（roles.json に担当を1件足す）`);
  }
}

/* ---------------------------------------------------------------- 3. README の一覧（任意） */

// 【汎用版】README.md はプロジェクト側で用意しなくても動く（無ければこの節は丸ごと飛ばす）。
const READMEPATH = path.join(PLAYBOOK_DIR, "README.md");
if (fs.existsSync(READMEPATH)) {
  const readme = fs.readFileSync(READMEPATH, "utf8");
  for (const f of actual) {
    const base = path.basename(f);
    const times = readme.split("`" + base + "`").length - 1;
    if (times === 0) warns.push(`README.md の一覧に載っていない → ${base}`);
    // 一覧に二重で載る事故を実際にやった（追記スクリプトの重ね掛け）。人の目では気づきにくい。
    if (times > 1) warns.push(`README.md の一覧に${times}回載っている → ${base}`);
  }
  // 「まだ現在地メモが無い担当（…）」の括弧の中に、実在するメモの担当が残っていないか
  const notYet = (readme.match(/まだ現在地メモが無い担当（([^）]*)）/) || [])[1] ?? "";
  for (const role of registry.roles) {
    if (!role.playbook || !exists(role.playbook)) continue;
    const short = role.name.replace(/担当$|・.*$/g, "");
    if (short && notYet.includes(short)) {
      warns.push(`README.md の「まだ現在地メモが無い担当」に ${role.name} が残っている（もう在る）`);
    }
  }
} else {
  notes.push("README.md が無いため一覧との整合性チェックは省略（任意ファイル）");
}

/* ---------------------------------------------------------------- 4. 別名の衝突 */

const seen = new Map();
const norm = (s) =>
  String(s).normalize("NFKC").toLowerCase().replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60)).replace(/[ー・\s　_/-]/g, "");
for (const role of registry.roles) {
  for (const a of [role.id, role.name, ...(role.aliases ?? [])]) {
    const k = norm(a);
    if (seen.has(k) && seen.get(k) !== role.id) {
      errors.push(`別名「${a}」が ${seen.get(k)} と ${role.id} で重複している（どちらに振るか決められない）`);
    }
    seen.set(k, role.id);
  }
}

/* ---------------------------------------------------------------- 出力 */

console.log(`# 担当台帳の見回り（担当 ${registry.roles.length} 件 / プレイブック ${actual.length} 本）\n`);
errors.forEach((e) => console.log(`✗ ${e}`));
warns.forEach((w) => console.log(`△ ${w}`));
notes.forEach((n) => console.log(`・${n}`));

if (!errors.length && !warns.length) console.log("問題なし。");
console.log(`\n合計: 壊れ ${errors.length} / 要確認 ${warns.length} / お知らせ ${notes.length}`);

process.exit(errors.length ? 1 : 0);
