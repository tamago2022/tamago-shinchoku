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

// ---------------------------------------------------------------------------
// 1180号（2026-09-28）言われたことを取りこぼさない受け皿。
//   たまごさん：「前回は散々言ったのに半分も伝わってなくて、後ろを振り返りながら進むことになった」
//   後からまとめて思い出すから漏れる。→ **言われたその場で1行ずつ**落とす。
//   ① status/1180_iwareta.jsonl に全行そのまま（判断しない・捨てない）
//   ② 指示・叱責・決め事に見える行だけ、既存の受付台帳(tools/daicho.py --ireru)へ。
//      同じことは新しい行にならず **回数が+1される**（kaisu>=3 が引き継ぎの先頭に出る）。
//   新種は発明していない。受け皿は既存の daicho.json のまま。
//   絶対に止めない（ここで止めるとたまごさんの発言自体が通らなくなる）。
// ---------------------------------------------------------------------------
try {
  const { appendFileSync, mkdirSync } = await import("node:fs");
  const { spawnSync } = await import("node:child_process");
  const path = (await import("node:path")).default;
  const REPO = path.resolve(new URL("../..", import.meta.url).pathname);
  const at = new Date().toISOString();

  const lines = String(p)
    .split(/\r?\n|。/)
    .map((s) => s.trim())
    .filter((s) => s.length >= 6 && s.length <= 140)
    .filter((s) => !/^https?:\/\//.test(s) && !/^[`#|\-*>]/.test(s));

  const SHIJI =
    /(して(ください|くれ|ね|おいて)?$|しないで|やめて|禁止|だめ|ダメ|絶対|毎回|必ず|忘れ|二度と|決め(た|る)|ルール|変えて|直して|入れて|出して|作って|消して|言った(のに|よね)|何回|また同じ)/;

  if (lines.length) {
    mkdirSync(path.join(REPO, "status"), { recursive: true });
    appendFileSync(
      path.join(REPO, "status", "1180_iwareta.jsonl"),
      JSON.stringify({ at, lines }) + "\n",
    );
    // 台帳へ入れるのは最大3行まで（UserPromptSubmitは15秒で切られる）
    const hits = lines.filter((s) => SHIJI.test(s)).slice(0, 3);
    for (const s of hits) {
      spawnSync("python3", [path.join(REPO, "tools", "daicho.py"), "--ireru", s], {
        timeout: 4000,
        stdio: "ignore",
      });
    }
  }
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
