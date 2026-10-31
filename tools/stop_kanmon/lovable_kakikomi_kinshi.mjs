#!/usr/bin/env node
// 憲法（2026-10-22・たまごさん厳命「Lovableに勝手に書き込むな。厳格に禁止」）：
// Lovable のチャット（send_message）・エディタ入力・API による書き込みを、AI は一切しない。
// 許されるのは「読む」道具と「公開を押す」deploy_project だけ。白名簿は tools/lovable_kinshi.py と同じ。
//
// きっかけ：2026-10-10 21:30:33 JST、プロジェクト 8ebdb648-… のチャットに
//   「新しい特集記事ページを1本作ってください（オーナー承認済み）…/feature/ekkyo…」が送られた。
//
// 何を止めるか（PreToolUse・exit 2）：
//   ① Lovable の MCP 道具で白名簿外のもの（send_message・create/initiate/remix_project・
//      set_*_knowledge・*_workspace_skill・add_connector・enable_database・respond_to_approval・
//      set_*_visibility・move_projects_to_folder・get_file_upload_url・import-claude-design-from-url）。
//      Lovable の道具かどうか：サーバー名に lovable／既知の接続ID／引数に Lovable の project_id か lovable の語。
//      query_database は SELECT だけ通す。
//   ② ブラウザ／画面操作で lovable.dev のエディタに入力・クリックする（読むだけの道具は通す）。
//   ③ Bash で mcp.lovable.dev／lovable.dev の API に、白名簿外の道具名や chat/message を送るコマンド。
// OSには触らない。台帳：status/lovable_kinshi.jsonl
// 逆テスト：node tools/stop_kanmon/lovable_kakikomi_kinshi.mjs --self-test

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";

const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
const DAICHO = path.join(REPO, "status", "lovable_kinshi.jsonl");

const YURUSU = new Set([
  "deploy_project", "get_project", "get_me", "get_workspace", "get_message", "get_diff",
  "get_database_status", "get_project_analytics", "get_project_analytics_trend",
  "get_project_knowledge", "get_workspace_knowledge", "get_workspace_skill",
  "list_projects", "list_workspaces", "list_messages", "list_edits", "list_files",
  "list_connectors", "list_custom_connectors", "list_design_systems",
  "list_template_projects", "list_workspace_skills",
  "read_file", "query_database", "render_project_widget",
]);
// Lovable にしか無い名前（サーバー名が数字の接続でも Lovable と分かる）
const LOVABLE_DAKE = new Set([
  "initiate_project", "remix_project", "set_project_knowledge", "set_workspace_knowledge",
  "create_workspace_skill", "update_workspace_skill", "delete_workspace_skill",
  "respond_to_approval", "import-claude-design-from-url", "move_projects_to_folder",
  "set_folder_visibility", "set_project_visibility", "list_edits", "get_project_knowledge",
  "render_project_widget", "list_design_systems", "list_template_projects",
]);
// 既知の Lovable 接続ID（Cowork のコネクタ名）
const LOVABLE_SERVER_IDS = ["1eb9c4c0-3f2e-476d-819a-efed3f3fba5f"];
const PROJECT_IDS = ["8ebdb648-3686-4457-b42c-d01c493793b1"];
const SQL_YOMU = /^\s*(select|with|explain|show)\b/i;
const SQL_KAKU = /\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|upsert)\b/i;
const BROWSER_READ = new Set([
  "tabs_context_mcp", "tabs_context", "get_page_text", "read_page", "find",
  "read_console_messages", "read_network_requests", "tabs_close_mcp", "tabs_close",
  "list_connected_browsers", "select_browser", "switch_browser", "screenshot",
]);

export function handan(toolName, input) {
  const name = String(toolName || "");
  const s = JSON.stringify(input || {});
  const parts = name.split("__");
  const server = parts.length >= 3 ? parts[1] : "";
  const suffix = parts[parts.length - 1];

  // ① MCP
  if (name.startsWith("mcp__")) {
    const isBrowser = /claude-in-chrome|Claude_Browser|computer-use/.test(server);
    if (!isBrowser) {
      const isLovable =
        /lovable/i.test(server) ||
        LOVABLE_SERVER_IDS.includes(server) ||
        LOVABLE_DAKE.has(suffix) ||
        PROJECT_IDS.some((p) => s.includes(p)) ||
        (/"project_id"/.test(s) && /lovable/i.test(s)) ||
        (suffix === "send_message" && /"project_id"/.test(s));
      if (isLovable) {
        if (!YURUSU.has(suffix)) return [false, `Lovableへの書き込みは全面禁止（${suffix}）。読む道具と deploy_project だけ。コードは GitHub へ push`];
        if (suffix === "query_database") {
          const sql = String((input || {}).sql || (input || {}).query || "");
          if (!SQL_YOMU.test(sql) || SQL_KAKU.test(sql)) return [false, "Lovable の query_database は SELECT だけ"];
        }
      }
      return [true, ""];
    }
    // ② ブラウザで lovable.dev のエディタに触る
    if (/lovable\.dev/i.test(s) && !BROWSER_READ.has(suffix)) {
      const action = String((input || {}).action || "");
      if (!/^(screenshot|scroll|zoom|wait)$/.test(action) || suffix !== "computer") {
        return [false, "lovable.dev のエディタにブラウザで入力・操作するのは禁止（読むだけ可）"];
      }
    }
    return [true, ""];
  }

  // ③ Bash
  if (name === "Bash") {
    const cmd = String((input || {}).command || "");
    if (/lovable\.dev/i.test(cmd)) {
      if (/send_message|\/chat\b|\/messages?\b|create_project|initiate_project|remix_project|set_project_knowledge|respond_to_approval/i.test(cmd)) {
        return [false, "Bash から Lovable のチャット／書き込みAPIを叩くのは禁止"];
      }
    }
  }
  return [true, ""];
}

function kiroku(rec) {
  try {
    mkdirSync(path.dirname(DAICHO), { recursive: true });
    writeFileSync(DAICHO, JSON.stringify({ at: new Date().toISOString(), ...rec }) + "\n", { flag: "a" });
  } catch {}
}

function selfTest() {
  const ng = [
    ["mcp__lovable__send_message", { project_id: "x", message: "作って" }],
    ["mcp__1eb9c4c0-3f2e-476d-819a-efed3f3fba5f__send_message", { project_id: "8ebdb648-3686-4457-b42c-d01c493793b1", message: "a" }],
    ["mcp__abc__send_message", { project_id: "p1", message: "新しい特集" }],
    ["mcp__abc__remix_project", { project_id: "p1" }],
    ["mcp__lovable__query_database", { project_id: "x", sql: "update t set a=1" }],
    ["mcp__claude-in-chrome__computer", { action: "type", text: "作って", url: "https://lovable.dev/projects/8ebdb648" }],
    ["Bash", { command: "curl -X POST https://mcp.lovable.dev -d '{\"name\":\"send_message\"}'" }],
  ];
  const ok = [
    ["mcp__lovable__deploy_project", { project_id: "x" }],
    ["mcp__1eb9c4c0-3f2e-476d-819a-efed3f3fba5f__list_messages", { project_id: "x" }],
    ["mcp__lovable__query_database", { project_id: "x", sql: "select 1" }],
    ["mcp__86f261aa-fc59-4cd8-a257-af25ab444ed3__send_message", { to: "a@b", subject: "s", body: "b" }],
    ["mcp__claude-in-chrome__get_page_text", { url: "https://lovable.dev/x" }],
    ["Bash", { command: "python3 tools/koukai_kakunin.py --id" }],
  ];
  let bad = 0;
  for (const [n, i] of ng) if (handan(n, i)[0]) { console.log("NGのはずが通った:", n); bad++; }
  for (const [n, i] of ok) if (!handan(n, i)[0]) { console.log("OKのはずが止まった:", n, handan(n, i)[1]); bad++; }
  console.log("lovable_kakikomi_kinshi self-test:", bad ? `FAIL ${bad}` : "PASS");
  process.exit(bad ? 1 : 0);
}

if (process.argv.includes("--self-test")) selfTest();
else {
  let raw = "";
  try { raw = readFileSync(0, "utf8"); } catch {}
  let ev = {};
  try { ev = JSON.parse(raw || "{}"); } catch { process.exit(0); }
  const [ok, why] = handan(ev.tool_name, ev.tool_input);
  if (!ok) {
    kiroku({ tool: ev.tool_name, why, session: ev.session_id || "" });
    process.stderr.write(`【関所・Lovable書き込み禁止】${why}\n（憲法 2026-10-22：Lovable のチャット・エディタ・APIにAIが書き込むのは全面禁止。公開は deploy_project だけ）\n`);
    process.exit(2);
  }
  process.exit(0);
}
