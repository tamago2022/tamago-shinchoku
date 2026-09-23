#!/usr/bin/env node
// 1154号：UserPromptSubmit フック。曖昧な「発車」を機械が弾く。
//
// 公式（https://code.claude.com/docs/en/hooks）：UserPromptSubmit は exit code 2 で
// プロンプトそのものを拒否できる。stderr の文字が理由としてClaudeに渡る。
//
// 弾く条件：文中に「発車」「着手」「始めて」があるのに、
//   ・URL（https://…）が無い、または
//   ・「完了条件」「終わったと言える」等の一行が無い
// → 何をもって終わりなのかが決まっていない依頼＝走らせない。

const stdin = await new Promise((res) => {
  let s = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (d) => (s += d));
  process.stdin.on("end", () => res(s));
  setTimeout(() => res(s), 3000);
});

let p = "";
try {
  p = JSON.parse(stdin || "{}").prompt || "";
} catch {}

const hasshaGo = /(発車|着手|始めて|やって走らせ)/.test(p);
const url = /https?:\/\/\S+/.test(p);
const jouken = /(完了条件|終わったと言える|done|200で|検収)/.test(p);

if (hasshaGo && !(url && jouken)) {
  console.error(
    "この依頼は発車させない。完了条件が1行で書けていない。\n" +
      "要るもの：①本番URL（https://…）②何をもって完了か（200で返る・中身が何バイト以上・差分が何件以上）。\n" +
      "受け方： node tools/stop_kanmon/ukeire.mjs uke <id> \"<題名>\" <URL> <最低バイト> <最低差分>",
  );
  process.exit(2);
}
process.exit(0);
