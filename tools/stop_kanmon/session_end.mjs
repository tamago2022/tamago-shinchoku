#!/usr/bin/env node
// 1154号：SessionEnd フック。公式いわく SessionEnd に決定権は無い（止められない）。
// だから「止める」ではなく「走ったまま消えたものを台帳に残す」だけをやる。
// 次のセッションは台帳を読めば、続きからやれる。

import { soukouchuu, write } from "./kanmon.mjs";

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 2000);
});
let reason = "other";
try {
  reason = JSON.parse(stdin || "{}").reason || "other";
} catch {}

for (const c of soukouchuu()) {
  write({ id: c.id, event: "session_end", why: `走行中のままセッションが終わった（${reason}）` });
}
process.exit(0);
