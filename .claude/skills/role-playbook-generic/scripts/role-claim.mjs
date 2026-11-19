#!/usr/bin/env node
/**
 * Builder（構築者）が「やったこと」を**検証可能な形**で置く場所
 *
 *   npm run role:claim -- --role つなげる担当 \
 *     --claim "Come Togetherのカバー2件を原曲へ接続した" \
 *     --evidence "cmd:node scripts/patrol/check-data-holes.mjs" \
 *     --evidence "grep:src/lib/coverGuide.ts::originalRef: { artistId: \"beatles\"" \
 *     --confidence 0.9 \
 *     --uncertainty "MJは自動検出できていない（コピーに Beatles の表記が無い）" \
 *     --assumption "動画題名の (Beatles Cover) 表記を根拠として信用した"
 *
 * ## なぜ「主張」と「証拠」を分けて書かせるか
 *
 * **同じ推論プロセスは同じ盲点に陥る。** 自分が書いた文章を自分で読み返しても、
 * 間違いは見つからない（見つかるなら最初から書いていない）。
 *
 * そこで Builder は**結論だけでなく、その結論を機械が確かめる手順**を必ず添える。
 * Judge はその手順を**実際に走らせて**合否を出す。Judgeは主張の文章を読まない。
 * これで「自己採点」ではなく「外部の正解データとの突き合わせ」になる。
 *
 * confidence / uncertainties / assumptions を必ず書かせるのは、
 * **自信の高さと正しさは別物**だからで、後で外れた時に「どの前提が外れたか」を辿るため。
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(HERE, "..", "..");
const FILE = path.join(REPO, ".claude/role-claims.json");

function all(name) {
  const out = [];
  const a = process.argv;
  for (let i = 0; i < a.length; i++) if (a[i] === `--${name}`) out.push(a[i + 1]);
  return out.filter(Boolean);
}
const one = (name) => all(name)[0] ?? null;

const role = one("role");
const claim = one("claim");
const evidence = all("evidence");
const confidence = Number(one("confidence") ?? "0.7");

if (!role || !claim) {
  console.error(
    `使い方: npm run role:claim -- --role <担当> --claim <主張> --evidence <証拠> [--confidence 0.9] [--uncertainty ...] [--assumption ...]

証拠の書き方（Judgeがこれを実際に走らせる）:
  cmd:<コマンド>              終了コード0なら合格
  cmd!:<コマンド>             終了コード0以外なら合格（「検出できること」を示す時）
  grep:<ファイル>::<文字列>    そのファイルに含まれていれば合格
  nogrep:<ファイル>::<文字列>  含まれていなければ合格
  commit:<SHA>                origin/main の祖先なら合格（＝本当にmainへ入った）
  url:<URL>::<文字列>          本番を取得して含まれていれば合格
  count:<コマンド>::<数>       コマンド出力にその数が出れば合格`,
  );
  process.exit(1);
}

const entry = {
  id: `${Date.now()}`,
  ranAt: new Date().toISOString(),
  role,
  /** Builderの成果物（言葉。Judgeはこれを読まない） */
  deliverable: claim,
  /** 0〜1。自信。**高くても正しいとは限らない** */
  confidence_score: confidence,
  /** 自分でも確信が持てていないところ */
  uncertainties: all("uncertainty"),
  /** 前提として置いたもの（外れたらここを疑う） */
  assumptions: all("assumption"),
  /** Judgeが実際に走らせる検証手順 */
  evidence,
  /** Managerが使う。差し戻し回数 */
  attempts: 0,
  verdict: null,
};

const db = fs.existsSync(FILE) ? JSON.parse(fs.readFileSync(FILE, "utf8")) : { claims: [] };
db.claims.unshift(entry);
db.claims = db.claims.slice(0, 200);
fs.writeFileSync(FILE, JSON.stringify(db, null, 2), "utf8");

if (!evidence.length) {
  console.log(`⚠ 証拠が0件です。Judgeは必ずFAILにします（検証できない主張は通さない）。`);
}
console.log(`記録した → .claude/role-claims.json（${role}／証拠 ${evidence.length}件）`);
console.log(`次: npm run role:judge`);
