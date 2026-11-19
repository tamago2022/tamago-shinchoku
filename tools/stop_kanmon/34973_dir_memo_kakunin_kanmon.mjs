#!/usr/bin/env node
// 34973号【判定日赤・2026-08-08に言われて1ヶ月以上未着手】
// 「同じ轍を踏まないよう、作業ディレクトリの確認と、メモを上書きする前の既存内容の確認を徹底してください。」
//
// ■ 何が起きていたか（実測・既存の失敗台帳から）
//   (1) status/failures.jsonl #F-20261009090406-quick：
//       pages_publish.sh が公開のソースにしていたのは origin/main ではなく、
//       常駐の作業ディレクトリ(/Users/mac/tamago/tamago-shinchoku)の**チェックアウト中の
//       現在のブランチ**だった。origin/mainへpushしただけでは公開に反映されず404が続いた。
//       （この1件自体は34863号でpages_publish.sh内のCUR算出をorigin/main優先に直済み。
//        本関所は「そもそもmain以外をチェックアウトした状態で公開系コマンドを打つ」こと自体を
//        入口で止め、同じ形の事故が別の場所で再発するのを防ぐ）
//   (2) MEMORY.md上書き事故（agent-memory配下の記憶ファイル・Coworkの.claude書き込み制限の
//       手順書適用時）：新規メモリ作成前に既存ファイル名を確認せず上書きし、他セッションの
//       記憶が消えた。git checkoutで復元した実例が過去にある。
//
// ■ 止めるもの（2点。どちらもexit 2）
//   A) Write/Edit/MultiEdit で「共有メモ系ファイル」（MEMORY.md・ai-brain配下.md・
//      agent-memory配下・genzaichi系・00_現在地.md・status/*_ima.md）の**既存ファイルを
//      上書き**しようとした時、このセッションのtranscriptに同じfile_pathへのRead呼び出しが
//      1回も無ければ拒否する（＝上書き前に中身を見ていない）。
//   B) Bash で pages_publish.sh / git push 等の「公開・main反映」系コマンドを打つ時、
//      cwdの実際のgitブランチがmainでなければ拒否する（＝作業ディレクトリの取り違え）。
//
// ■ 人質にしない（憲法）
//   transcriptが読めない・形が違う・git判定ができない → 黙って通す（exit 0）。
//   新規ファイル作成（まだ存在しないファイルへのWrite）は対象外。
//
// 台帳：status/34973_kanmon.jsonl
// 逆テスト：node tools/stop_kanmon/34973_dir_memo_kakunin_kanmon.mjs --self-test

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "34973_kanmon.jsonl");

const MEMO_PATTERNS = [
  /MEMORY\.md$/,
  /agent-memory\//,
  /ai-brain[\\/].*\.md$/i,
  /genzaichi.*\.md$/i,
  /00_現在地\.md$/,
  /status[\\/].*_ima\.md$/,
];

const PUBLISH_CMD_PATTERNS = [
  /pages_publish\.sh/,
  /\bgit\s+push\b/,
];

function nowIso() {
  return new Date().toISOString();
}

function log(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: nowIso(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}

function isMemoFile(p) {
  if (!p) return false;
  return MEMO_PATTERNS.some((re) => re.test(p));
}

function hasPublishCmd(cmd) {
  if (!cmd) return false;
  return PUBLISH_CMD_PATTERNS.some((re) => re.test(cmd));
}

/** transcriptを読み、このセッションで file_path への Read 呼び出しがあったか */
function readBefore(transcriptPath, filePath) {
  if (!transcriptPath || !existsSync(transcriptPath)) return null; // 判定不能
  let raw;
  try {
    raw = readFileSync(transcriptPath, "utf8");
  } catch {
    return null;
  }
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
      if (c?.type !== "tool_use") continue;
      if (c.name !== "Read") continue;
      const fp = c.input?.file_path;
      if (fp && path.resolve(String(fp)) === path.resolve(String(filePath))) {
        return true;
      }
    }
  }
  return false;
}

/** cwdの実ブランチを見る。main以外ならそのブランチ名を返す */
function branchMismatch(cwd) {
  try {
    // symbolic-ref は未コミットの新規リポジトリでもブランチ名を返す
    // （rev-parse --abbrev-ref HEAD はコミットが1つも無いと失敗する）
    const r = spawnSync("git", ["-C", cwd || REPO, "symbolic-ref", "--short", "-q", "HEAD"], {
      encoding: "utf8",
      timeout: 5000,
    });
    if (r.status !== 0) return null; // 判定不能（detached HEAD等）
    const branch = (r.stdout || "").trim();
    if (!branch) return null;
    if (branch === "main") return null;
    return branch;
  } catch {
    return null;
  }
}

async function main() {
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
  } catch {
    process.exit(0);
  }

  const tool = String(input.tool_name || "");
  const ti = input.tool_input || {};
  const sid = input.session_id || "unknown";
  const tp = input.transcript_path;
  const cwd = input.cwd;

  try {
    // --- A) メモ系ファイルの無確認上書き ---
    if (tool === "Write") {
      const fp = ti.file_path;
      if (fp && isMemoFile(fp) && existsSync(fp)) {
        const seen = readBefore(tp, fp);
        if (seen === false) {
          log({ event: "memo_overwrite", decision: "block", session: sid, file: fp });
          console.error(
            [
              `終われない。**既存の共有メモを、事前にReadせず上書きしようとしている。**`,
              `対象: ${fp}`,
              `34973号（2026-08-08判定日赤）の再発防止：MEMORY.md等の共有ファイルは他セッションと`,
              `共有されている。上書きすると相手の記録が消える（過去にgit checkoutで復元した事故あり）。`,
              `いますぐ Read で既存内容を読み、必要な行だけ追記・置換してから書き直すこと。`,
              `（台帳：status/34973_kanmon.jsonl）`,
            ].join("\n"),
          );
          process.exit(2);
        }
        log({ event: "memo_overwrite", decision: "ok", session: sid, file: fp, seen });
      }
    }

    // --- B) 作業ディレクトリ取り違えでの公開系コマンド ---
    if (tool === "Bash") {
      const cmd = String(ti.command || "");
      if (hasPublishCmd(cmd)) {
        const mismatch = branchMismatch(cwd);
        if (mismatch) {
          log({ event: "dir_mismatch", decision: "block", session: sid, branch: mismatch, cmd: cmd.slice(0, 200) });
          console.error(
            [
              `終われない。**作業ディレクトリが main 以外（${mismatch}）をチェックアウトした状態で、`,
              `公開・main反映系のコマンドを実行しようとしている。**`,
              `34973号（2026-08-08判定日赤）・既存事故F-20261009090406-quickと同じ形：`,
              `作業ディレクトリのHEADと origin/main がズレたまま公開すると、反映されたと思って`,
              `実は反映されていない（404が続く）事故につながる。`,
              `先に \`git -C ${cwd || REPO} fetch origin main\` → ブランチを main に揃えるか、`,
              `origin/main を明示的に対象にしてから実行すること。`,
              `（台帳：status/34973_kanmon.jsonl）`,
            ].join("\n"),
          );
          process.exit(2);
        }
        log({ event: "dir_mismatch", decision: "ok", session: sid, cmd: cmd.slice(0, 200) });
      }
    }

    process.exit(0);
  } catch (e) {
    try {
      log({ event: "error", session: sid, why: String(e && e.message) });
    } catch {}
    process.exit(0); // 関所が壊れてもセッションを人質にしない
  }
}

// --- 逆テスト（--self-test）---
// たまごさんの恒久ルール（見張りは必ず逆テストする）：緑は無実の証明ではない。
// 違反を仕込んで赤(exit 2)になるまで確認する。
async function selfTest() {
  const os = await import("node:os");
  const tmp = path.join(os.tmpdir(), `34973-selftest-${Date.now()}`);
  mkdirSync(tmp, { recursive: true });

  let pass = 0, fail = 0;
  function expectExit(name, input, wantCode) {
    const r = spawnSync("node", [new URL(import.meta.url).pathname], {
      input: JSON.stringify(input),
      encoding: "utf8",
      timeout: 10000,
    });
    const ok = r.status === wantCode;
    console.log(`${ok ? "✅" : "❌"} ${name}: 期待=${wantCode} 実際=${r.status}`);
    if (ok) pass += 1; else fail += 1;
  }

  // ケース1: 既存メモファイルをReadせずWrite → block(2)が期待値
  const memoFile = path.join(tmp, "MEMORY.md");
  writeFileSync(memoFile, "既存の内容\n");
  const transcriptNoRead = path.join(tmp, "transcript_no_read.jsonl");
  writeFileSync(transcriptNoRead, JSON.stringify({ message: { content: [{ type: "tool_use", name: "Bash", input: {} }] } }) + "\n");
  expectExit("A-違反: メモを読まずに上書き", {
    tool_name: "Write",
    tool_input: { file_path: memoFile, content: "書き換え" },
    transcript_path: transcriptNoRead,
    session_id: "test-a-ng",
  }, 2);

  // ケース2: 既存メモファイルをRead済みでWrite → 通る(0)が期待値
  const transcriptWithRead = path.join(tmp, "transcript_with_read.jsonl");
  writeFileSync(transcriptWithRead, JSON.stringify({ message: { content: [{ type: "tool_use", name: "Read", input: { file_path: memoFile } }] } }) + "\n");
  expectExit("A-正常: 既読のメモを上書き", {
    tool_name: "Write",
    tool_input: { file_path: memoFile, content: "書き換え" },
    transcript_path: transcriptWithRead,
    session_id: "test-a-ok",
  }, 0);

  // ケース3: メモ系ではない通常ファイルのWrite → 通る(0)
  const normalFile = path.join(tmp, "normal.txt");
  writeFileSync(normalFile, "x");
  expectExit("A-対象外: 通常ファイル上書き", {
    tool_name: "Write",
    tool_input: { file_path: normalFile, content: "y" },
    transcript_path: transcriptNoRead,
    session_id: "test-a-skip",
  }, 0);

  // ケース4: main以外のディレクトリでgit pushを打つ → block(2)
  const gitTmp = path.join(tmp, "repo-feature");
  mkdirSync(gitTmp, { recursive: true });
  spawnSync("git", ["init", "-q", gitTmp]);
  spawnSync("git", ["-C", gitTmp, "checkout", "-q", "-b", "feature/x"]);
  expectExit("B-違反: main以外でgit push", {
    tool_name: "Bash",
    tool_input: { command: "git push origin main" },
    cwd: gitTmp,
    session_id: "test-b-ng",
  }, 2);

  // ケース5: mainブランチでgit pushを打つ → 通る(0)
  const gitMain = path.join(tmp, "repo-main");
  mkdirSync(gitMain, { recursive: true });
  spawnSync("git", ["init", "-q", "-b", "main", gitMain]);
  expectExit("B-正常: mainでgit push", {
    tool_name: "Bash",
    tool_input: { command: "git push origin main" },
    cwd: gitMain,
    session_id: "test-b-ok",
  }, 0);

  console.log(`\n合計: PASS=${pass} FAIL=${fail}`);
  process.exit(fail > 0 ? 1 : 0);
}

if (process.argv.includes("--self-test")) {
  selfTest();
} else {
  main();
}
