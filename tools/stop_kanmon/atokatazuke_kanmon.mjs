#!/usr/bin/env node
// 98404号：後片付けの関所（Stop）。たまごさん「使ったらしまう・使ったら閉じる。
// やりっぱなしで後で面倒な思いをするのは俺」（2026-10-15）の機械の裏付け。
//
// ■ なぜこの作りなのか（1161号 tab_kanmon.mjs と同じ発想を**そのまま**転用）
//   OSには触らない。読むのは「このセッションの記録（transcript）」だけ。
//   Bashで /private/tmp・$TMPDIR 配下に何かを作ったコマンド（mkdir/touch/cp/mktemp/
//   リダイレクト）の中から、作った「つもりの」パスを文字列で拾う。
//   そのパスが**今まだ本当にファイルシステム上に存在するか**を fs.existsSync で見る
//   （これは普通のファイル確認で、TCC許可ダイアログは一切出ない。タブの枚数を数える時の
//   「OS側の許可が要る」問題とは違う）。本当に消していないと existsSync は false にならない。
//
// ■ 対象外（二重の関所にしない）
//   .worktrees 配下・/private/tmp/claude-* は、worktree_taihi.py（10分おき）が別に
//   自動で片付ける担当なので、ここでは数えない（除外しないと「片付け役がいる物」まで
//   このセッションの責任にしてしまい、過剰にブロックする）。
//
// ■ 人質にしない（憲法）
//   - transcript が読めない → exit 0
//   - 3回ブロックしても消えなければ、理由を台帳に残して通す（無限ループを作らない）
//
// 台帳：status/98404_atokatazuke_kanmon.jsonl
// 進捗表：status/public/atokatazuke_kanmon.json
// 逆テスト：node tools/stop_kanmon/atokatazuke_kanmon.mjs --self-test

import { readFileSync, writeFileSync, mkdirSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import path from "node:path";
import os from "node:os";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "98404_atokatazuke_kanmon.jsonl");
const PUB = path.join(REPO, "status", "public", "atokatazuke_kanmon.json");
const MAX_BLOCK = 3;

const CREATE_RE = [
  /mkdir\s+(?:-p\s+)?(\/private\/tmp\/\S+)/g,
  /touch\s+(\/private\/tmp\/\S+)/g,
  /mktemp\s+(?:-d\s+)?[^\n]*?(\/private\/tmp\/\S+)/g,
  /cp\s+-[a-zA-Z]*\s+\S+\s+(\/private\/tmp\/\S+)/g,
  />\s*(\/private\/tmp\/\S+)/g,
];
const REMOVE_RE = [
  /rm\s+-[a-zA-Z]*\s+(\/private\/tmp\/\S+)/g,
  /git\s+worktree\s+remove\s+(?:--force\s+)?(\/private\/tmp\/\S+)/g,
];

function cleanPath(raw) {
  return (raw || "").replace(/["'`;&|)]+$/, "").replace(/\/+$/, "");
}

function isExcluded(p) {
  return p.includes("/.worktrees/") || /\/private\/tmp\/claude-/.test(p);
}

function matchAll(text, list) {
  const out = new Set();
  for (const re of list) {
    const r = new RegExp(re);
    let m;
    while ((m = r.exec(text))) {
      const p = cleanPath(m[1]);
      if (p && !isExcluded(p)) out.add(p);
    }
  }
  return out;
}

/** transcriptの中のBashコマンド本文だけを1つの文字列にまとめる（純粋関数。自己テストで使う） */
export function bashText(raw) {
  const out = [];
  for (const ln of raw.split("\n")) {
    if (!ln.trim()) continue;
    let o;
    try {
      o = JSON.parse(ln);
    } catch {
      continue;
    }
    const content = o?.message?.content;
    if (!Array.isArray(content)) continue;
    for (const c of content) {
      if (c?.type === "tool_use" && c.name === "Bash" && c.input?.command) {
        out.push(String(c.input.command));
      }
    }
  }
  return out.join("\n");
}

/** 作った痕跡から、まだ消していないものを判定する（純粋関数。自己テストで使う）。
 *  existsCheck を差し替えられるようにして、OSに触らず自己テストできるようにする。 */
export function kazoeru(text, existsCheck = existsSync) {
  const created = matchAll(text, CREATE_RE);
  const removedMentioned = matchAll(text, REMOVE_RE);
  const nokori = [...created].filter((p) => !removedMentioned.has(p) && existsCheck(p));
  return { created: [...created], removedMentioned: [...removedMentioned], nokori };
}

function blocksFor(sessionId) {
  try {
    if (!existsSync(DAICHO)) return 0;
    const raw = readFileSync(DAICHO, "utf8");
    let n = 0;
    for (const ln of raw.split("\n")) {
      if (!ln.trim()) continue;
      try {
        const o = JSON.parse(ln);
        if (o.decision === "block" && o.session === sessionId) n += 1;
      } catch {}
    }
    return n;
  } catch {
    return 0;
  }
}

function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}

function kaku(r, decision, sid) {
  try {
    mkdirSync(path.dirname(PUB), { recursive: true });
    writeFileSync(
      PUB,
      JSON.stringify(
        {
          at: new Date().toLocaleString("sv-SE", { timeZone: "Asia/Tokyo" }),
          source: "Stopフックがセッションの記録から数えた（OSには触っていない。existsSyncだけ）",
          created: r.created.length,
          leftover: r.nokori.length,
          lastDecision: decision,
          lastSession: sid,
          leftoverPaths: r.nokori.slice(0, 20),
        },
        null,
        1,
      ),
    );
  } catch {}
}

async function main() {
  if (process.argv.includes("--self-test")) {
    let ok = 0;
    const total = 5;
    // 1) mkdirして残したものは「残り」として拾う
    // ★os.tmpdir()は$TMPDIR（/var/folders/.../T）を指し/private/tmpではない。関所の対象は
    //   /private/tmp固定なので、自己テストも/private/tmp配下に作らないと再現にならない。
    const d1 = mkdtempSync(path.join("/private/tmp", "atokatazuke_st_"));
    const made = path.join(d1, "leftover_dir");
    mkdirSync(made);
    {
      const text = `mkdir -p ${made}\n`;
      const r = kazoeru(text);
      if (r.nokori.includes(made)) ok += 1;
      else console.log("NG: 作って残したものを検出できていない");
    }
    // 2) 作ってから同じコマンド列でrmしていれば「残り」に入らない（existsCheckがfalseのケースも別途）
    {
      const made2 = path.join(d1, "cleaned_dir");
      mkdirSync(made2);
      const text = `mkdir -p ${made2}\nrm -rf ${made2}\n`;
      const r = kazoeru(text, (p) => p !== made2); // 本当に消された想定でexistsSyncはfalseを返す
      if (!r.nokori.includes(made2)) ok += 1;
      else console.log("NG: rmしたのに残り判定になっている");
    }
    // 3) worktree配下は対象外
    {
      const text = `mkdir -p /private/tmp/.worktrees/qXX-test\n`;
      const r = kazoeru(text, () => true);
      if (r.created.length === 0) ok += 1;
      else console.log("NG: .worktrees配下を除外できていない");
    }
    // 4) claude-* は対象外
    {
      const text = `touch /private/tmp/claude-abc/foo.txt\n`;
      const r = kazoeru(text, () => true);
      if (r.created.length === 0) ok += 1;
      else console.log("NG: claude-* を除外できていない");
    }
    // 5) bashText がBash以外のtool_useを無視する
    {
      const raw = JSON.stringify({ message: { content: [{ type: "tool_use", name: "Read", input: { file_path: "/private/tmp/x" } }] } });
      const t = bashText(raw);
      if (t === "") ok += 1;
      else console.log("NG: Bash以外の道具まで数えている");
    }
    rmSync(d1, { recursive: true, force: true });
    console.log(`${ok}/${total} 件合格`);
    process.exit(ok === total ? 0 : 1);
  }

  const stdin = await new Promise((res) => {
    let s = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (s += d));
    process.stdin.on("end", () => res(s));
    setTimeout(() => res(s), 3000);
  });
  let input = {};
  try {
    input = JSON.parse(stdin || "{}");
  } catch {}
  const hook = input.hook_event_name || "Stop";
  const tp = input.transcript_path;
  const sid = input.session_id || "unknown";

  try {
    if (!tp || !existsSync(tp)) {
      process.exit(0); // 読めないなら人質にしない
    }
    const raw = readFileSync(tp, "utf8");
    const text = bashText(raw);
    const r = kazoeru(text);

    if (r.nokori.length === 0) {
      if (r.created.length > 0) write({ event: "atokatazuke", decision: "ok", hook, session: sid, proof: r });
      kaku(r, "ok", sid);
      process.exit(0);
    }

    const already = blocksFor(sid);
    if (already >= MAX_BLOCK) {
      write({ event: "atokatazuke", decision: "akirameta", hook, session: sid, proof: r,
        why: `${MAX_BLOCK}回止めても消えなかった。無限ループにしないので通す` });
      kaku(r, "akirameta", sid);
      console.log(
        JSON.stringify({
          hookSpecificOutput: {
            hookEventName: hook,
            additionalContext: `★/private/tmp に${r.nokori.length}件残したまま終わった。報告に残した場所を書くこと。`,
          },
        }),
      );
      process.exit(0);
    }

    write({ event: "atokatazuke", decision: "block", hook, session: sid, proof: r });
    kaku(r, "block", sid);
    console.error(
      [
        `終われない。**自分が /private/tmp に作ったものを消していない。**`,
        `残り ${r.nokori.length}件：`,
        ...r.nokori.slice(0, 10).map((p) => `  ${p}`),
        ``,
        `いますぐやること：使い終わった作業場・複製・中間ファイルを rm -rf で消す`,
        `（push や納品が済んだものだけ消す。まだ使う途中のものは消さなくてよい）。`,
        `届かない事情があれば、報告に「${r.nokori.length}件残った・理由」を書くこと。`,
        `（台帳：status/98404_atokatazuke_kanmon.jsonl）`,
      ].join("\n"),
    );
    process.exit(2); // ← 終了を拒否
  } catch (e) {
    try {
      write({ event: "atokatazuke", decision: "error", hook, session: sid, why: String(e && e.message) });
    } catch {}
    process.exit(0); // 関所が壊れてもセッションを人質にしない
  }
}

main();
