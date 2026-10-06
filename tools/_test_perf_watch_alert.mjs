#!/usr/bin/env node
// 429番：悪化検知ロジックの逆テスト（本物のstatus/は一切触らない）。
// 「見張りは必ず逆テストする」（緑は無実の証明ではない。違反を仕込んで赤になるまで確認する）。
import assert from "node:assert/strict";
import { computeAlert, findPrevRecord, isTodayFullyRecorded, PAGES } from "./perf_watch.mjs";

let pass = 0;
let fail = 0;
function check(label, cond) {
  if (cond) {
    pass++;
    console.log(`PASS: ${label}`);
  } else {
    fail++;
    console.log(`FAIL: ${label}`);
  }
}

// --- computeAlert: 悪化が10%未満なら鳴らない（誤検知しないことの逆テスト） ---
check("9%悪化は鳴らない", computeAlert({ key: "home", url: "u", prevLcpMs: 1000, newLcpMs: 1089 }) === null);
check("同値は鳴らない", computeAlert({ key: "home", url: "u", prevLcpMs: 1000, newLcpMs: 1000 }) === null);
check("改善(速くなった)は鳴らない", computeAlert({ key: "home", url: "u", prevLcpMs: 1000, newLcpMs: 500 }) === null);
check("prevがnullなら鳴らない", computeAlert({ key: "home", url: "u", prevLcpMs: null, newLcpMs: 2000 }) === null);
check("newがnullなら鳴らない", computeAlert({ key: "home", url: "u", prevLcpMs: 1000, newLcpMs: null }) === null);
check("prevが0以下なら鳴らない(0除算ガード)", computeAlert({ key: "home", url: "u", prevLcpMs: 0, newLcpMs: 2000 }) === null);

// --- computeAlert: ちょうど10%・それ以上は鳴る（見逃さないことの逆テスト） ---
const exactAlert = computeAlert({ key: "home", url: "https://x/", prevLcpMs: 1000, newLcpMs: 1100 });
check("ちょうど10%悪化は鳴る", exactAlert !== null && exactAlert.ok === false);
const bigAlert = computeAlert({ key: "cover_guide", url: "https://x/cg", prevLcpMs: 2000, newLcpMs: 3000 });
check("50%悪化は鳴る", bigAlert !== null);
check("鳴った時にn=429が付く", bigAlert?.n === 429);
check("鳴った時にurlsが入る", Array.isArray(bigAlert?.urls) && bigAlert.urls[0] === "https://x/cg");

// --- findPrevRecord: 同日を比較対象にしない(冪等性)の逆テスト ---
const hist = [
  { key: "home", date: "2026-09-04", lcp_ms: 1000 },
  { key: "home", date: "2026-09-05", lcp_ms: 1200 },
  { key: "home", date: "2026-09-06", lcp_ms: 9999 }, // 本日分(--forceで複数回計測した想定)
];
const prev = findPrevRecord(hist, "home", "2026-09-06");
check("findPrevRecordは本日分を無視し前日を返す", prev?.date === "2026-09-05" && prev?.lcp_ms === 1200);
check("該当keyが無ければnull", findPrevRecord(hist, "world_music", "2026-09-06") === null);

// --- isTodayFullyRecorded ---
const partial = [{ key: "home", date: "2026-09-06" }];
check("1/3ページしか無ければfalse", isTodayFullyRecorded(partial, "2026-09-06") === false);
const full = PAGES.map((p) => ({ key: p.key, date: "2026-09-06" }));
check("3/3ページ揃えばtrue", isTodayFullyRecorded(full, "2026-09-06") === true);

console.log(`\n---\nPASS(${pass}) FAIL(${fail}) / total ${pass + fail}`);
process.exit(fail === 0 ? 0 : 1);
