#!/usr/bin/env node
// 1161号：タブの関所。**自分が開いたタブを閉じずに終わろうとしたら、終了を拒否する。**
//
// たまごさん（2026-09-26・同じ指摘は10回目）：
//   「10回は言ってる。使ったら閉じろ。コンピューターを軽く保つのはあなたの重大な仕事。
//     9割方直らない。仕組みにしろ。」
//   「止めろ。AppleScript / System Events を使うな。TCC許可・画面操作が要る手段は全面禁止。
//     タブを閉じるのは Chrome MCP（tabs_close_mcp）だけ。届かないなら届かないと正直に書け。」
//
// ■ なぜこの作りなのか（ここが今日の学び）
//   ブラウザに何枚タブがあるかを外側から数えるには、どの道もmacOSのオートメーション許可
//   （TCC）が要る。常駐からそれを叩くと、たまごさんの画面に許可ダイアログが飛び出す。
//   → **枚数を数えにいかない。**代わりに**そのセッションの記録（transcript）を読む。**
//     「タブを作る道具を何回呼んだか」対「閉じる道具を何回呼んだか」。
//     これはOSに一切触らずに分かるし、ごまかせない（本当に tabs_close_mcp を
//     呼ばないと数が合わない）。許可ダイアログは出ない。0円。
//
// ■ 数えているもの
//   作った： mcp__claude-in-chrome__tabs_create_mcp
//            mcp__claude-in-chrome__navigate（tabId を渡していない呼び方＝勝手に1枚作る）
//            mcp__Claude_Browser__tabs_create / preview_start（内蔵ブラウザ）
//   閉じた： mcp__claude-in-chrome__tabs_close_mcp
//            mcp__Claude_Browser__tabs_close
//   ★browser_batch の中に入っている呼び出しも数える（input を丸ごと文字列で見る）。
//
// ■ 人質にしない（憲法）
//   ・transcript が読めない／形が違う → 何も言わずに通す（exit 0）
//   ・3回ブロックしても合わなければ、理由を台帳に残して通す（無限ループを作らない）
//
// 記録：status/1154_stop_kanmon.jsonl（event:"tab"）
//       status/public/tabs.json（進捗表がこれを読む）

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "1154_stop_kanmon.jsonl");
const PUB = path.join(REPO, "status", "public", "tabs.json");
const MAX_BLOCK = 3;

const OPEN_NAMES = [
  "mcp__claude-in-chrome__tabs_create_mcp",
  "mcp__Claude_Browser__tabs_create",
  "mcp__Claude_Browser__preview_start",
];
const CLOSE_NAMES = [
  "mcp__claude-in-chrome__tabs_close_mcp",
  "mcp__Claude_Browser__tabs_close",
];

function nowIso() {
  return new Date().toISOString();
}

function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: nowIso(), ...rec }) + "\n", { flag: "a" });
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

const hook = input.hook_event_name || "Stop";
const tp = input.transcript_path;
const sid = input.session_id || "unknown";

/** transcript を1行ずつ読み、道具の呼び出しを数える */
function kazoeru(file) {
  const raw = readFileSync(file, "utf8");
  let opened = 0,
    closed = 0,
    navNoTab = 0;
  const openUrls = [];
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
      const name = String(c.name || "");
      const inp = c.input || {};
      const inpStr = (() => {
        try {
          return JSON.stringify(inp);
        } catch {
          return "";
        }
      })();

      if (OPEN_NAMES.includes(name)) {
        opened += 1;
        if (inp.url) openUrls.push(String(inp.url).slice(0, 120));
        continue;
      }
      if (CLOSE_NAMES.includes(name)) {
        closed += 1;
        continue;
      }
      // navigate を tabId 無しで呼ぶと、向こうが勝手に1枚作る（公式の説明どおり）
      if (name === "mcp__claude-in-chrome__navigate" && inp.url && inp.tabId === undefined) {
        navNoTab += 1;
        openUrls.push(String(inp.url).slice(0, 120));
        continue;
      }
      // browser_batch の中身。名前が入っているだけ数える（丸ごと文字列で見る）
      if (name.endsWith("browser_batch")) {
        for (const n of OPEN_NAMES) {
          const short = n.split("__").pop();
          opened += (inpStr.match(new RegExp(`"${short}"`, "g")) || []).length;
        }
        for (const n of CLOSE_NAMES) {
          const short = n.split("__").pop();
          closed += (inpStr.match(new RegExp(`"${short}"`, "g")) || []).length;
        }
      }
    }
  }
  return { opened: opened + navNoTab, closed, navNoTab, openUrls };
}

/** 同じセッションで tab ブロックを何回出したか */
function blocksFor(sessionId) {
  try {
    if (!existsSync(DAICHO)) return 0;
    const raw = readFileSync(DAICHO, "utf8");
    let n = 0;
    for (const ln of raw.split("\n")) {
      if (!ln.trim()) continue;
      try {
        const o = JSON.parse(ln);
        if (o.event === "tab" && o.decision === "block" && o.session === sessionId) n += 1;
      } catch {}
    }
    return n;
  } catch {
    return 0;
  }
}

function kaku(r, decision) {
  try {
    mkdirSync(path.dirname(PUB), { recursive: true });
    let prev = {};
    try {
      prev = JSON.parse(readFileSync(PUB, "utf8"));
    } catch {}
    const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Tokyo" });
    const closedToday = (prev.day === day ? prev.closedToday || 0 : 0) + (r.closed || 0);
    writeFileSync(
      PUB,
      JSON.stringify(
        {
          day,
          at: new Date().toLocaleString("sv-SE", { timeZone: "Asia/Tokyo" }),
          // ★ここが「正直」の全部。ブラウザ全体の枚数はTCC無しでは数えられない。
          //   だから 0 とは書かない。数えられるのは「このセッションが開いた／閉じた数」だけ。
          source: "Stopフックがセッションの記録から数えた（OSには触っていない）",
          sessionOpened: r.opened,
          sessionClosed: r.closed,
          outstanding: Math.max(0, r.opened - r.closed),
          closedToday,
          chrome: null, // ブラウザ全体の枚数＝数えられていない（TCC禁止のため）
          brave: null, // 同じ
          braveNote: "Braveは新しく開かないことで0に保つ。既にあるタブには届かない＝数えられていない",
          unreachableNote:
            "MCPのタブグループ外のタブには届かない（tabs_context_mcp は自分の分しか返さない）",
          lastDecision: decision,
          lastSession: sid,
          openUrls: (r.openUrls || []).slice(0, 20),
        },
        null,
        1,
      ),
    );
  } catch {}
}

try {
  if (!tp || !existsSync(tp)) process.exit(0); // 読めないなら人質にしない
  const r = kazoeru(tp);
  const nokori = r.opened - r.closed;

  if (nokori <= 0) {
    if (r.opened > 0) write({ event: "tab", decision: "ok", hook, session: sid, proof: r });
    kaku(r, "ok");
    process.exit(0);
  }

  const already = blocksFor(sid);
  if (already >= MAX_BLOCK) {
    write({ event: "tab", decision: "akirameta", hook, session: sid, proof: r, why: `${MAX_BLOCK}回止めても合わなかった。無限ループにしないので通す` });
    kaku(r, "akirameta");
    console.log(
      JSON.stringify({
        hookSpecificOutput: {
          hookEventName: hook,
          additionalContext:
            `★タブが${nokori}枚閉じられていないまま終わった（開いた${r.opened}／閉じた${r.closed}）。` +
            `報告に「閉じる前◯枚→後◯枚／届かなかった分◯枚」を必ず書くこと。`,
        },
      }),
    );
    process.exit(0);
  }

  write({ event: "tab", decision: "block", hook, session: sid, proof: r });
  kaku(r, "block");
  console.error(
    [
      `終われない。**自分が開いたタブを閉じていない。**`,
      `開いた ${r.opened}枚 ／ 閉じた ${r.closed}枚 ／ 残り ${nokori}枚`,
      r.openUrls.length ? `開いた住所（先頭から）：\n  ` + r.openUrls.slice(0, 10).join("\n  ") : "",
      ``,
      `いますぐやること：`,
      `  1. tabs_context_mcp でこのセッションのタブ一覧を出す`,
      `  2. tabs_close_mcp で1枚ずつ閉じる（0枚にする）`,
      `  3. 閉じる前◯枚→後◯枚を報告に書く。グループ外で届かない分は「届かない」と書く`,
      `★AppleScript / System Events / osascript は禁止。閉じるのは Chrome MCP だけ。`,
      `（台帳：status/1154_stop_kanmon.jsonl の event:"tab"）`,
    ]
      .filter(Boolean)
      .join("\n"),
  );
  process.exit(2); // ← 終了を拒否
} catch (e) {
  try {
    write({ event: "tab", decision: "error", hook, session: sid, why: String(e && e.message) });
  } catch {}
  process.exit(0); // 関所が壊れてもセッションを人質にしない
}
