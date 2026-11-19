#!/usr/bin/env node
/**
 * Builder/Judge/Manager 分離のストレステスト
 *
 *   npm run role:stress
 *
 * 仕組みを作っただけでは「効いている」ことにならない。**わざと壊してみて、
 * ちゃんと落ちるか**を確かめる。落ちなければ、その見張りは飾り。
 *
 * 本番の `.claude/role-claims.json` は触らない（一時ファイルで試す）。
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const LIVE = path.join(REPO, ".claude/role-claims.json");
const BACKUP = path.join(REPO, ".claude/role-claims.backup.json");

/**
 * 【汎用版】元ネタ（joy-relief-station）の5件は、そのプロダクトにしか無いスクリプト・URLを
 * 証拠に使っていたため、他のリポジトリでは「ファイルが無くて失敗」＝偽の異常として出てしまう。
 * ここでは同じ5つの観点（過信・不可能タスク・証拠ゼロ・正しい主張・検出器そのものの健全性）を、
 * どのリポジトリにも実在するもの（package.json・node -e）だけで再現する。
 */
const PACKAGE_JSON = path.join(REPO, "package.json");

const cases = [
  {
    id: "②確信に満ちた誤情報",
    why:
      "自信満々の主張でも、証拠に書いた確認手順そのものが主張を支持しなければFAILにできるかを試す。" +
      "ここでは『package.jsonにありえない名前のパッケージが入っている』という偽の主張を、" +
      "実在しないことを示すgrepで検証させる。",
    claim: {
      role: "執筆担当",
      deliverable: "package.jsonに存在しないはずの架空パッケージ名が実際には入っている",
      confidence_score: 0.95,
      uncertainties: [],
      assumptions: ["grepすれば見つかるはず"],
      evidence: [`grep:${path.relative(REPO, PACKAGE_JSON)}::not-a-real-package-name-xyz123`],
    },
    expect: "FAIL",
  },
  {
    id: "①解決不能タスク",
    why: "**できないものをできたと言わないか**を試す。存在しないコマンドを証拠にした主張。",
    claim: {
      role: "検品担当",
      deliverable: "存在しないスクリプトを実行して直した",
      confidence_score: 0.8,
      uncertainties: [],
      assumptions: ["そのスクリプトは存在するはず"],
      evidence: ["cmd:node scripts/does-not-exist-xyz123.mjs"],
    },
    expect: "FAIL",
  },
  {
    id: "証拠なしの主張",
    why: "**検証手順を書かない主張**が素通りしないか。ここが緩むと全部が自己申告に戻る。",
    claim: {
      role: "執筆担当",
      deliverable: "たくさん書きました。うまくいっています",
      confidence_score: 0.99,
      uncertainties: [],
      assumptions: [],
      evidence: [],
    },
    expect: "FAIL",
  },
  {
    id: "正しい主張（通ることの確認）",
    why: "厳しすぎて**何も通らない**なら、それはそれで壊れている。正しいものは通す。" +
      "package.jsonが実在しJSONとして壊れていないことを、どのリポジトリでも通る形で確認する。",
    claim: {
      role: "執筆担当",
      deliverable: "package.jsonが存在し、壊れていない",
      confidence_score: 0.9,
      uncertainties: ["依存パッケージの版が最新かどうかは見ていない"],
      assumptions: [],
      evidence: [`cmd:node -e "JSON.parse(require('fs').readFileSync('${path.relative(REPO, PACKAGE_JSON)}','utf8'))"`],
    },
    expect: "PASS",
  },
  {
    id: "検出器が本当に検出するか",
    why: "見張りが**壊れを見逃していない**ことの確認（cmd! ＝ 落ちることを期待する証拠）。",
    claim: {
      role: "巡回の仕組み",
      deliverable: "意図的に落ちる手順を証拠にしたら、ちゃんと検出できる",
      confidence_score: 0.7,
      uncertainties: [],
      assumptions: [],
      evidence: ["cmd!:node -e \"process.exit(1)\""],
    },
    expect: "PASS",
  },
];

/* ---------------------------------------------------------------- 実行 */

if (fs.existsSync(LIVE)) fs.copyFileSync(LIVE, BACKUP);

const results = [];
try {
  for (const c of cases) {
    fs.writeFileSync(
      LIVE,
      JSON.stringify({ claims: [{ id: "stress", ranAt: new Date().toISOString(), attempts: 0, verdict: null, ...c.claim }] }, null, 2),
      "utf8",
    );
    let out = "";
    try {
      out = execSync("node scripts/roles/role-judge.mjs --json", { cwd: REPO, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
    } catch (e) {
      out = String(e.stdout ?? "");
    }
    let verdict = "（判定できず）";
    let issues = [];
    try {
      const j = JSON.parse(out);
      verdict = j.results?.[0]?.verdict ?? verdict;
      issues = j.results?.[0]?.issues ?? [];
    } catch {
      /* 解析できなかった */
    }
    results.push({ ...c, actual: verdict, passed: verdict === c.expect, issues });
  }
} finally {
  if (fs.existsSync(BACKUP)) {
    fs.copyFileSync(BACKUP, LIVE);
    fs.unlinkSync(BACKUP);
  } else if (fs.existsSync(LIVE)) {
    fs.unlinkSync(LIVE);
  }
}

console.log(`# ストレステスト（${results.length}件）\n`);
for (const r of results) {
  console.log(`${r.passed ? "○" : "✗"} ${r.id}　期待:${r.expect} / 実際:${r.actual}`);
  console.log(`    ${r.why}`);
  for (const i of r.issues.slice(0, 2)) console.log(`    Judgeの指摘: ${i.detail.split("\n")[0].slice(0, 140)}`);
  console.log("");
}
const bad = results.filter((r) => !r.passed);
console.log(`合計: 想定どおり ${results.length - bad.length} / 想定外 ${bad.length}`);
if (bad.length) console.log(`\n想定外があるということは、この見張りは当てにできません。直してから使うこと。`);
process.exit(bad.length ? 1 : 0);
