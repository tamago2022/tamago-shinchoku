#!/usr/bin/env node
// 1186号【Chrome起動禁止の関所】2026-09-29
//
// たまごさん（2026-09-29 深夜・一晩で5回）：
//   「Chromeの『どなたが使用しますか？』が画面の中央に繰り返し出てくる。避けてもまた中央に出る。」
//   「Chromeを起動・再起動する処理を全部止める。例外なし。タブ掃除も含めて止める。
//     たまごさんの邪魔をするくらいなら、タブが残る方がまし。」
//   「二度と『Chromeを起動する』処理を誰も書けないようにする。」
//
// ■ 何が起きていたか（実測・これがこの関所の存在理由）
//   tools/1401_cdp_arm.py が
//     pkill -TERM -x "Google Chrome" → open -a "Google Chrome" --args --remote-debugging-port=9222
//   をやっていた。Chrome 153 は既定プロファイルでの --remote-debugging-port を無効化しているので
//   ポートは永久に開かず、失敗の枝で「1回だけ」の印(status/.1401_armed_once)を**消していた**。
//   ＝2分おきに永久に Chrome を殺して開き直す。開き直すとプロファイル選択画面が画面中央に出る。
//
// ■ 何を止めるか（Bash / Write / Edit / MultiEdit の中身を見る）
//   ① Chromeを開く：open -a "Google Chrome" / open -na ... / Chrome.app/Contents/MacOS/Google Chrome
//   ② CDPで開き直す：--remote-debugging-port
//   ③ Chromeを終了させる（終了→再起動の前半）：pkill / killall / kill -TERM の対象が Google Chrome
//   ④ 止めた便を launchd に載せ直す：com.tamago.chrome-tab-cdp を load / bootstrap / kickstart
//   ⑤ osascript で Chrome を触る（許可ダイアログが出る）
//
// ■ 止めないもの
//   ・.md / .txt / .json（記録・台帳。事実を書くのは自由）
//   ・この関所自身と、既に止めてある 1401 系のファイル（止める側の修理を人質にしない）
//   ・Brave / Claude in Chrome の MCP（タブを読む・押すのは別の関所の管轄）
//   ・記録が読めない・形が違う → 黙って通す（exit 0）。人質にしない。
//
// 台帳：status/1186_chrome_kidou.jsonl
// OSには触らない。AppleScript / osascript / System Events は1行も使わない。

import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "1186_chrome_kidou.jsonl");
const CONF = path.join(REPO, "status", "1186_chrome_kidou.json");

let CONFIG = { enabled: true };
try {
  if (existsSync(CONF)) CONFIG = { ...CONFIG, ...JSON.parse(readFileSync(CONF, "utf8")) };
} catch {}

// ── 止める形 ───────────────────────────────────────────────
const RULES = [
  {
    name: "open-chrome",
    rx: /\bopen\b[^\n;|&]*-[a-zA-Z]*a[a-zA-Z]*\s+["']?(\/Applications\/)?Google Chrome(\.app)?["']?/i,
    say: 'open -a "Google Chrome"（＝プロファイル選択画面が画面中央に出る）',
  },
  {
    name: "chrome-binary",
    rx: /Google Chrome\.app\/Contents\/MacOS\/Google Chrome/,
    say: "Chrome本体のバイナリを直接起動している",
  },
  {
    name: "cdp-port",
    rx: /--remote-debugging-port/,
    say: "--remote-debugging-port（Chromeを開き直さないと付けられない＝必ず再起動になる）",
  },
  {
    name: "kill-chrome",
    rx: /\b(pkill|killall)\b[^\n;|&]*["']?Google Chrome["']?/i,
    say: "Chromeを終了させている（終了→再起動の前半。タブごと持っていかれる）",
  },
  {
    name: "relaunch-cdp-bin",
    rx: /(launchctl\s+(load|bootstrap|kickstart|enable)[^\n]*|cp[^\n]*LaunchAgents[^\n]*)com\.tamago\.chrome-tab-cdp/i,
    say: "止めてある Chromeタブ掃除便（com.tamago.chrome-tab-cdp）を載せ直している",
  },
  {
    name: "osascript-chrome",
    rx: /osascript[^\n]*Google Chrome|tell application ["']Google Chrome["']/i,
    say: "osascript で Chrome を触っている（たまごさんの画面に許可ダイアログが出る）",
  },
];

// ── 見に行かないファイル（記録と、止める側そのもの）────────────────
const EXEMPT_PATH = [
  /\.(md|txt|jsonl|log|html)$/i,
  /stop_kanmon\/1186_/,
  /status\/1186_/,
  /tools\/1401_(cdp_arm|tab_cdp|cdp_run|install)\./,
  /tools\/(chrome_tab_sweeper|launch_watchdog|heartbeat|machine_status_push)\./,
];

function write(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", {
      flag: "a",
    });
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

if (!CONFIG.enabled) process.exit(0);

const tool = String(input.tool_name || "");
const ti = input.tool_input || {};
const sid = String(input.session_id || "unknown");

// 見る場所：Bashならコマンド、書き込み系なら書き込む中身だけ（既存の中身は見ない）
let subject = "";
const fp = String(ti.file_path || "");
if (tool === "Bash") {
  subject = String(ti.command || "");
} else if (tool === "Write") {
  subject = String(ti.content || "");
} else if (tool === "Edit") {
  subject = String(ti.new_string || "");
} else if (tool === "MultiEdit") {
  subject = (ti.edits || []).map((e) => String(e?.new_string || "")).join("\n");
} else {
  process.exit(0);
}
if (!subject) process.exit(0);
if (fp && EXEMPT_PATH.some((rx) => rx.test(fp))) process.exit(0);

for (const r of RULES) {
  if (!r.rx.test(subject)) continue;
  write({ event: "chrome_kidou", decision: "block", session: sid, tool, file: fp, rule: r.name });
  console.error(
    [
      "★Chromeを起動・再起動する処理は憲法で禁止。拒否した。（1186号）",
      `　引っかかった形：${r.say}`,
      "",
      "たまごさん（2026-09-29）：",
      "　「Chromeを起動・再起動する処理を全部止める。例外なし。タブ掃除も含めて止める。",
      "　　たまごさんの邪魔をするくらいなら、タブが残る方がまし。」",
      "",
      "なぜ：Chromeを開き直すと『Chrome はどなたが使用しますか？』が画面の**中央**に出る。",
      "　　　たまごさんが下に避けても、また中央に出る。一晩で5回、作業を止めた。",
      "",
      "代わりに使うもの：",
      "　・ページを読む → web_fetch / curl（心臓経由：status/oneshot/pending/*.sh）",
      "　・画面を見る　 → 既に開いているタブを Claude in Chrome の MCP で読む（新しく開かない）",
      "　・スクリーンショット → 既存の headless 実装を使う場合も、この関所を外さずに",
      "　　　たまごさんへ「何のために要るか」を1行で聞いてから。黙って開かない。",
      "",
      "★この関所を外して通す道は用意していない。外すなら status/1186_chrome_kidou.json に",
      "　{\"enabled\": false} を書く＝たまごさんが自分で判断したときだけ。",
      "（台帳：status/1186_chrome_kidou.jsonl）",
    ].join("\n"),
  );
  process.exit(2);
}

process.exit(0);
