#!/usr/bin/env node
/**
 * 全担当チェック（無人巡回の目）
 *
 *   npm run role -- 全担当チェック      人が読む形
 *   npm run role:sweep -- --json        機械が読む形（定期実行はこちら）
 *   npm run role:sweep -- --pick        次に進めるべき担当を1つだけ出す
 *
 * ## 設計の要（前の自動巡回が壊れた理由への回答）
 *
 * 以前の `joy-relief-station-fleet-driver` は「生きている特定のセッションに
 * 話しかけ続ける」作りだった。**対象セッションが消えた時点で全部止まった。**
 *
 * この巡回は **セッションの生死に一切依存しない。**
 *   - 読むのはファイルだけ（現在地メモ・台帳・調整ボード）。
 *   - 誰かが動いているかは見ない。**残っている仕事があるかだけを見る。**
 *   - 出力もファイルへ落ちる。次に誰が呼んでも、前回の続きが分かる。
 *   - 送信手段・常駐プロセス・セッションIDを一切持たない＝壊れる部品が無い。
 *
 * このコマンド自体は**何も変更しない（読み取り専用）。**
 * 実際に手を動かすのは、これを呼んだセッション側の仕事。
 */
import fs from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const REGISTRY = path.join(REPO, ".claude/playbooks/roles.json");

/** これ以上放置されたら「古い」とみなす日数 */
const STALE_DAYS = 21;
/** 現在地メモが無い担当を、どれくらい重く見るか */
const NO_PLAYBOOK_WEIGHT = 40;

const today = () =>
  new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const exists = (rel) => fs.existsSync(path.join(REPO, rel));
const readIf = (rel) => (exists(rel) ? fs.readFileSync(path.join(REPO, rel), "utf8") : null);

/* ---------------------------------------------------------------- 現在地メモを読む */

/**
 * 「次にやること」「次の一手」の節から、残っている項目を数える。
 * 見出しの書き方は担当ごとに自由なので、番号付き・箇条書きの両方を拾う。
 */
function readNextMoves(rel) {
  const text = readIf(rel);
  if (text == null) return null;

  const updated = (text.match(/最終更新[：:]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})/) || [])[1] ?? null;

  // 「次にやること」「次の一手」を含む見出し（## でも ### でも）から次の見出しまで
  const sections = [];
  const lines = text.split("\n");
  let cur = null;
  for (const line of lines) {
    const h = line.match(/^(#{2,4})\s+(.*)$/);
    if (h) {
      if (cur) sections.push(cur);
      // 見出しの書き方は担当ごとに自由（「次にやること」「次の一手」「次にやると効きそうなこと」…）。
      // ここを狭くすると**残件があるのに0件と報告する**＝巡回が嘘をつく。実際に
      // 「次にやると効きそうなこと」を取りこぼしてパーソナライズ担当を0件と誤報した。
      cur = /次に|次の一手|残件|やり残|todo/i.test(h[2]) ? { title: h[2].trim(), body: [] } : null;
      continue;
    }
    if (cur) cur.body.push(line);
  }
  if (cur) sections.push(cur);

  const items = [];
  for (const s of sections) {
    for (const raw of s.body) {
      const l = raw.trim();
      // 「1. 〜」「- 〜」だけを項目とみなす。入れ子の説明行（3スペース以上）は数えない
      if (!/^(\d+\.|[-*])\s+\S/.test(l)) continue;
      if (/^\s{3,}/.test(raw)) continue;
      if (/^[-*]\s*\[x\]/i.test(l)) continue; // 済みは数えない
      items.push(l.replace(/^(\d+\.|[-*])\s+/, "").trim());
    }
  }

  // 「未着手」「未設計」「未確認」「まだ無い」は、まだ手が付いていない印
  const notStarted = items.filter((i) => /未着手|未設計|未確認|まだ無い|未実装/.test(i)).length;

  return { updated, items, notStarted };
}

/** 雛形のまま埋められていない現在地メモか */
function looksLikeTemplate(rel) {
  const text = readIf(rel);
  if (text == null) return false;
  return /（次のセッションが読んで、そのまま着手できる粒度で）|（変わっていなければ「前回から変更なし」でよい）|（1〜2行。想像で盛らない、実際にmainへ入った分だけ）|（無ければ「特になし」でよい。省略はしない）/.test(
    text,
  );
}

/* ---------------------------------------------------------------- 判定 */

function assess(role) {
  const out = {
    id: role.id,
    name: role.name,
    priority: role.sweepPriority ?? 5,
    playbook: role.playbook ?? null,
    hasPlaybook: Boolean(role.playbook && exists(role.playbook)),
    updated: null,
    ageDays: null,
    openItems: 0,
    notStartedItems: 0,
    nextMove: null,
    flags: [],
    score: 0,
  };

  if (!out.hasPlaybook) {
    out.flags.push("現在地メモが無い（＝現在地未確認。進捗ゼロという意味ではない）");
    out.nextMove = `実態を調べて .claude/playbooks/${role.name}.md を作る（npm run role:handoff -- ${role.id} --create）`;
    out.score = NO_PLAYBOOK_WEIGHT + (10 - out.priority);
    return out;
  }

  const nm = readNextMoves(role.playbook);
  out.updated = nm.updated;
  if (nm.updated) {
    out.ageDays = Math.floor((Date.parse(today()) - Date.parse(nm.updated)) / 86400000);
  }
  out.openItems = nm.items.length;
  out.notStartedItems = nm.notStarted;
  out.nextMove = nm.items[0] ?? null;

  if (looksLikeTemplate(role.playbook)) {
    out.flags.push("雛形のまま埋まっていない");
    out.score += 30;
  }
  if (!nm.updated) out.flags.push("最終更新の行が無い");
  if (out.ageDays != null && out.ageDays > STALE_DAYS) {
    out.flags.push(`${out.ageDays}日放置されている`);
    out.score += Math.min(25, out.ageDays - STALE_DAYS);
  }
  if (out.openItems === 0) {
    out.flags.push("次の一手が書かれていない（終わったのか、書き忘れたのか不明）");
    out.score += 15;
  }

  // 残件があるほど、優先度が高いほど、古いほど上に来る
  out.score += Math.min(20, out.openItems * 4);
  out.score += (10 - out.priority) * 2;
  if (out.ageDays != null) out.score += Math.min(10, out.ageDays);

  return out;
}

/* ---------------------------------------------------------------- 実行 */

/* ---------------------------------------------------------------- 担当ごとの自動点検 */

/**
 * 現在地メモを読むだけでは分からない「担当の持ち場の実害」を、その場で機械に見せる。
 *
 * 元ネタ（joy-relief-station・店主指摘 2026-08-08）：仕入れ担当が入れた若いバンドのCome Togetherが、
 * 他のCome Togetherと繋がっていなかった。それを店主が偶然見つけて指摘する形になった。
 * 「これつながってないよ」と毎回言わせるのではなく、担当が自分で気づく仕組みにした。
 *
 * 【汎用版】どの担当にどの点検コマンドを当てるかはプロジェクトごとに全く違うため、
 * ここにハードコードしない。`registry.autoChecks`（配列）が無ければ何もしない（安全側）。
 * 各要素のスキーマ： { "role": "担当名", "what": "何を見るか", "cmd": "実行コマンド",
 *   "jsonField": "jsonの出力から拾うキー（省略可。省略時は終了コードだけで判定）" }
 */
function runAutoChecks() {
  const checks = (registry.autoChecks ?? []).map((c) => ({
    role: c.role,
    what: c.what,
    cmd: c.cmd,
    read: c.jsonField
      ? (json) => ({
          found: json[c.jsonField] ?? 0,
          detail: (json[c.jsonField] ?? 0) > 0 ? `検出 ${json[c.jsonField]}件` : "検出なし",
        })
      : null,
  }));

  const out = [];
  for (const c of checks) {
    try {
      const raw = execSync(c.cmd, { cwd: REPO, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
      let found = 0;
      let detail = "問題なし";
      if (c.read) {
        const parsed = JSON.parse(raw);
        ({ found, detail } = c.read(parsed));
      }
      out.push({ ...c, ok: true, found, detail });
    } catch (e) {
      // 終了コード1＝検出あり。落ちたのか検出なのかを混同しない
      const text = String(e.stdout ?? "") + String(e.message ?? "");
      out.push({
        ...c,
        ok: false,
        found: 1,
        detail: text.includes("合計") ? text.split("\n").filter((l) => l.includes("合計"))[0] : "実行できなかった",
      });
    }
  }
  return out;
}



/* ---------------------------------------------------------------- 横相談（Peer Help） */

/**
 * 人へ上げる前の一段。担当Aが専門外で詰まった時、担当Bへ直接投げたカードを拾う。
 *
 * **誰かを止めている相談は、その担当自身の次の一手より優先する。**
 * 自分の仕事を進めるより、詰まっている隣を動かす方が全体は速い。
 */
function runPeerHelp() {
  const file = path.join(REPO, ".claude/role-help.json");
  if (!fs.existsSync(file)) return { open: [], byRole: new Map() };
  let db;
  try {
    db = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return { open: [], byRole: new Map() };
  }
  const open = (db.cards ?? []).filter((c) => c.status !== "resolved");
  const byRole = new Map();
  for (const c of open) {
    if (!byRole.has(c.need)) byRole.set(c.need, []);
    byRole.get(c.need).push(c);
  }
  return { open, byRole };
}


/* ---------------------------------------------------------------- 繰り返しの検知 */

/**
 * **同じ依頼が何度も出てくること自体を「構造的に詰まっているサイン」として扱う。**
 *
 * 事故（2026-08-08）：バッジのSQLについて店主が「OK、やって」と承認したのに、
 * 複数セッション・複数回のやり取りを経ても実行されず、店主が
 * **「もう10回以上言ってる」**と不満を表明する事態になった。
 *
 * 原因は、実行を試みた側が**本番プロジェクトが無い別のSupabase組織にログインしていた**こと。
 * 誰もそれに気づかないまま「やっておきます」だけが繰り返された。
 * **「承認は得た」と「実際に完了した」の間の検証が抜けていた。**
 *
 * 人間が「また言ってる」と気づくより先に、機械が数えて気づく。
 * **同じ話題が3回以上ログに出たら、その話題の解決を最優先へ引き上げる。**
 */
const REPEAT_ALERT = 3;

function detectRepeats() {
  const log = readIf(".claude/role-sweep-log.md");
  if (!log) return [];

  // 「判断待ち」「問題」の行だけを見る（完了は繰り返されても害がない）
  const lines = log
    .split("\n")
    .filter((l) => /^- \*\*(判断待ち|問題)\*\*/.test(l.trim()))
    .map((l) => l.replace(/^- \*\*(判断待ち|問題)\*\*：/, "").trim());

  // 話題の指紋。名詞のかたまりで数える（言い回しが毎回違っても同じ話題として拾うため）
  // 【汎用版】固有の話題パターンはプロジェクトごとに違うため、ここでハードコードしない。
  // registry.json に `"sweepTopics": [{"key":"...", "re":"正規表現文字列"}]` を書けばそれを使う。
  // 未指定なら「同じ話題を数える」機能そのものを無効化（空配列）にして安全側に倒す。
  const TOPICS = (registry.sweepTopics ?? []).map((t) => ({ key: t.key, re: new RegExp(t.re, "i") }));

  const out = [];
  for (const t of TOPICS) {
    const hits = lines.filter((l) => t.re.test(l));
    if (hits.length >= REPEAT_ALERT) {
      out.push({ topic: t.key, times: hits.length, latest: hits[0]?.slice(0, 110) ?? "" });
    }
  }
  return out.sort((a, b) => b.times - a.times);
}

/* ---------------------------------------------------------------- Manager（管理者） */

/**
 * Judgeの判定を受けて**次の一手だけ**を決める層。感情も忖度も持たない。
 *
 *   PASS                    → 納品。もう触らない。
 *   FAIL かつ 試行 < 上限   → Builderへ差し戻し（何が駄目かはJudgeの指摘をそのまま渡す）
 *   FAIL かつ 試行 >= 上限  → 人間へエスカレーション。**「どこまで試して何が原因で詰まったか」を必ず添える。**
 *
 * ここを人が読んで気を利かせる場所にしない。**上限を超えたら必ず止める**のがこの層の仕事で、
 * 「あと1回だけ」を許すとコストが青天井になる。
 */
const MAX_ATTEMPTS = 3;

function runManager() {
  const file = path.join(REPO, ".claude/role-claims.json");
  if (!fs.existsSync(file)) return { pending: [], escalate: [], delivered: 0 };
  let db;
  try {
    db = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return { pending: [], escalate: [], delivered: 0, broken: true };
  }
  const pending = [];
  const escalate = [];
  let delivered = 0;
  for (const c of db.claims ?? []) {
    if (c.verdict === "PASS") { delivered++; continue; }
    if (c.verdict !== "FAIL") continue;
    const attempts = c.attempts ?? 0;
    const item = {
      role: c.role,
      deliverable: c.deliverable,
      attempts,
      issues: (c.issues ?? []).map((i) => i.detail),
      assumptions: c.assumptions ?? [],
      uncertainties: c.uncertainties ?? [],
    };
    if (attempts >= MAX_ATTEMPTS) escalate.push(item);
    else pending.push(item);
  }
  return { pending, escalate, delivered };
}

const registry = JSON.parse(fs.readFileSync(REGISTRY, "utf8"));
const helpForRole = runPeerHelp().byRole;
const results = registry.roles
  .map((r) => {
    const a = assess(r);
    const cards = helpForRole.get(r.name) ?? [];
    if (cards.length) {
      // 誰かがこの担当を待って止まっている。自分の残件より前に出す。
      a.helpWaiting = cards.length;
      a.flags.push(`他の担当から助けを求められている（${cards.length}件）`);
      a.score += 35 + cards.filter((c) => c.urgency === "high").length * 15;
      a.nextMove = `横相談 ${cards[0].task} に答える：${cards[0].problem}`;
    }
    return a;
  })
  .sort((a, b) => b.score - a.score);
const autoChecks = process.argv.includes("--no-checks") ? [] : runAutoChecks();
const manager = runManager();
const peerHelp = runPeerHelp();
const repeats = detectRepeats();

const summary = {
  ranAt: new Date().toISOString(),
  date: today(),
  roleCount: results.length,
  withoutPlaybook: results.filter((r) => !r.hasPlaybook).length,
  withOpenItems: results.filter((r) => r.openItems > 0).length,
  stale: results.filter((r) => r.flags.some((f) => f.includes("放置"))).length,
  totalOpenItems: results.reduce((n, r) => n + r.openItems, 0),
  autoChecks,
  peerHelp: { open: peerHelp.open.length, cards: peerHelp.open },
  repeats,
  manager,
  /** 次に手を付けるべき担当（1つだけ） */
  pick: results.find((r) => r.nextMove) ?? null,
  roles: results,
};

const args = process.argv.slice(2);

if (args.includes("--json")) {
  console.log(JSON.stringify(summary, null, 2));
} else if (args.includes("--pick")) {
  if (!summary.pick) console.log("進めるべき担当は見つかりませんでした。");
  else console.log(`${summary.pick.name}\t${summary.pick.nextMove}`);
} else {
  console.log(`# 全担当チェック（${summary.date}）\n`);
  console.log(
    `担当 ${summary.roleCount} / 現在地メモ無し ${summary.withoutPlaybook} / ` +
      `残件あり ${summary.withOpenItems} / ${STALE_DAYS}日以上放置 ${summary.stale} / 残件合計 ${summary.totalOpenItems}\n`,
  );
  console.log("優先 | 担当 | 最終更新 | 残件 | 状態");
  console.log("---|---|---|---|---");
  for (const r of results) {
    const state = r.flags.length ? r.flags.join(" / ") : "順調";
    console.log(
      `${String(r.score).padStart(3)} | ${r.name} | ${r.updated ?? "—"}${
        r.ageDays != null ? `(${r.ageDays}日前)` : ""
      } | ${r.openItems} | ${state}`,
    );
  }
  if (autoChecks.length) {
    console.log(`\n## 担当ごとの自動点検（現在地メモに書いていない実害を機械で見る）`);
    for (const c of autoChecks) {
      const mark = c.found ? "⚠" : "  ";
      console.log(`${mark} ${c.role}：${c.what} → ${c.detail}`);
      if (c.found) console.log(`     詳しく: ${c.cmd.replace(" --json", "")}`);
    }
  }
  if (repeats.length) {
    console.log(`\n## ⛔ 繰り返し出ている話題（構造的に詰まっているサイン）`);
    for (const r of repeats) {
      console.log(`   ${r.topic} … ログに ${r.times} 回`);
      console.log(`     ${r.latest}`);
    }
    console.log(`   **同じ依頼が繰り返されるのは、誰かが怠けているのではなく、経路のどこかが壊れている合図。**`);
    console.log(`   次の一手より先に、この話題の「本当に効いたか」を実測すること。`);
  }
  if (peerHelp.open.length) {
    console.log(`\n## 横相談（人へ上げる前の一段。誰かがこの担当を待って止まっている）`);
    for (const c of peerHelp.open) {
      console.log(`${c.urgency === "high" ? "🔴" : "  "} ${c.task}　${c.from} → ${c.need}`);
      console.log(`     ${c.problem}`);
      console.log(`     試したこと: ${(c.tried ?? []).join(" / ")}`);
    }
    console.log(`     詳しく: npm run role:help`);
  }
  if (manager.pending.length || manager.escalate.length) {
    console.log(`\n## Manager（Judgeの判定を受けた次の一手）`);
    for (const m of manager.pending) {
      console.log(`↩ 差し戻し（${m.attempts + 1}回目 / 上限${MAX_ATTEMPTS}）: ${m.role} — ${m.deliverable.slice(0, 50)}`);
      for (const i of m.issues.slice(0, 2)) console.log(`     直すところ: ${i.split("\n")[0].slice(0, 120)}`);
    }
    for (const m of manager.escalate) {
      console.log(`🛑 エスカレーション（${m.attempts}回試して駄目）: ${m.role} — ${m.deliverable.slice(0, 50)}`);
      for (const i of m.issues.slice(0, 2)) console.log(`     詰まった原因: ${i.split("\n")[0].slice(0, 120)}`);
      for (const a of m.assumptions.slice(0, 2)) console.log(`     置いた前提（外れている可能性）: ${a.slice(0, 100)}`);
    }
  }
  if (summary.pick) {
    console.log(`\n## 次に進めるべき1件`);
    console.log(`担当: ${summary.pick.name}`);
    console.log(`次の一手: ${summary.pick.nextMove}`);
    console.log(`\n進め方: npm run role -- ${summary.pick.name}`);
  }
}

// 機械が読む写しは常に残す（定期実行が前回との差分を見られるように）
fs.writeFileSync(
  path.join(REPO, ".claude/role-sweep-latest.json"),
  JSON.stringify(summary, null, 2),
  "utf8",
);
