#!/usr/bin/env node
// 1166号：ブラウザの**入口の関所**（PreToolUse）。
// ★これは憲法である。文章ではなく機械で止める。
//
// たまごさん（2026-09-27。同じ指摘は何十回目）：
//   「Braveに Supabase、Claude。あなたが開いたものがいくつもある。Braveは使うのをやめてほしい。」
//   「Chromeも開いてるじゃん。Chromeでやってくれればいいのに未だにBraveでやる。
//     ここは作業場じゃないんだよね、Claudeの。Chromeを用意してあるんだから、そこでやってほしい。」
//   「会議室を使ったら椅子を整えて退出する、っていうのは基本だよね。」
//   「言い訳はいらないのでChrome使って」
//
// ■ なぜ Brave に行っていたのか（実測。憶測ではない）
//   2026-09-27 07:2x の list_connected_browsers の生の返り：
//     [{deviceId:"88704cda…"(Brave), connectedAt:1790446469336, inUse:true},
//      {deviceId:"7d965dae…"(Chrome), connectedAt:1790437734550}]
//     添え書き：「"Browser 1"(88704cda…) is the one picked last and will be used.」
//   → **後から繋がった／最後に選ばれた方が既定になる。** Braveの方が新しく繋がっていた。
//     子セッションが select_browser を呼ばずに navigate などを始めると、
//     何も宣言していないのに Brave に落ちる。これが原因。
//
// ■ 直し方（穴を塞ぐのでなくパイプを替える）
//   「気をつける」「プロンプトに書く」は何十回も効かなかった。だから**触れなくする。**
//   ブラウザ系の道具を呼ぶ前に、このセッションが select_browser(Chrome) を済ませていることを
//   強制する。済んでいない／Braveが選ばれているなら **exit 2 で道具ごと拒否**する。
//   設定は .claude/settings.json の PreToolUse に1か所だけ置く＝**全子セッションに効く。**
//
// ■ OSには一切触らない
//   AppleScript / osascript / System Events / TCC は使わない。
//   読むのはこのセッションの記録（transcript）だけ。許可ダイアログは出ない。0円。
//
// 台帳：status/1166_browser_kanmon.jsonl
// 進捗表用：status/public/browser.json（braveBlocked / braveUsed / chromeSelected）

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "1166_browser_kanmon.jsonl");
const PUB = path.join(REPO, "status", "public", "browser.json");
const CONF = path.join(REPO, "status", "browser_kanmon.json");

// 既定値（実測済み）。Chromeを入れ替えたら status/browser_kanmon.json で上書きできる。
let CONFIG = {
  chromeIds: ["7d965dae-93ae-48b8-b36f-50ba347fa98e"],
  braveIds: ["88704cda-a4dc-46d1-a19d-4b41696cc20c"],
  enabled: true,
};
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

const PREFIX = "mcp__claude-in-chrome__";
// ブラウザを選ぶ／見るだけの道具。これは通す（通さないと選べない）
const FREE = new Set([
  PREFIX + "list_connected_browsers",
  PREFIX + "select_browser",
  PREFIX + "switch_browser",
]);

function nowIso() {
  return new Date().toISOString();
}
function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: nowIso(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}
function pub(patch) {
  try {
    mkdirSync(path.dirname(PUB), { recursive: true });
    let prev = {};
    try {
      prev = JSON.parse(readFileSync(PUB, "utf8"));
    } catch {}
    const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Tokyo" });
    if (prev.day !== day) prev = { day, braveBlocked: 0, braveUsed: 0, chromeSelected: 0 };
    const next = { ...prev, day, at: new Date().toLocaleString("sv-SE", { timeZone: "Asia/Tokyo" }) };
    for (const [k, v] of Object.entries(patch)) {
      next[k] = typeof v === "number" ? (next[k] || 0) + v : v;
    }
    next.source = "1166号 入口の関所（PreToolUse）が数えた。OSには触っていない";
    writeFileSync(PUB, JSON.stringify(next, null, 1));
  } catch {}
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

const tool = String(input.tool_name || "");
const ti = input.tool_input || {};
const sid = input.session_id || "unknown";
const tp = input.transcript_path;

// ブラウザ以外の道具には関係しない
if (!CONFIG.enabled || !tool.startsWith(PREFIX)) process.exit(0);

const isBrave = (id) => CONFIG.braveIds.includes(String(id));
const isChrome = (id) => CONFIG.chromeIds.includes(String(id));

function deny(lines, rec) {
  write({ event: "browser", decision: "block", session: sid, tool, ...rec });
  console.error(lines.filter(Boolean).join("\n"));
  process.exit(2); // ★道具の実行を拒否
}

// ── ① Brave を選ぼうとした ──────────────────────────────
if (tool === PREFIX + "select_browser" || tool === PREFIX + "switch_browser") {
  if (isBrave(ti.deviceId)) {
    pub({ braveBlocked: 1 });
    deny(
      [
        "★Braveは使わない。これは憲法である（たまごさん：「Braveは使うのをやめてほしい」「言い訳はいらないのでChrome使って」）。",
        `拒否した deviceId：${ti.deviceId}（＝Brave）`,
        `Chromeを選べ： select_browser({ deviceId: "${CONFIG.chromeIds[0]}" })`,
        "Braveはたまごさんの作業場。こちらの作業場ではない。読むだけでも入らない。",
        "（台帳：status/1166_browser_kanmon.jsonl）",
      ],
      { why: "brave-select", deviceId: ti.deviceId },
    );
  }
  if (tool === PREFIX + "switch_browser" && !ti.deviceId) {
    deny(
      [
        "★switch_browser（相手を指定しない呼び方）は禁止。既定＝最後に繋がった方に落ちる＝Braveに行く。",
        `必ず名指しで： select_browser({ deviceId: "${CONFIG.chromeIds[0]}" })`,
      ],
      { why: "switch-broadcast" },
    );
  }
  if (isChrome(ti.deviceId)) {
    write({ event: "browser", decision: "ok", session: sid, tool, why: "chrome-select" });
    pub({ chromeSelected: 1 });
  } else if (ti.deviceId) {
    // 知らないIDは通す（Chromeを入れ替えた可能性）が、記録して目に見えるようにする
    write({ event: "browser", decision: "unknown-id", session: sid, tool, deviceId: ti.deviceId });
    pub({ lastUnknownId: String(ti.deviceId) });
  }
  process.exit(0);
}

if (FREE.has(tool)) process.exit(0);

// ── ② それ以外のブラウザ操作：Chromeを名指ししたか、記録で確かめる ──────
function lastSelected(file) {
  // 記録を上から読み、最後に select_browser / switch_browser に渡された deviceId を返す
  let last = null;
  let n = 0;
  const raw = readFileSync(file, "utf8");
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
      const nm = String(c.name || "");
      if (nm === PREFIX + "select_browser" || nm === PREFIX + "switch_browser") {
        const id = c.input?.deviceId;
        if (id) {
          last = String(id);
          n += 1;
        }
      }
    }
  }
  return { last, n };
}

let sel = { last: null, n: 0 };
try {
  if (tp && existsSync(tp)) sel = lastSelected(tp);
  else process.exit(0); // 記録が読めないなら人質にしない（憲法：仕組みが壊れても止めない）
} catch {
  process.exit(0);
}

if (!sel.last) {
  deny(
    [
      "★まだどのブラウザで作業するか名指ししていない。**この状態で動くと既定のBraveに落ちる。**",
      "実測（2026-09-27）：list_connected_browsers の返りで Brave が inUse:true ＝ 後から繋がった方が既定。",
      `いますぐ： select_browser({ deviceId: "${CONFIG.chromeIds[0]}" })  ← Chrome`,
      "そのうえで tabs_context_mcp からやり直すこと。",
      "（台帳：status/1166_browser_kanmon.jsonl）",
    ],
    { why: "no-select", tool },
  );
}
if (isBrave(sel.last)) {
  pub({ braveUsed: 1 });
  deny(
    [
      "★いまBraveが選ばれている。Braveで操作することは憲法違反。",
      `選ばれている deviceId：${sel.last}（＝Brave）`,
      `Chromeに移れ： select_browser({ deviceId: "${CONFIG.chromeIds[0]}" })`,
      "Braveでタブを開くと、セッションが終わった後だれも閉じられない（tabs_close_mcp は自分のグループしか閉じられない）。だから開かせない。",
    ],
    { why: "brave-active", deviceId: sel.last },
  );
}

write({ event: "browser", decision: "pass", session: sid, tool, deviceId: sel.last });
process.exit(0);
