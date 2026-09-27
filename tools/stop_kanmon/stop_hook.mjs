#!/usr/bin/env node
// 1154号：Stop / SubagentStop フック本体。
//
// 公式（https://code.claude.com/docs/en/hooks）の Stop decision control をそのまま使う：
//   ・終了を拒否する＝ exit code 2。stderr の文字がそのまま「続ける理由」になる。
//   ・入力の stop_hook_active が true なら、すでにフックで続行中。
//     公式は8回連続ブロックで本体が上書きして終わらせる、と書いてあるので、
//     こちらも8回で引き際にし、代わりに引き継ぎを書いて、止まる。
//   ・止めない時に一言渡したいだけなら hookSpecificOutput.additionalContext。
//
// 落ちても続きから：判断材料は全部 status/1154_stop_kanmon.jsonl にある。
// このフックは記憶を一切持たない。

import { writeFileSync } from "node:fs";
import path from "node:path";
import { REPO, write, soukouchuu, kensa, keikaJikan, nowIso } from "./kanmon.mjs";

const MAX_BLOCK = 8; // 公式の上限に合わせる
const TIME_H = 6; // たまご憲法：6時間で引き継ぐ

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

function hikitsugi(c, why, proof) {
  const f = path.join(REPO, "status", `1154_hikitsugi_${c.id}.md`);
  writeFileSync(
    f,
    [
      `# ${c.id} 引き継ぎ（${nowIso()}）`,
      ``,
      `止まった理由：${why}`,
      `完了条件：${JSON.stringify(c.done)}`,
      `いまの実測：${JSON.stringify(proof)}`,
      `ブロック回数：${c.blocks}`,
      ``,
      `次の人へ：この1件は status/1154_stop_kanmon.jsonl に全部残っている。`,
      `\`node tools/stop_kanmon/ukeire.mjs miru\` で今の姿が出る。続きからやれる。`,
    ].join("\n") + "\n",
  );
  write({ id: c.id, event: "hikitsugi", hook, why, proof, file: path.relative(REPO, f) });
}

try {
  const cases = soukouchuu();
  if (cases.length === 0) process.exit(0);

  const riyuu = [];
  for (const c of cases) {
    const r = await kensa(c);
    if (r.ok) {
      write({ id: c.id, event: "kanryou", hook, proof: r.proof });
      continue;
    }
    // 引き際：8回ブロックした／6時間たった → 止めずに引き継ぎを残す
    if (c.blocks >= MAX_BLOCK || keikaJikan(c) >= (c.deadline_h ?? TIME_H)) {
      hikitsugi(c, r.why, r.proof);
      riyuu.push(`【引き継ぎに回した】${c.id} ${c.title}：${r.why}`);
      continue;
    }
    write({ id: c.id, event: "block", hook, why: r.why, proof: r.proof });
    riyuu.push(
      `${c.id}「${c.title}」はまだ終わっていない：${r.why}` +
        `（実測 status=${r.proof.status} bytes=${r.proof.bytes} diff=${r.proof.diff}／${c.blocks + 1}回目）`,
    );
  }

  if (riyuu.some((r) => !r.startsWith("【引き継ぎ"))) {
    console.error(
      ["終われない。台帳の完了条件を満たしていない案件がある：", ...riyuu].join("\n") +
        "\n（台帳：status/1154_stop_kanmon.jsonl ／ 見る：node tools/stop_kanmon/ukeire.mjs miru）",
    );
    process.exit(2); // ← 終了を拒否して続けさせる
  }

  if (riyuu.length > 0) {
    console.log(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: hook,
          additionalContext: riyuu.join("\n"),
        },
      }),
    );
  }
  process.exit(0);
} catch (e) {
  // 関所そのものが壊れてセッションを人質にしない（開いて通す）。ただし台帳には残す。
  try {
    write({ id: "_kanmon", event: "error", hook, why: String(e && e.message) });
  } catch {}
  process.exit(0);
}
