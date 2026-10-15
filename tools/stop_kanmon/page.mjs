#!/usr/bin/env node
// 1154号：本番ページを台帳から機械で書き出す。手で数字を書き足さない。
//   node tools/stop_kanmon/page.mjs

import { writeFileSync } from "node:fs";
import path from "node:path";
import { REPO, read, jotai } from "./kanmon.mjs";

const rows = read();
const cases = jotai();
const block = rows.filter((r) => r.event === "block").length;
const kanryou = rows.filter((r) => r.event === "kanryou").length;
const hikitsugi = rows.filter((r) => r.event === "hikitsugi").length;
const now = new Date(Date.now() + 9 * 3600 * 1000)
  .toISOString()
  .replace("T", " ")
  .slice(0, 16);

const esc = (s) =>
  String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// 調べた事例（誰が／何を／出典URL）。出典が取れないものは載せていない。
const jirei = [
  ["Anthropic Claude Code", "Stop / SubagentStop フック。エージェントが終わろうとした瞬間に発火し、exit code 2 か <code>{\"decision\":\"block\"}</code> で<b>終了を拒否して続けさせる</b>。stderr の文字がそのまま「なぜ続けるか」の理由になる。暴走止めは <code>stop_hook_active</code> と「8回連続でブロックしたら本体が打ち切る」", "停止条件を外に置く", "https://code.claude.com/docs/en/hooks"],
  ["OpenAI Agents SDK", "output guardrail。エージェントの最終出力に対して別の判定を走らせ、<code>tripwire_triggered</code> が立つと <code>OutputGuardrailTripwireTriggered</code> を投げて最終出力を却下する。却下しても、済んだツール呼び出しはセッションに残す", "停止条件を外に置く", "https://openai.github.io/openai-agents-python/guardrails/"],
  ["LangChain / LangGraph", "interrupt と checkpointer。止めるには checkpointer が必須で、状態は毎スーパーステップ外に保存される。再開はノードの途中からではなく<b>ノードの頭から再実行</b>されるので、副作用は冪等でないといけない", "進捗をファイルに落とす", "https://docs.langchain.com/oss/python/langgraph/interrupts"],
  ["Temporal", "ワークフロー永続化。LLM呼び出しもツール呼び出しも Activity として追記専用のイベント履歴に載る。落ちても最後に終わった一歩から自動で再開する。履歴は無限ではないので Continue-As-New で畳む", "進捗をファイルに落とす", "https://temporal.io/solutions/ai"],
  ["AutoGen", "termination condition。ターン数か合言葉で会話を止める。＝<b>回数と文字列でしか止められない</b>（同じツール呼び出しの繰り返しは見ていない）", "停止条件を外に置く（ただし浅い）", "https://theneuralbase.com/autogen/learn/intermediate/team-termination-conditions/"],
  ["CrewAI", "max_iter。上限に当たると「精一杯の答え」を返すが、<b>打ち切られたという印が付かない</b>。受け取る側は完了と見分けられない、と本家のissueに書かれている", "停止条件を外に置く（ただし浅い）", "https://github.com/crewAIInc/crewAI/issues/6414"],
];

// 失敗例・やめた理由
const shippai = [
  ["チェックポイント＝永続実行だと思っていた", "LangGraph・CrewAI・Google ADK のチェックポイントは「状態の保存」であって「落ちた所からの再開」ではない、と外部が指摘。InMemorySaver はプロセスが死ぬと消える", "https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows"],
  ["止まらないループ（IAL）", "論文いわく、有効な終了条件が無いままLLM呼び出し・ツール呼び出し・エージェント遷移が繰り返される失敗を Infinite Agentic Loop と呼ぶ", "https://arxiv.org/html/2607.01641v1"],
  ["max_iterations の固定上限をやめた", "収束したかを見ずに回数で切ると、金を焼いたうえに劣化した答えが残る。回数ではなく収束で止めて巻き戻す道具（LoopGain）が出ている", "https://github.com/loopgain-ai/loopgain"],
];

const hooks = [
  ["Stop", "node tools/stop_kanmon/stop_hook.mjs", "本体が終わろうとした時。走行中の案件が完了条件を満たしていなければ <b>exit 2 で終了を拒否</b>"],
  ["SubagentStop", "node tools/stop_kanmon/stop_hook.mjs", "子セッション（サブエージェント）が終わろうとした時。同じ判定で拒否"],
  ["UserPromptSubmit", "node tools/stop_kanmon/prompt_gate.mjs", "「発車して」と言われたのに完了条件が1行で書けていない依頼を <b>exit 2 で弾く</b>"],
  ["SessionEnd", "node tools/stop_kanmon/session_end.mjs", "公式いわく止める権限は無い。走行中のまま消えた案件を台帳に残すだけ"],
];

const html = `<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>止まれない関所（Stopフック）</title>
<style>
:root{--ink:#16130f;--sub:#6b6259;--line:#e5ded4;--bg:#faf7f2;--red:#c0392b;--amber:#b7791f;--gr:#1e7a3c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px 14px 64px}
h1{font-size:20px;margin:0 0 4px;letter-spacing:.02em}
h2{font-size:15px;margin:28px 0 8px}
.sub{color:var(--sub);font-size:12px;margin:0 0 18px}
.big{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 10px}
.big>div{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 10px;text-align:center}
.big b{display:block;font-size:44px;line-height:1.05;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.big span{font-size:12px;color:var(--sub)}
.big .ng b{color:var(--red)}
.big .okk b{color:var(--gr)}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
 border-radius:10px;overflow:hidden;font-size:13px}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f3ede4;font-size:11px;color:var(--sub);font-weight:600;white-space:nowrap}
td.d{white-space:nowrap;color:var(--sub);font-size:11.5px}
td.g{color:var(--sub);font-size:11.5px}
code{background:#f3ede4;border-radius:4px;padding:1px 4px;font-size:12px}
a{color:#1c5fa8}
.s{font-size:11px;padding:2px 7px;border-radius:99px;white-space:nowrap;display:inline-block}
.s.ok{background:#e3f3e6;color:var(--gr)}
.s.run{background:#e4eefb;color:#1c5fa8}
.s.stop{background:#fbe3e0;color:#a6301f}
.s.yet{background:#efeae3;color:#6b6259}
pre{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px;overflow:auto;font-size:11.5px;line-height:1.6}
.note{margin:18px 0 0;font-size:11.5px;color:var(--sub);line-height:1.9}
@media(max-width:640px){.big b{font-size:34px}}
</style>
<div class="wrap">
<h1>止まれない関所（Stopフック）</h1>
<p class="sub">終わろうとした瞬間に機械が止める仕組み。数字は台帳 <code>status/1154_stop_kanmon.jsonl</code> から機械で数えたもの。${now} 時点。手で書き足していません。</p>

<div class="big">
 <div class="ng"><b>${block}</b><span>実際にブロックが発火した回数</span></div>
 <div class="okk"><b>${kanryou}</b><span>完了条件を満たして通した回数</span></div>
 <div><b>${hikitsugi}</b><span>引き継ぎに回した回数</span></div>
</div>

<h2>入れたフック</h2>
<table><thead><tr><th>フック</th><th>走るもの</th><th>何をするか</th></tr></thead><tbody>
${hooks.map(([a, b, c]) => `<tr><td><code>${a}</code></td><td class="g"><code>${esc(b)}</code></td><td>${c}</td></tr>`).join("\n")}
</tbody></table>
<p class="note">書き方は公式そのまま（<code>.claude/settings.json</code> の <code>hooks</code> → matcher群 → <code>type:"command"</code>）。終了の拒否は exit code 2、理由は stderr。オリジナルの書き方はしていません。</p>

<h2>世界のトップランナーはどう止めているか</h2>
<table><thead><tr><th>誰が</th><th>何を</th><th>型</th><th>出典</th></tr></thead><tbody>
${jirei.map(([a, b, c, u]) => `<tr><td>${a}</td><td>${b}</td><td class="g">${c}</td><td class="d"><a href="${u}">出典</a></td></tr>`).join("\n")}
</tbody></table>
<p class="note">共通していたのは2つだけ。<b>①停止条件をエージェントの外に置く（自分で「終わった」と言わせない）</b>　<b>②進捗を毎回ファイルに落とす（記憶に置かない）</b>。この2つを満たしていない止め方（回数だけ・合言葉だけ）は、下の失敗例のとおり事故になっている。</p>

<h2>失敗例・やめた理由</h2>
<table><thead><tr><th>やめたこと</th><th>なぜ</th><th>出典</th></tr></thead><tbody>
${shippai.map(([a, b, u]) => `<tr><td>${a}</td><td>${b}</td><td class="d"><a href="${u}">出典</a></td></tr>`).join("\n")}
</tbody></table>

<h2>いまの案件</h2>
<table><thead><tr><th>番号</th><th>題名</th><th>状態</th><th>ブロック</th><th>完了条件</th></tr></thead><tbody>
${cases
  .map((c) => {
    const st = c.kanryou
      ? '<span class="s ok">完了</span>'
      : c.hikitsugi
        ? '<span class="s stop">引き継ぎ</span>'
        : c.hassha
          ? '<span class="s run">走行中</span>'
          : '<span class="s yet">受付のみ</span>';
    return `<tr><td>${esc(c.id)}</td><td>${esc(c.title)}</td><td>${st}</td><td>${c.blocks}回</td><td class="g">${esc(c.done?.url ?? "")} が200・${esc(c.done?.min_bytes ?? "")}バイト以上・差分${esc(c.done?.min_diff ?? "")}件以上</td></tr>`;
  })
  .join("\n")}
</tbody></table>

<h2>台帳の生ログ（最後の12行）</h2>
<pre>${esc(rows.slice(-12).map((r) => JSON.stringify(r)).join("\n"))}</pre>
<p class="note">この台帳は追記だけ。状態ファイルを別に持たず、頭から再生して今の姿を作っている（Temporalのイベント履歴と同じ形）。だから落ちても、このファイルさえ残っていれば続きから走れる。</p>
</div>
`;

const out = path.join(REPO, "1154-tomaranai.html");
writeFileSync(out, html);
console.log(`書いた：${out}（${Buffer.byteLength(html)}バイト／ブロック${block}回）`);
