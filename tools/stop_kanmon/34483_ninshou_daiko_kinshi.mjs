#!/usr/bin/env node
// 34483号：認証情報（ID／パスワード）の代理入力を**機械で**拒否する入口の関所（PreToolUse）。
// ★これは憲法である。文章ではなく機械で止める（1166号Brave禁止と同じ作り）。
//
// たまごさん（2026-08-05 05:11）：「認証情報(ID/パスワード)を代わりに入力することは禁止。」
// 1ヶ月以上「気をつける」で放置され判定日赤になった案件。既存の運用マニュアル
// （tools/session_watchdog.pyのMANUAL_ESSENTIALS⑥）には文章として書かれていたが、
// **実際に動くコマンドのexit codeで止める仕組みが無かった。** ここで機械化する。
//
// ■ 何を拒否するか
//   ブラウザ操作系（claude-in-chrome / computer-use）の道具呼び出しで、
//   tool_input を文字列化した中に「パスワード」「ID」等の認証情報を**入力しようとしている**
//   痕跡（パスワード欄らしきselector/description＋値、ID/パスワードという語、秘密鍵等）が
//   あれば、exit 2 で道具ごと拒否する。読み取り系（get_page_text等）は拒否しない
//   （ログイン済みかどうかの確認は害が無い。害があるのは「代わりに打ち込む」行為）。
//
// ■ なぜ文字列マッチという緩い判定か
//   claude-in-chrome／computer-useの正確な入力ツール名・引数スキーマはこの環境からは
//   確定できなかった（found: find/navigate/tabs_*/read_*のみ、type/fill系は未確認）。
//   ツール名を決め打ちすると、別名のツールから入力されたときに素通りする穴になる。
//   だから「ブラウザ系・画面操作系の道具すべて」を対象に、入力内容そのものを見る方が
//   漏れが少ない（1166号もBrave判定はdeviceIdの文字列一致、同じ発想）。
//
// ■ OSには一切触らない
//   AppleScript / osascript / System Events / TCC は使わない。読むのは
//   このツール呼び出しのtool_inputだけ。許可ダイアログは出ない。0円。
//
// 台帳：status/34483_ninshou_kanmon.jsonl
// 進捗表用：status/public/ninshou_kanmon.json（blocked / checked）
// 逆テスト：node tools/stop_kanmon/34483_ninshou_daiko_kinshi.mjs --self-test

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "34483_ninshou_kanmon.jsonl");
const PUB = path.join(REPO, "status", "public", "ninshou_kanmon.json");

// 対象にする道具（プレフィックス一致）。画面操作系すべて。
const TARGET_PREFIXES = ["mcp__claude-in-chrome__", "mcp__computer-use__", "mcp__Claude_Browser__"];

// 読み取るだけ・害が無い道具は通す（ここで止めると作業そのものができなくなる）
const READ_ONLY_SUFFIX = new Set([
  "list_connected_browsers",
  "select_browser",
  "switch_browser",
  "tabs_context_mcp",
  "tabs_close_mcp",
  "get_page_text",
  "read_console_messages",
  "read_network_requests",
  "read_page",
  "find", // 要素を「探す」だけなら害が無い。入力はfindの結果を使う別呼び出しで行われる
]);

// 認証情報を「代わりに入力している」と判定するキーワード（日英両方・表記ゆれ込み）
const NINSHOU_KEYWORDS = [
  /password/i,
  /passwd/i,
  /\bpwd\b/i,
  /パスワード/,
  /暗証番号/,
  /ログインID/,
  /ログイン\s*パスワード/,
  /\bid\s*\/\s*パスワード/i,
  /secret[_-]?key/i,
  /秘密鍵/,
  /api[_-]?key/i,
  /type\s*=\s*["']?password["']?/i, // <input type="password"> を狙った指定
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
function pub(patch) {
  try {
    mkdirSync(path.dirname(PUB), { recursive: true });
    let prev = {};
    try {
      prev = JSON.parse(readFileSync(PUB, "utf8"));
    } catch {}
    const day = new Date().toLocaleDateString("sv-SE", { timeZone: "Asia/Tokyo" });
    if (prev.day !== day) prev = { day, blocked: 0, checked: 0 };
    const next = { ...prev, day, at: new Date().toLocaleString("sv-SE", { timeZone: "Asia/Tokyo" }) };
    for (const [k, v] of Object.entries(patch)) {
      next[k] = typeof v === "number" ? (next[k] || 0) + v : v;
    }
    next.source = "34483号 入口の関所（PreToolUse）が数えた。OSには触っていない";
    writeFileSync(PUB, JSON.stringify(next, null, 1));
  } catch {}
}

function judge(toolName, toolInput) {
  const isTarget = TARGET_PREFIXES.some((p) => toolName.startsWith(p));
  if (!isTarget) return { skip: true };
  const suffix = toolName.split("__").pop() || "";
  if (READ_ONLY_SUFFIX.has(suffix)) return { skip: true };
  const blob = JSON.stringify(toolInput || {});
  const hit = NINSHOU_KEYWORDS.find((re) => re.test(blob));
  if (hit) return { skip: false, block: true, hit: String(hit) };
  return { skip: false, block: false };
}

async function main() {
  if (process.argv.includes("--self-test")) {
    const cases = [
      { name: "password入力を拒否", tool: "mcp__claude-in-chrome__type", input: { selector: "#password", text: "hunter2" }, expectBlock: true },
      { name: "日本語パスワードを拒否", tool: "mcp__computer-use__type_text", input: { label: "パスワード", value: "abcd1234" }, expectBlock: true },
      { name: "ID/パスワード同時入力を拒否", tool: "mcp__claude-in-chrome__fill_form", input: { fields: [{ name: "ログインID", value: "eggypop" }, { name: "password", value: "x" }] }, expectBlock: true },
      { name: "無関係な検索語入力は通す", tool: "mcp__claude-in-chrome__type", input: { selector: "#search", text: "today news" }, expectBlock: false },
      { name: "読み取り専用get_page_textは通す", tool: "mcp__claude-in-chrome__get_page_text", input: {}, expectBlock: false },
      { name: "navigateは対象外（入力ではない）だが語が無ければ通す", tool: "mcp__claude-in-chrome__navigate", input: { url: "https://example.com" }, expectBlock: false },
      { name: "対象外のBashツールはそもそもskip", tool: "Bash", input: { command: "echo password=1" }, expectBlock: false, expectSkip: true },
    ];
    let ok = 0;
    for (const c of cases) {
      const r = judge(c.tool, c.input);
      const blocked = !!r.block;
      const skipped = !!r.skip;
      const passSkip = c.expectSkip ? skipped : true;
      const pass = blocked === c.expectBlock && passSkip;
      console.log(`${pass ? "OK " : "NG "} ${c.name} -> block=${blocked} skip=${skipped}`);
      if (pass) ok += 1;
    }
    console.log(`\n${ok}/${cases.length} 件合格`);
    process.exit(ok === cases.length ? 0 : 1);
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

  const r = judge(tool, ti);
  if (r.skip) process.exit(0);

  pub({ checked: 1 });
  if (r.block) {
    pub({ blocked: 1 });
    write({ event: "ninshou", decision: "block", session: sid, tool, hit: r.hit });
    console.error(
      [
        "★認証情報（ID／パスワード）をAIが代わりに入力することは禁止（たまごさん指示 2026-08-05・34483号）。",
        `拒否した道具：${tool}`,
        "たまごさん本人に直接ログインしてもらってください。AIはログイン済みの画面を読む・操作することはできますが、",
        "ID・パスワード・暗証番号・秘密鍵の値を入力欄へ打ち込むことはできません。",
        "（台帳：status/34483_ninshou_kanmon.jsonl）",
      ].join("\n"),
    );
    process.exit(2);
  }

  write({ event: "ninshou", decision: "pass", session: sid, tool });
  process.exit(0);
}

main();
