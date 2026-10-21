#!/usr/bin/env node
/**
 * 横相談（Peer Help）— 人へ上げる前に、隣の担当へ振る
 *
 *   npm run role:help -- --ask --from つなげる担当 --need 棚編集UI担当 \
 *     --problem "バッジが保存できない" \
 *     --observed "エラートーストが出る" --observed "ログインは通っている" \
 *     --tried "再読み込み" --tried "別の曲で試した" \
 *     --hypothesis "本番DBに列が無い" --urgency high
 *
 *   npm run role:help                       開いている相談を見る
 *   npm run role:help -- --take <id>        「自分が見ます」と印を付ける
 *   npm run role:help -- --resolve <id> --answer "..."   解決して閉じる
 *
 * ## なぜ要るか（店主指示 2026-08-08）
 *
 * ある担当が**自分の専門外**で詰まった時、いきなり人間へ上げると、
 * 人間が「それは別の担当の話だよ」と振り分けるだけの伝書鳩になる。
 * **店主を伝書鳩にしない。** 詰まった担当が、隣の担当へ直接カードを投げる。
 *
 * ## 詰まった時の順番（この順を飛ばさない）
 *
 *   1. 自己解決を2〜3手試す（もう一度やる／別のやり方／過去を見る）
 *   2. **横相談** ← ここ。他の担当の専門で解ける問題ではないか
 *   3. それでも駄目なら「判断待ち」として記録し、人へ
 *
 * **2を飛ばして3へ行かない。** 専門外の問題を専門外のまま抱えて人へ上げるのが、
 * いちばん時間を溶かす。
 *
 * 保存はJSONだが、**表示は店主が指定したYAMLの形**にしてある
 * （Nodeに標準のYAML解析が無いため、壊れにくいJSONで持ち、読む時だけYAMLに整形する）。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const FILE = path.join(REPO, ".claude/role-help.json");
const REGISTRY = path.join(REPO, ".claude/playbooks/roles.json");

const argv = process.argv.slice(2);
const many = (n) => argv.reduce((a, v, i) => (v === `--${n}` ? [...a, argv[i + 1]] : a), []).filter(Boolean);
const one = (n) => many(n)[0] ?? null;
const has = (n) => argv.includes(`--${n}`);

const db = fs.existsSync(FILE) ? JSON.parse(fs.readFileSync(FILE, "utf8")) : { cards: [] };
const save = () => fs.writeFileSync(FILE, JSON.stringify(db, null, 2), "utf8");
const today = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);

/** 店主が指定したYAMLの形で1枚ぶん出す */
function toYaml(c) {
  const list = (a) => `[${(a ?? []).join(", ")}]`;
  return [
    `task: ${c.task}`,
    `from: ${c.from}`,
    `problem: ${c.problem}`,
    `observed: ${list(c.observed)}`,
    `tried: ${list(c.tried)}`,
    `hypothesis: ${list(c.hypothesis)}`,
    `need: ${c.need}`,
    `urgency: ${c.urgency}`,
    `status: ${c.status}${c.takenBy ? `（${c.takenBy} が対応中）` : ""}`,
    c.answer ? `answer: ${c.answer}` : null,
  ]
    .filter(Boolean)
    .join("\n");
}

/* ---------------------------------------------------------------- 相談を出す */

if (has("ask")) {
  const from = one("from");
  const need = one("need");
  const problem = one("problem");
  if (!from || !need || !problem) {
    console.error("必須: --from <困っている担当> --need <助けてほしい担当> --problem <何が起きているか>");
    process.exit(1);
  }
  // 宛先が実在する担当かを確かめる（存在しない担当へ投げると永遠に拾われない）
  const registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
  const known = registry.roles.some((r) => r.name === need || r.id === need);
  if (!known) {
    console.error(`✗ 「${need}」という担当は台帳にありません。宛先が無い相談は誰にも届きません。`);
    console.error(`  一覧: npm run role -- --list`);
    process.exit(1);
  }
  const tried = many("tried");
  if (tried.length < 1) {
    console.error("✗ --tried が0件です。**自分で試したことを書かずに人へ振らない**（横相談は自己解決の後）。");
    process.exit(1);
  }
  const seq = String(db.cards.length + 1).padStart(3, "0");
  const card = {
    task: one("task") ?? `${(one("slug") ?? "help")}-${seq}`,
    from,
    need,
    problem,
    observed: many("observed"),
    tried,
    hypothesis: many("hypothesis"),
    urgency: one("urgency") ?? "normal",
    status: "open",
    takenBy: null,
    answer: null,
    createdAt: today(),
  };
  db.cards.unshift(card);
  save();
  console.log("助けてカードを出した：\n");
  console.log(toYaml(card));
  console.log(`\n次に ${need} が動く時、または全担当チェックが回る時に拾われる。`);
  process.exit(0);
}

/* ---------------------------------------------------------------- 受ける・閉じる */

if (has("take") || has("resolve")) {
  const id = one("take") ?? one("resolve");
  const card = db.cards.find((c) => c.task === id);
  if (!card) {
    console.error(`✗ そのカードがありません → ${id}`);
    process.exit(1);
  }
  if (has("take")) {
    card.status = "taken";
    card.takenBy = one("by") ?? card.need;
    save();
    console.log(`受けた：${card.task}（${card.takenBy}）`);
  } else {
    const answer = one("answer");
    if (!answer) {
      console.error("✗ --answer が要る。**何をして直ったか**を書かないと、次に同じ相談がまた来る。");
      process.exit(1);
    }
    card.status = "resolved";
    card.answer = answer;
    card.resolvedAt = today();
    save();
    console.log(`閉じた：${card.task}\n${toYaml(card)}`);
  }
  process.exit(0);
}

/* ---------------------------------------------------------------- 一覧 */

const openCards = db.cards.filter((c) => c.status !== "resolved");
const forRole = one("for");
const shown = forRole ? openCards.filter((c) => c.need === forRole) : openCards;

if (has("json")) {
  console.log(JSON.stringify({ open: openCards.length, cards: shown }, null, 2));
  process.exit(0);
}

console.log(`# 横相談（開いている ${openCards.length} 件${forRole ? ` / ${forRole} 宛 ${shown.length} 件` : ""}）\n`);
if (!shown.length) {
  console.log("開いている相談はありません。");
} else {
  const order = { high: 0, normal: 1, low: 2 };
  shown.sort((a, b) => (order[a.urgency] ?? 1) - (order[b.urgency] ?? 1));
  for (const c of shown) {
    console.log("```yaml");
    console.log(toYaml(c));
    console.log("```\n");
  }
  console.log(`受ける: npm run role:help -- --take <task>`);
  console.log(`閉じる: npm run role:help -- --resolve <task> --answer "何をして直ったか"`);
}
