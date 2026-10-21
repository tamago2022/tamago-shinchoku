#!/usr/bin/env node
/**
 * 担当ブリーフ生成（担当別プレイブックの入口）
 *
 *   npm run role -- 気分診断
 *   npm run role -- つなげる
 *   npm run role -- --list
 *   npm run role -- パーソナライズ --json
 *
 * 目的：依頼者（店主・PM・自分自身）が同じ説明を二度三度しなくて済むようにする。
 * 担当名を1語渡すだけで、「読むもの・触る場所・触らない場所・今の現在地・
 * 他セッションとの衝突・落とし穴・検品コマンド・完成条件・報告形式」が1枚で出る。
 *
 * 正本は `.claude/playbooks/roles.json`（恒久情報）と
 * `.claude/playbooks/<担当名>.md`（今の現在地）。このスクリプトは読むだけで、何も書き換えない。
 *
 * ── このファイルはどのリポジトリにも依存しない汎用版 ──
 * `joy-relief-station`固有の文言（店主／Lovable等）は出力テキストの慣用句として一部残る場合があるが、
 * ロジックは `registry`（roles.json）の内容だけで動く。`completionStages` を registry に書けば
 * 「完了は何段階か」の文言も自分のプロジェクト用に差し替えられる（未指定なら汎用デフォルトを使う）。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const REGISTRY = path.join(REPO, ".claude/playbooks/roles.json");

/** 日本時間の今日（toISOString はUTCなので、朝9時前だと前日になってしまう） */
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/* ------------------------------------------------------------------ 表記ゆれ吸収 */

/**
 * 店主は音声入力なので表記がゆれる（カタカナ／ひらがな／「担当」有無／伸ばし棒）。
 * 比較用に平たくする。
 */
function normalize(s) {
  return String(s ?? "")
    .normalize("NFKC")
    .toLowerCase()
    // カタカナ → ひらがな
    .replace(/[ァ-ヶ]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0x60))
    .replace(/[ー・\s　_/-]/g, "")
    .replace(/(担当|たんとう|係|がかり|さん|の仕事|まわり)$/g, "");
}

function resolveRole(registry, query) {
  const q = normalize(query);
  if (!q) return null;
  const scored = [];
  for (const role of registry.roles) {
    const keys = [role.id, role.name, ...(role.aliases ?? [])].map(normalize);
    if (keys.includes(q)) return { role, how: "完全一致" };
    for (const k of keys) {
      if (!k) continue;
      if (k.startsWith(q) || q.startsWith(k)) scored.push({ role, how: "前方一致", len: k.length });
      else if (k.includes(q) || q.includes(k)) scored.push({ role, how: "部分一致", len: k.length });
    }
  }
  if (!scored.length) return null;
  // 前方一致を優先し、同順位なら短い（＝具体的な）語を優先
  scored.sort((a, b) => (a.how === b.how ? a.len - b.len : a.how === "前方一致" ? -1 : 1));
  return { role: scored[0].role, how: scored[0].how };
}

/* ------------------------------------------------------------------ 補助 */

const exists = (rel) => fs.existsSync(path.join(REPO, rel));
const readIf = (rel) => (exists(rel) ? fs.readFileSync(path.join(REPO, rel), "utf8") : null);
const mark = (rel) => `${exists(rel) ? "  " : "⚠ "}${rel}${exists(rel) ? "" : "（見つからない）"}`;

/** プレイブックから「今の方針 / 直近の決定 / 次にやること」だけを抜く */
function playbookDigest(rel) {
  const text = readIf(rel);
  if (text == null) return null;
  const updated = (text.match(/最終更新[：:]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/) || [])[1] ?? null;
  const blocks = [];
  const lines = text.split("\n");
  let current = null;
  for (const line of lines) {
    const h = line.match(/^##\s+(.*)$/);
    if (h) {
      if (current) blocks.push(current);
      current = { title: h[1].trim(), body: [] };
      continue;
    }
    if (current) current.body.push(line);
  }
  if (current) blocks.push(current);
  // 拾う節。**常設の施策（例「プチ物語」）は見出しが自由なので、
  // 中に「設計思想」「次の一手」がある節も拾う。** ここを狭くすると、
  // 一番新しくて一番大事な方針がブリーフに出ないまま次の担当が着手する。
  const want = /次にやること|直近の決定|今の方針|進行中|残件|設計思想|次の一手|常設/;
  const picked = blocks.filter(
    (b) => want.test(b.title) || want.test(b.body.slice(0, 60).join("\n")),
  );
  return { updated, blocks: picked.length ? picked : blocks.slice(0, 1) };
}

/** ACTIVE_WORK.md の「占有中」表から、衝突しそうな行を拾う */
function conflicts(role) {
  const text = readIf(".claude/ACTIVE_WORK.md");
  if (!text) return [];
  const section = text.split("## 占有中")[1]?.split(/\n## /)[0] ?? "";
  const needles = [
    role.name,
    ...(role.aliases ?? []),
    ...(role.touch ?? []).map((t) => path.basename(t.split("（")[0].trim())),
  ]
    .map((s) => String(s).trim())
    .filter((s) => s.length >= 3);

  const rows = [];
  for (const line of section.split("\n")) {
    if (!line.startsWith("|") || line.includes("---") || line.includes("開始日")) continue;
    const hit = needles.find((n) => line.includes(n));
    if (!hit) continue;
    const cells = line.split("|").map((c) => c.trim());
    rows.push({ owner: cells[2] ?? "?", branch: cells[3] ?? "?", hit });
  }
  return rows;
}

/**
 * 自分宛のメールボックス（`.claude/mailbox/<担当名>.md`）から未対応の伝言を拾う。
 * 担当セッション同士の非同期の直接連絡（店主指示 2026-08-12「また活発にやってほしい」）。
 * 詳しい運用ルールは `.claude/mailbox/README.md`。ここは読むだけで、何も書き換えない。
 */
function mailboxDigest(role) {
  const rel = `.claude/mailbox/${role.name}.md`;
  const text = readIf(rel);
  if (text == null) return { rel, exists: false, body: null };
  const section = text.split(/^## 未対応（新着）\s*$/m)[1]?.split(/\n## /)[0] ?? "";
  const trimmed = section.trim();
  const isEmpty = !trimmed || trimmed.includes("（まだ伝言はありません）");
  return { rel, exists: true, empty: isEmpty, body: isEmpty ? null : trimmed };
}

/** KNOWN_ISSUES.md の未解決見出しのうち、この担当に関係しそうなもの */
function knownIssues(role) {
  const text = readIf(".claude/KNOWN_ISSUES.md");
  if (!text) return [];
  const unresolved = text.split("## 未解決")[1]?.split(/\n## /)[0] ?? "";
  const needles = [role.name, ...(role.aliases ?? [])].filter((s) => s.length >= 2);
  return unresolved
    .split("\n")
    .filter((l) => l.startsWith("### "))
    .map((l) => l.replace(/^###\s+/, "").trim())
    .filter((title) => needles.some((n) => title.includes(n)) || role.id === "perf" || role.id === "patrol");
}

/* ------------------------------------------------------------------ 出力 */

function printList(registry) {
  console.log("# 担当一覧（`npm run role -- <名前>` で開く）\n");
  for (const r of registry.roles) {
    const pb = r.playbook && exists(r.playbook) ? "現在地あり" : "現在地メモ未作成";
    console.log(`- ${r.name}（${r.id}）… ${r.mission}`);
    console.log(`    別名: ${(r.aliases ?? []).slice(0, 6).join(" / ")}`);
    console.log(`    ${pb}\n`);
  }
}

function printBrief(registry, role, how) {
  const out = [];
  const p = (s = "") => out.push(s);

  p(`# ${role.name} ブリーフ（${today()} 生成・照合: ${how}）`);
  p();
  p(`## この担当は何をする人か`);
  p(role.mission);
  p();

  p(`## 1. 読むもの（この順に読む）`);
  p("### 共通コア（全担当）");
  registry.alwaysRead.forEach((f) => p(mark(f)));
  p();
  p("### この担当のもの");
  if (role.playbook) p(mark(role.playbook) + "  ← 今の現在地。ここから読む");
  (role.manuals ?? []).forEach((n) => {
    const hit = fs
      .readdirSync(path.join(REPO, ".claude/manuals"))
      .find((f) => f.startsWith(n + "-"));
    p(hit ? mark(`.claude/manuals/${hit}`) : `⚠ .claude/manuals/${n}-*（見つからない）`);
  });
  (role.docs ?? []).forEach((f) => p(mark(f)));
  (role.skills ?? []).forEach((f) => p(mark(f)));
  p();

  const digest = role.playbook ? playbookDigest(role.playbook) : null;
  p(`## 2. 今の現在地`);
  if (!digest) {
    p("この担当のプレイブックはまだ無い。＝**現在地は未確認**。進捗ゼロという意味ではない。");
    p("→ まず最新main・直近コミット・作業ブランチ・ACTIVE_WORKから実態を確かめる。");
    p("→ 今回の作業が終わる時に `.claude/playbooks/" + role.name + ".md` を作り、");
    p("   「今の方針」「直近の決定」「次にやること」の3点だけ書き残す（`npm run role:handoff -- " + role.id + " --create` が雛形を出す）。");
    p("→ **確かめていないことを書かない。分からない項目は「未確認・要更新」と正直に書く。**");
    p("   推測すること自体は禁止しない。推測を確認済みと偽ることを禁止する。");
  } else {
    p(`（最終更新: ${digest.updated ?? "不明"}）`);
    for (const b of digest.blocks) {
      p();
      p(`### ${b.title}`);
      p(b.body.join("\n").trim());
    }
  }
  p();

  p(`## 3. 触ってよい場所 / 触ってはいけない場所`);
  (role.touch ?? []).forEach((f) => p(`  触る　　: ${f}`));
  (role.doNotTouch ?? []).forEach((f) => p(`  触らない: ${f}`));
  p();

  const conf = conflicts(role);
  p(`## 4. 他セッションとの衝突（.claude/ACTIVE_WORK.md 占有中）`);
  if (!conf.length) p("  該当なし。作業開始前に自分の行を追記すること。");
  else conf.forEach((c) => p(`⚠ ${c.owner} / ${c.branch}（「${c.hit}」で一致）`));
  p();

  // 5番以降は「既知の未解決」節の有無で個数が変わるため、通し番号は変数で数える。
  let n = 5;

  const mailbox = mailboxDigest(role);
  p(`## ${n++}. 自分宛のメールボックス（${mailbox.rel}）`);
  if (!mailbox.exists) p(`  ⚠ ${mailbox.rel}（見つからない。.claude/mailbox/README.md を参照）`);
  else if (mailbox.empty) p("  新着の伝言なし。");
  else {
    p("  他の担当セッションからの伝言。読んだら該当ファイルの「対応済み」へ移動すること。");
    p();
    p(mailbox.body);
  }
  p();

  const issues = knownIssues(role);
  if (issues.length) {
    p(`## ${n++}. 既知の未解決（.claude/KNOWN_ISSUES.md）— 新しいバグとして報告し直さない`);
    issues.forEach((t) => p(`  ・${t}`));
    p();
  }

  p(`## ${n++}. この担当が過去に落ちた穴`);
  (role.traps ?? []).forEach((t) => p(`  ・${t}`));
  p();

  p(`## ${n++}. 担当外でも必ず守る憲法`);
  registry.crossCuttingLaws.forEach((l) => p(`  ・${l.title} — ${l.summary}`));
  p();

  p(`## ${n++}. 検品（自己申告ではなく、これを実際に走らせる）`);
  if (!(role.verify ?? []).length) p("  自動検品コマンドは無い。実画面・実URLでの確認を検品とする。");
  else (role.verify ?? []).forEach((v) => p(`  $ ${v}`));
  p("  $ bash scripts/verify-project.sh   ← 変更がコードに及ぶ場合");
  p();

  p(`## ${n++}. 完成条件`);
  p(`  ${role.done}`);
  const stages = registry.completionStages ?? ["実装・自動検品", "PR作成", "mainへMerged", "本番反映＋依頼者の実画面合格"];
  p(`  完了は${stages.length}段階。` + stages.map((s, i) => `${i + 1}${s}`).join(" "));
  if (role.branchHint) p(`  この担当の通常ブランチ: ${role.branchHint}`);
  p();

  p(`## ${n++}. 報告の型（これ以外を並べない）`);
  registry.reportFormat.forEach((f) => p(`  ${f}`));
  p();
  p(`## 終わる前に必ず`);
  p(`  1. ${role.playbook ?? ".claude/playbooks/" + role.name + ".md"} の「次にやること」を書き換える`);
  p(`  2. .claude/ACTIVE_WORK.md の自分の行を更新または削除する`);
  p(`  3. 新しい恒久ルール・事故があれば ${path.relative(REPO, REGISTRY)} の traps に1行足す`);
  p(`  4. 作業中に担当外の気づきがあれば ${mailbox.rel.replace(role.name, "<相手の担当名>")} へ一言添える（.claude/mailbox/README.md）`);

  console.log(out.join("\n"));
}

/* ------------------------------------------------------------------ main */

async function main() {
  const args = process.argv.slice(2);
  const registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
  const asJson = args.includes("--json");
  const query = args.filter((a) => !a.startsWith("--")).join(" ");

  // 「全担当チェック」は担当名ではなく巡回の合図。1担当ではなく全部を見る方へ回す。
  // 【注意】比較は必ず normalize() を通した形どうしで行う。normalize はカタカナをひらがなに
  // 直すので、ここに「全担当チェック」とカタカナのまま書くと一生一致しない（実際にやった）。
  const SWEEP_WORDS = ["全担当チェック", "全担当", "ぜんたんとうチェック", "ぜんたんとう", "全部チェック", "巡回", "一斉点検", "sweep", "all"].map(
    normalize,
  );
  if (SWEEP_WORDS.includes(normalize(query))) {
    await import("./role-sweep.mjs");
    return;
  }

  if (args.includes("--list") || !query) {
    if (asJson) {
      console.log(JSON.stringify(registry.roles.map(({ id, name, aliases, mission }) => ({ id, name, aliases, mission })), null, 2));
    } else {
      printList(registry);
      if (!query) console.log("使い方: npm run role -- <担当名>");
    }
    return;
  }

  const found = resolveRole(registry, query);
  if (!found) {
    console.error(`「${query}」に当たる担当が見つかりません。\n`);
    printList(registry);
    process.exitCode = 1;
    return;
  }

  if (asJson) {
    console.log(
      JSON.stringify(
        {
          ...found.role,
          matchedBy: found.how,
          alwaysRead: registry.alwaysRead,
          crossCuttingLaws: registry.crossCuttingLaws,
          reportFormat: registry.reportFormat,
          conflicts: conflicts(found.role),
          knownIssues: knownIssues(found.role),
          playbookDigest: found.role.playbook ? playbookDigest(found.role.playbook) : null,
          mailbox: mailboxDigest(found.role),
        },
        null,
        2,
      ),
    );
    return;
  }

  printBrief(registry, found.role, found.how);
}

await main();
