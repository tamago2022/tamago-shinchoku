#!/usr/bin/env node
// 1773号：『たまごさんにやってもらう』を最初の選択肢にしない関所（Stop hook版）。
//
// ■ 外部検品FIXで指摘された穴（2026-10-20）
//   「self-test PASSだけでは、関所が実際の子セッションの出力に常時かかっているか分からない」
//   ＝ tools/1773_tanomanai_kanmon.py は作っただけで、kenpin_gate.py --submit を手で呼んだ時
//     しか効かなかった。手で呼ぶのを忘れれば素通りする＝「常時」ではない。
//
// ■ どう直したか（tab_kanmon.mjs・atokatazuke_kanmon.mjsと同じ型）
//   セッションの transcript を読み、**最後のassistant本文（最終応答）**を取り出し、
//   tools/1773_tanomanai_kanmon.py に渡して判定する。Stop hookは全セッションで
//   自動発火するので、kenpin_gate.pyを呼んだかどうかに関係なく常にかかる。
//   判定ロジックは二重管理しない（1773_tanomanai_kanmon.py をサブプロセスで呼ぶだけ）。
//
// ■ 人質にしない（憲法）
//   ・transcriptが読めない／最終応答が空 → 何も言わずに通す（exit 0）
//   ・3回ブロックしても合わなければ、理由を台帳に残して通す（無限ループを作らない）
//
// 記録：status/1154_stop_kanmon.jsonl（event:"tanomanai"）
// 逆テスト：node tools/stop_kanmon/1773_tanomanai_stop_kanmon.mjs --self-test

import { readFileSync, writeFileSync, mkdirSync, existsSync, mkdtempSync, rmSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import os from "node:os";

const REPO = "/Users/mac/tamago/tamago-shinchoku";
const KANMON_PY = path.join(REPO, "tools", "1773_tanomanai_kanmon.py");
const DAICHO = path.join(REPO, "status", "1154_stop_kanmon.jsonl");
const MAX_BLOCK = 3;

function nowIso() {
  return new Date().toISOString();
}

function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: nowIso(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}

/** transcript(jsonl)から最後のassistant本文(text)を取り出す */
function saigoNoText(file) {
  const raw = readFileSync(file, "utf8");
  let lastText = "";
  for (const ln of raw.split("\n")) {
    if (!ln.trim()) continue;
    let o;
    try {
      o = JSON.parse(ln);
    } catch {
      continue;
    }
    if (o?.type !== "assistant") continue;
    const content = o?.message?.content;
    if (!Array.isArray(content)) continue;
    for (const c of content) {
      if (c?.type === "text" && typeof c.text === "string" && c.text.trim()) {
        lastText = c.text;
      }
    }
  }
  return lastText;
}

function hantei(text) {
  const r = spawnSync("python3", ["-I", KANMON_PY, "--text", text], {
    encoding: "utf8",
    timeout: 15000,
  });
  return { ok: r.status === 0, out: String(r.stdout || r.stderr || "") };
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
        if (o.event === "tanomanai" && o.decision === "block" && o.session === sessionId) n += 1;
      } catch {}
    }
    return n;
  } catch {
    return 0;
  }
}

async function readStdin() {
  return new Promise((res) => {
    let s = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (d) => (s += d));
    process.stdin.on("end", () => res(s));
    setTimeout(() => res(s), 3000);
  });
}

function selfTest() {
  const dir = mkdtempSync(path.join(os.tmpdir(), "1773-stop-kanmon-"));
  const mk = (text) =>
    JSON.stringify({ type: "assistant", message: { content: [{ type: "text", text }] } });
  const cases = [
    { text: "完了。本番URLはhttps://example.com/です。", wantOk: true },
    { text: "どうしますか？AとBどちらがいいですか。", wantOk: false },
    {
      text: "ここはたまごさんにやってもらうことにしました。進めてください。",
      wantOk: false,
    },
    {
      text: "パスワードの入力が必要です。https://example.com/login を開いて、ログインしてください。",
      wantOk: true,
    },
  ];
  let allOk = true;
  for (const c of cases) {
    const file = path.join(dir, "t.jsonl");
    writeFileSync(file, mk(c.text) + "\n");
    const text = saigoNoText(file);
    const r = hantei(text);
    if (r.ok !== c.wantOk) {
      allOk = false;
      console.error(`FAIL: ${JSON.stringify(c.text)} -> got ok=${r.ok} want ok=${c.wantOk}\n${r.out}`);
    }
  }
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {}
  console.log(`TANOMANAI_STOP_KANMON_SELFTEST: ${allOk ? "PASS" : "FAIL"}`);
  process.exit(allOk ? 0 : 1);
}

if (process.argv.includes("--self-test")) {
  selfTest();
}

const stdin = await readStdin();
let input = {};
try {
  input = JSON.parse(stdin || "{}");
} catch {}

const hook = input.hook_event_name || "Stop";
const tp = input.transcript_path;
const sid = input.session_id || "unknown";

try {
  if (!tp || !existsSync(tp)) process.exit(0); // 読めないなら人質にしない

  const text = saigoNoText(tp);
  if (!text) process.exit(0); // 最終応答が無ければ対象外

  const r = hantei(text);

  if (r.ok) {
    write({ event: "tanomanai", decision: "ok", hook, session: sid, out: r.out.slice(0, 300) });
    process.exit(0);
  }

  const already = blocksFor(sid);
  if (already >= MAX_BLOCK) {
    write({ event: "tanomanai", decision: "akirameta", hook, session: sid, out: r.out.slice(0, 500) });
    console.log(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: hook,
          additionalContext:
            `★最終応答が1773番の関所に${MAX_BLOCK}回引っかかったまま終わる。` +
            `「たまごさんにやってもらう」を最初の選択肢にしていないか、報告に明記すること。`,
        },
      }),
    );
    process.exit(0);
  }

  write({ event: "tanomanai", decision: "block", hook, session: sid, out: r.out.slice(0, 500) });
  console.error(
    [
      "終われない。**最終応答が『たまごさんにやってもらう』を最初の選択肢にしている。**",
      r.out,
      "",
      "いますぐやること：",
      "  1. お金／不可逆の削除／外部公開／パスワード・ログイン・権限承認のどれにも当たらないなら、",
      "     確認を求めず自分で安全な側を選んで進める（報告に「こう決めた」と書く）。",
      "  2. 当たる場合は、URL（開く場所）と具体的な操作（押す・入力する・承認する等）を言い切る。",
      "（台帳：status/1154_stop_kanmon.jsonl の event:\"tanomanai\"／判定：tools/1773_tanomanai_kanmon.py）",
    ].join("\n"),
  );
  process.exit(2);
} catch (e) {
  try {
    write({ event: "tanomanai", decision: "error", hook, session: sid, why: String(e && e.message) });
  } catch {}
  process.exit(0); // 関所が壊れてもセッションを人質にしない
}
