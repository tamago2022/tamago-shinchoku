#!/usr/bin/env node
/**
 * Judge（判定者）— Builderとは別の「外部の正解データ」で合否を出す
 *
 *   npm run role:judge              未判定の主張を全部見る
 *   npm run role:judge -- --json    機械が読む形
 *
 * ## この装置の原則
 *
 * 1. **主張の文章を読まない。** 読むと同じ推論に引きずられる（＝同じ盲点に落ちる）。
 *    読むのは `evidence` に書かれた**手順**だけで、それを実際に走らせる。
 * 2. **印象で語らない。** 出すのは `PASS` / `FAIL` と、FAILなら
 *    「どの証拠が」「どう失敗したか」だけ。「良さそう」は出力に存在しない。
 * 3. **証拠が0件の主張は自動でFAIL。** 検証できない主張を通すと、この仕組み全体が
 *    ただの自己申告に戻る。**ここは緩めない。**
 * 4. **Judgeは直さない。** 直すのはBuilderの仕事。役割を混ぜると分離した意味が消える。
 *
 * ## この店での「外部の正解データ」
 *
 * | 種類 | 正解データ |
 * |---|---|
 * | コード | ビルド・型チェック・見回りスクリプトの終了コード |
 * | データ | 名簿の実データ（件数・穴・重複） |
 * | 事実 | 本番DBの実スキーマ、YouTubeのoEmbed、本番URLの中身 |
 * | 反映 | `origin/main` の祖先判定（＝本当に届いたか） |
 *
 * どれも**Builderの頭の外にある**。ここが「同じモデルの自己採点」との決定的な違い。
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const FILE = path.join(REPO, ".claude/role-claims.json");
const TIMEOUT_MS = 180000;

const asJson = process.argv.includes("--json");

if (!fs.existsSync(FILE)) {
  console.log("判定する主張がありません（.claude/role-claims.json が無い）。");
  process.exit(0);
}
const db = JSON.parse(fs.readFileSync(FILE, "utf8"));

function run(cmd) {
  try {
    const out = execSync(cmd, { cwd: REPO, encoding: "utf8", timeout: TIMEOUT_MS, stdio: ["ignore", "pipe", "pipe"] });
    return { code: 0, out };
  } catch (e) {
    return { code: e.status ?? 1, out: String(e.stdout ?? "") + String(e.stderr ?? "") };
  }
}

/** 証拠1件を検証する。**主張の文章は一切見ない。** */
function checkEvidence(ev) {
  const fail = (detail) => ({ ok: false, detail });
  const ok = (detail) => ({ ok: true, detail });

  if (ev.startsWith("cmd!:")) {
    const cmd = ev.slice(5);
    const r = run(cmd);
    return r.code !== 0
      ? ok(`期待どおり検出した（終了コード ${r.code}）`)
      : fail(`検出できていない。終了コード0で通ってしまった → ${cmd}`);
  }
  if (ev.startsWith("cmd:")) {
    const cmd = ev.slice(4);
    const r = run(cmd);
    return r.code === 0
      ? ok("終了コード0")
      : fail(`終了コード ${r.code} で失敗 → ${cmd}\n      ${r.out.split("\n").slice(-4).join(" / ").slice(0, 200)}`);
  }
  if (ev.startsWith("nogrep:") || ev.startsWith("grep:")) {
    const neg = ev.startsWith("nogrep:");
    const body = ev.slice(neg ? 7 : 5);
    const [file, needle] = body.split("::");
    if (!file || needle === undefined) return fail(`証拠の書式が壊れている → ${ev}`);
    const p = path.join(REPO, file);
    if (!fs.existsSync(p)) return fail(`ファイルが無い → ${file}`);
    const has = fs.readFileSync(p, "utf8").includes(needle);
    if (neg) return has ? fail(`まだ含まれている → ${file} に「${needle.slice(0, 40)}」`) : ok("含まれていない");
    return has ? ok("含まれている") : fail(`含まれていない → ${file} に「${needle.slice(0, 40)}」`);
  }
  if (ev.startsWith("commit:")) {
    const sha = ev.slice(7).trim();
    run("git fetch origin main -q");
    const r = run(`git merge-base --is-ancestor ${sha} origin/main`);
    return r.code === 0
      ? ok("origin/main の祖先＝本当に届いている")
      : fail(`origin/main に入っていない → ${sha}（「main反映済み」は嘘になる）`);
  }
  if (ev.startsWith("url:")) {
    const [url, needle] = ev.slice(4).split("::");
    if (!url || needle === undefined) return fail(`証拠の書式が壊れている → ${ev}`);
    // -a 必須（NULバイトがあると grep がバイナリ扱いして黙る）
    const r = run(`curl -s "${url}" | grep -a -c -- "${needle.replace(/"/g, '\\"')}"`);
    const n = Number((r.out || "0").trim());
    return n > 0 ? ok(`本番に出ている（${n}件）`) : fail(`本番に出ていない → ${url} に「${needle.slice(0, 40)}」`);
  }
  if (ev.startsWith("count:")) {
    const [cmd, want] = ev.slice(6).split("::");
    const r = run(cmd);
    return r.out.includes(String(want).trim())
      ? ok(`出力に ${want} が出た`)
      : fail(`出力に ${want} が出ない → ${cmd}\n      ${r.out.split("\n").slice(-3).join(" / ").slice(0, 200)}`);
  }
  return fail(`知らない証拠の種類 → ${ev}`);
}

/* ---------------------------------------------------------------- 判定 */

const results = [];
for (const c of db.claims) {
  if (c.verdict === "PASS") continue; // 一度通ったものは再判定しない

  const issues = [];

  if (!c.evidence?.length) {
    issues.push({
      type: "証拠なし",
      location: `claim:${c.id}`,
      detail: "検証手順が1件も無い。検証できない主張は通さない（自己申告に戻ってしまうため）。",
    });
  } else {
    for (const ev of c.evidence) {
      const r = checkEvidence(ev);
      if (!r.ok) issues.push({ type: "証拠が通らない", location: ev.slice(0, 80), detail: r.detail });
    }
  }

  // 自信が高いのに不確実性を1件も書いていない主張は、**過信のサイン**として見る。
  // 落とすほどではないので警告だけ（Judgeの仕事は合否であって説教ではない）。
  const overconfident = (c.confidence_score ?? 0) >= 0.9 && (c.uncertainties?.length ?? 0) === 0;

  const verdict = issues.length ? "FAIL" : "PASS";
  c.verdict = verdict;
  c.judgedAt = new Date().toISOString();
  c.issues = issues;
  results.push({ id: c.id, role: c.role, verdict, issues, overconfident, attempts: c.attempts ?? 0 });
}

fs.writeFileSync(FILE, JSON.stringify(db, null, 2), "utf8");

const summary = {
  ranAt: new Date().toISOString(),
  judged: results.length,
  pass: results.filter((r) => r.verdict === "PASS").length,
  fail: results.filter((r) => r.verdict === "FAIL").length,
  results,
};

if (asJson) {
  console.log(JSON.stringify(summary, null, 2));
} else {
  console.log(`# Judge（判定 ${summary.judged}件 / PASS ${summary.pass} / FAIL ${summary.fail}）\n`);
  if (!summary.judged) console.log("未判定の主張はありません。");
  for (const r of results) {
    console.log(`${r.verdict === "PASS" ? "PASS" : "FAIL"}  ${r.role}${r.attempts ? `（差し戻し${r.attempts}回目）` : ""}`);
    for (const i of r.issues) console.log(`      ・${i.type}: ${i.detail}`);
    if (r.overconfident) console.log(`      △ 自信0.9以上なのに不確実性の記載が0件（過信のサイン）`);
  }
}

process.exit(summary.fail ? 1 : 0);
