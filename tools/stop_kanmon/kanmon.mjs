// 1154号：止まれない関所（Stopフックの中身）
//
// お手本（丸写しした相手）：
//   ・Claude Code 公式 Hooks リファレンス https://code.claude.com/docs/en/hooks
//     - Stop / SubagentStop は exit code 2 で「終了を拒否」できる。
//       stderr の文字が、そのまま「なぜ続けるのか」の理由としてClaudeに渡る。
//     - 入力に stop_hook_active（すでにStopフックで続行中か）が来る。
//       公式は「8回連続でブロックしたら本体が上書きして終わらせる」と書いてある。
//   ・LangGraph：止めた場所を必ず外（checkpointer）に書く。記憶に置かない。
//   ・Temporal：進みをイベントの列（append-only）で持ち、落ちたら続きから。
//
// だからここでも「進みは status/1154_stop_kanmon.jsonl に追記だけ」。
// セッションの記憶には一切置かない。落ちても、このファイルを読めば続きから走れる。

import { appendFileSync, readFileSync, existsSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import path from "node:path";

export const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
export const LEDGER = path.join(REPO, "status", "1154_stop_kanmon.jsonl");

export const nowIso = () =>
  new Date(Date.now() + 9 * 3600 * 1000).toISOString().replace("Z", "+09:00");

export function read() {
  if (!existsSync(LEDGER)) return [];
  return readFileSync(LEDGER, "utf8")
    .split("\n")
    .filter((l) => l.trim())
    .map((l) => {
      try {
        return JSON.parse(l);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

export function write(row) {
  mkdirSync(path.dirname(LEDGER), { recursive: true });
  appendFileSync(LEDGER, JSON.stringify({ at: nowIso(), ...row }) + "\n");
}

// 台帳を頭から再生して、いまの姿を作る（状態ファイルを別に持たない＝食い違いが起きない）
export function jotai() {
  const m = new Map();
  for (const r of read()) {
    if (!r.id) continue;
    const c = m.get(r.id) ?? { id: r.id, blocks: 0, events: 0 };
    c.events++;
    if (r.event === "ukeire") {
      c.title = r.title;
      c.done = r.done;
      c.uketa = r.at;
    }
    if (r.event === "hassha") {
      c.hassha = r.at;
      c.base_sha = r.base_sha;
      c.deadline_h = r.deadline_h ?? 6;
    }
    if (r.event === "block") c.blocks++;
    if (r.event === "kanryou") c.kanryou = r.at;
    if (r.event === "hikitsugi") c.hikitsugi = r.at;
    m.set(r.id, c);
  }
  return [...m.values()];
}

// いま走っているもの＝発車済みで、完了も引き継ぎもしていないもの
export const soukouchuu = () =>
  jotai().filter((c) => c.hassha && !c.kanryou && !c.hikitsugi);

// 完了条件が1行で書けているか。書けていない依頼は発車させない。
export function joukenOK(done) {
  if (!done || typeof done !== "object") return "完了条件（done）が無い";
  if (!done.url || !/^https?:\/\//.test(done.url))
    return "done.url（200で返る本番URL）が無い";
  if (!(done.min_bytes > 0)) return "done.min_bytes（中身の最低バイト数）が無い";
  if (!(done.min_diff > 0)) return "done.min_diff（最低の差分件数）が無い";
  return null;
}

async function urlCheck(url, minBytes) {
  try {
    const res = await fetch(url, {
      cache: "no-store",
      signal: AbortSignal.timeout(15000),
    });
    if (res.status !== 200) return { ok: false, why: `URLが${res.status}（200じゃない）: ${url}`, status: res.status, bytes: 0 };
    const body = await res.text();
    const bytes = Buffer.byteLength(body);
    if (bytes < minBytes)
      return { ok: false, why: `中身が薄い（${bytes}バイト < ${minBytes}）: ${url}`, status: 200, bytes };
    return { ok: true, status: 200, bytes };
  } catch (e) {
    return { ok: false, why: `URLに触れない（${e.message}）: ${url}`, status: 0, bytes: 0 };
  }
}

function diffCount(baseSha) {
  // 実測（1154号）：git status は index.lock を書きに行く。フックは他のgit処理と
  // 同時に走るので、ここで壊れた残骸を残すと工場の自動commitごと止まる。
  // --no-optional-locks / GIT_OPTIONAL_LOCKS=0 で、読むだけにして鍵を取らせない。
  const sh = (args) => {
    try {
      return execFileSync("git", ["--no-optional-locks", ...args], {
        cwd: REPO,
        encoding: "utf8",
        env: { ...process.env, GIT_OPTIONAL_LOCKS: "0" },
      });
    } catch {
      return "";
    }
  };
  const n = new Set();
  if (baseSha) {
    for (const f of sh(["diff", "--name-only", `${baseSha}`, "HEAD"]).split("\n"))
      if (f.trim()) n.add(f.trim());
  }
  for (const l of sh(["status", "--porcelain"]).split("\n"))
    if (l.trim()) n.add(l.slice(3).trim());
  return n.size;
}

// 1152号を相乗りさせる：★外の判定が入るまで完了にしない。
//
// たまごさん（2026-09-26）「Claudeだけだと裏切られっぱなしで信用できない。
//   判定する側をClaudeの外に出す。★こちら側が自分で『完了』と書けない。
//   外の判定が入って初めて完了になる。」
//
// 鍵は status/gaibu/soto_hantei.json（tools/gaibu_shinsa.py が外から持ち帰って書く）。
// ★ここは読むだけ。関所の側から鍵を書く口は作らない（作った瞬間に自己申告に戻る）。
// 鍵が1個も無いあいだは効かせない（誰も完了できず工場が全停止するため）。
// 1個でも入った時点から、この検査は有効になる。
function sotoNoHantei(c) {
  const f = path.join(REPO, "status", "gaibu", "soto_hantei.json");
  if (!existsSync(f)) return { kiiteru: false };
  let m;
  try {
    m = JSON.parse(readFileSync(f, "utf8"));
  } catch {
    return { kiiteru: false };
  }
  const keys = Object.keys(m || {});
  if (keys.length === 0) return { kiiteru: false };
  const norm = (x) =>
    String(x || "")
      .replace(/[★☆*#`>【】\[\]「」『』（）()・:：,、。.\-—–_/\\!！?？\s]/g, "")
      .toLowerCase()
      .slice(0, 24);
  const k = norm(c.title);
  const r = m[k];
  if (!r) return { kiiteru: true, ok: false, why: "外の判定がまだ無い（未審査）" };
  if (!r.ok) return { kiiteru: true, ok: false, why: `外が不合格と言っている：${r.naze || ""}` };
  return { kiiteru: true, ok: true, kara: r.kara, naze: r.naze };
}

// 1件を検査する。返り値 {ok, why, proof}
export async function kensa(c) {
  const bad = joukenOK(c.done);
  if (bad) return { ok: false, why: bad, proof: {} };
  const u = await urlCheck(c.done.url, c.done.min_bytes);
  const d = diffCount(c.base_sha);
  const proof = { url: c.done.url, status: u.status, bytes: u.bytes, diff: d };
  if (!u.ok) return { ok: false, why: u.why, proof };
  if (d < c.done.min_diff)
    return { ok: false, why: `差分が${d}件（${c.done.min_diff}件以上要る）`, proof };
  // ★機械の検査はここまで通った。だが完了ではない。外の判定を見る。
  const soto = sotoNoHantei(c);
  if (soto.kiiteru && !soto.ok)
    return { ok: false, why: `★${soto.why}（完了はこちら側では書けません）`,
             proof: { ...proof, soto: false } };
  return { ok: true, proof: { ...proof, soto: soto.kiiteru ? (soto.kara || true) : "鍵まだ0件" } };
}

export const keikaJikan = (c) =>
  c.hassha ? (Date.now() - new Date(c.hassha).getTime()) / 3600000 : 0;
