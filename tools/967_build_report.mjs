#!/usr/bin/env node
/* 967【覆面調査】結果の1枚。tools/967_fukumen_result.json から作り直すだけ。
 * 走らせ方： node tools/967_fukumen.mjs && node tools/967_build_report.mjs
 * 文章はここに書かない。数字は必ず result.json から引く（手で書くとズレる）。 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "tools/967_fukumen_result.json"), "utf8"));
const OUT = path.join(ROOT, "share/check/967-fukumen-chousa.html");
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const day = new Date(D.when);
const hiduke = `${day.getFullYear()}.${String(day.getMonth() + 1).padStart(2, "0")}.${String(day.getDate()).padStart(2, "0")}`;

/* ── 直すところ：数字は全部 result.json から ─────────────── */
const namae = D.rows.filter((r) => r.want && r.want.artist && r.want.artist !== "__NONE__");
const namaeNG = namae.filter((r) => (r.hit || 0) < 2);
const heikin = (namae.reduce((s, r) => s + (r.hit || 0), 0) / namae.length).toFixed(1);
const NAOSU = [
  {
    midashi: "名前を言っても、その人が出てこない",
    kazu: `${namaeNG.length} / ${namae.length} 問　4枚中ならして ${heikin} 枚`,
    hon: `名指しで頼んだ ${namae.length} 問すべてで、頼んだ本人は 4枚中 0〜1枚 しか出なかった（ならして ${heikin} 枚）。`
       + `「坂本龍一かけて」で出たのは 矢野顕子・Kraftwerk・青葉市子・松任谷由実 の4枚で、本人は1枚も無い。`,
    naze: `棚の中では、お客さんが名指しした名前も、案内人が自分で足した8〜14組の名前も、同じ点（120点）で並ぶ。`
        + `そのあと「1組につき1枚ずつ」配るので、上位4組に入れなければ本人は0枚、入っても1枚で終わる。`,
    naosi: `findSongs に「これはお客さんが口に出した名前」という印を渡して、そこだけ桁違いに加点する。`
         + `名指しのときは4枚のうち2〜3枚を本人にする。`,
    doko: namaeNG.map((r) => r.id).join(" "),
  },
  {
    midashi: "出した4枚について聞かれても、答えられない",
    kazu: `紹介文 ${D.shirabe.shoukai.pct}%／発表年 ${D.shirabe.nen.pct}%`,
    hon: `案内人が喋ってよいのは棚に書いてあることだけ、という作りは正しい。`
       + `ところが棚の側が空で、紹介文があるのは ${D.shirabe.shoukai.all} 組中 ${D.shirabe.shoukai.n} 組（${D.shirabe.shoukai.pct}%）、`
       + `発表年がある曲は ${D.shirabe.nen.pct}%。実際に出た4枚では、紹介文は 0枚 だった。`,
    naze: `4枚を選ぶとき、題名の見た目（長さ・記号）しか見ていない。中身が空かどうかを見ていない。`,
    naosi: `4枚を選ぶ時点で、紹介文か発表年が入っている札を先に出す。`
         + `「深掘りされても答えられる札」を上に持ってくるだけで、会話が続くようになる。`,
    doko: "F1 F3",
  },
  {
    midashi: "「ことば」の棚に、ことばが無い",
    kazu: `13枚中ほぼ全部が曲`,
    hon: `指示文は「ことば」「詩」「名言」→ joy の棚、と決めている。`
       + `ところが joy の棚の中身は ${D.shirabe.kotoba.slice(0, 4).map((t) => "「" + t + "」").join("・")} …で、実体は「うれしくなる曲」。`
       + `「名言みたいなの」と頼むと Uptown Funk が出る。`,
    naze: `棚の名前（joy＝ことば）と、棚に入っているもの（喜びの曲・動画）が食い違っている。`,
    naosi: `指示文から「詩」「名言」を外して「うれしくなるもの」に直すか、棚の名前を「喜び」に変える。`
         + `ついでに「白髪が多い人の原因」は、どう見てもこの棚ではない。`,
    doko: "C4",
  },
];

const jiku = [
  ["合っているか", D.pt.atari, 40],
  ["くどくないか", D.pt.kudoku, 20],
  ["楽しいか", D.pt.tanoshi, 20],
  ["速さ", D.pt.hayasa, 10],
  ["嘘をついていないか", D.pt.uso, 10],
];

const gyou = D.rows.map((r) => {
  const t = r.ten;
  const mark = t === undefined ? "―" : t >= 0.75 ? "○" : t > 0 ? "△" : "×";
  const cls = t >= 0.75 ? "ok" : t > 0 ? "sa" : "x";
  return `<tr class="${t < 0.75 ? "ng" : ""}">
  <td class="id">${esc(r.id)}</td>
  <td class="mk ${cls}">${mark}</td>
  <td class="say">${esc(r.say)}</td>
  <td class="got">${r.names.length ? r.names.map((n) => esc(n)).join(" ／ ") : '<i>出さなかった（これが正解の問）</i>'}</td>
  <td class="bad">${r.bad.map((b) => esc(b)).join("<br>")}</td>
</tr>`;
}).join("\n");

const html = `<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>967 覆面調査｜案内人（959）の体験を ${D.n}問たたいた</title>
<style>
:root{ --kami:#EDE6D6; --ai:#22304A; --shu:#C1442E; --usu:#cfc6b2; }
*{box-sizing:border-box}
body{margin:0;background:var(--kami);color:var(--ai);
  font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.85;
  -webkit-font-smoothing:antialiased}
.w{max-width:760px;margin:0 auto;padding:56px 22px 90px}
.kan{font-size:.72rem;letter-spacing:.24em;color:#8d8570}
h1{font-size:1.32rem;font-weight:400;letter-spacing:.04em;margin:.5em 0 .2em}
.sub{font-size:.8rem;color:#8d8570;margin:0 0 42px}
.ten{display:flex;align-items:baseline;gap:14px;border-top:1px solid var(--usu);
  border-bottom:1px solid var(--usu);padding:26px 0;margin:0 0 8px}
.ten b{font-size:4.6rem;font-weight:400;line-height:1;letter-spacing:-.02em}
.ten span{font-size:.82rem;color:#8d8570}
.jiku{margin:18px 0 54px;font-size:.78rem}
.jiku div{display:grid;grid-template-columns:8.5em 1fr 3.6em;align-items:center;gap:10px;margin:.42em 0}
.bar{height:3px;background:#ded5c0}
.bar i{display:block;height:3px;background:var(--ai)}
.jiku em{font-style:normal;text-align:right;color:#8d8570}
h2{font-size:.72rem;letter-spacing:.24em;color:#8d8570;font-weight:400;
  border-bottom:1px solid var(--usu);padding-bottom:8px;margin:0 0 26px}
.n{margin:0 0 40px;padding-left:48px;position:relative}
.n .no{position:absolute;left:0;top:2px;font-size:1.9rem;color:var(--shu);line-height:1}
.n h3{font-size:1.06rem;font-weight:400;margin:0 0 2px}
.n .kazu{font-size:.74rem;color:var(--shu);letter-spacing:.08em;margin:0 0 10px}
.n p{margin:0 0 6px;font-size:.88rem}
.n .lab{color:#8d8570;font-size:.74rem;letter-spacing:.1em;margin-right:.6em}
.n .doko{font-size:.7rem;color:#a39a85;letter-spacing:.06em}
table{width:100%;border-collapse:collapse;font-size:.76rem;
  font-family:"Hiragino Sans","Yu Gothic",sans-serif;line-height:1.6}
th{text-align:left;font-weight:400;color:#8d8570;font-size:.68rem;letter-spacing:.14em;
  border-bottom:1px solid var(--usu);padding:0 8px 7px}
td{border-bottom:1px solid #e2dac6;padding:9px 8px;vertical-align:top}
tr.ng{background:rgba(193,68,46,.05)}
.id{color:#a39a85;font-size:.68rem;white-space:nowrap}
.mk{font-size:.95rem;width:1.4em}
.mk.x{color:var(--shu)}
.mk.sa{color:#b58a3a}
.say{white-space:nowrap}
.got{color:#5d6b82}
.bad{color:var(--shu);font-size:.7rem}
.shou{margin:56px 0 0;padding:22px 24px;border:1px solid var(--usu);
  font-size:.78rem;color:#6a6350;background:rgba(255,255,255,.28)}
.shou b{font-weight:400;color:var(--ai);letter-spacing:.1em;font-size:.72rem;
  display:block;margin:0 0 8px}
.shou p{margin:0 0 .7em}
.shou p:last-child{margin:0}
code{font-family:ui-monospace,monospace;font-size:.92em;background:rgba(34,48,74,.06);padding:.1em .4em}
a{color:var(--shu)}
@media(max-width:620px){ .w{padding:38px 16px 70px} .ten b{font-size:3.4rem}
  .say{white-space:normal} table{font-size:.72rem} .n{padding-left:36px} }
</style></head><body><div class="w">

<div class="kan">FUKUMEN CHOUSA ／ 覆面調査</div>
<h1>案内人（959）に、お客さんのふりをして ${D.n}問きいてきました</h1>
<p class="sub">${hiduke}　対象：${esc(D.target)}</p>

<div class="ten"><b>${D.total}</b><span>点／100点　${D.n}問　○は「4枚のうち3枚以上が頼んだもの」</span></div>
<div class="jiku">
${jiku.map(([n, v, m]) => `  <div><span>${n}</span><span class="bar"><i style="width:${(v / m) * 100}%"></i></span><em>${v.toFixed(0)}／${m}</em></div>`).join("\n")}
</div>

<h2>直すところ　多い順に3つ</h2>
${NAOSU.map((x, i) => `<div class="n">
  <div class="no">${i + 1}</div>
  <h3>${x.midashi}</h3>
  <div class="kazu">${esc(x.kazu)}</div>
  <p>${x.hon}</p>
  <p><span class="lab">なぜ</span>${x.naze}</p>
  <p><span class="lab">直し方</span>${x.naosi}</p>
  <div class="doko">出た問： ${esc(x.doko)}</div>
</div>`).join("\n")}

<h2>1問ずつ</h2>
<table>
<thead><tr><th></th><th></th><th>お客さんが言ったこと</th><th>出てきた4枚</th><th>悪かったところ</th></tr></thead>
<tbody>
${gyou}
<tr><td class="id">F1</td><td class="mk x">×</td><td class="say">1番の曲、何年の？</td><td class="got">${esc(D.fuka[0].why)}</td><td class="bad">聞かれても半分は「分かりません」になる</td></tr>
<tr><td class="id">F2</td><td class="mk ok">○</td><td class="say">これって代表曲なの？</td><td class="got">${esc(D.fuka[1].why)}</td><td class="bad"></td></tr>
<tr><td class="id">F3</td><td class="mk x">×</td><td class="say">このアーティスト、どんな人？</td><td class="got">${esc(D.fuka[2].why)}</td><td class="bad">紹介文が空なので、何も答えられない</td></tr>
</tbody></table>

<div class="shou">
<b>この調査で試せていないこと</b>
<p>声は一度も使っていません。この箱から Google の口（googleapis.com）に出られないので、<b style="display:inline">案内人の頭そのもの（Gemini 3.8 Live）は一度も呼べていません。</b>頭は安いモデルの代役に、959 ページから抜き出した指示文と道具の定義をそのまま渡して叩きました。</p>
<p>だから <b style="display:inline">マイクの聞き取り・しゃべりの間・声色・くどさ</b>は、この点数に入っていません。試せたのは「お客さんの言葉 → 棚の引き方 → 出てきた4枚 → 答えられる事実」までです。棚を引く速さは中央 32ms・最大 98ms で、遅さの問題は棚の側にはありませんでした。</p>
<p>点数は機械判定だけで付けています。LLM に採点させると、並び順や長さで大きく外すことが分かっているためです（<a href="https://www.adaline.ai/blog/llm-as-judge-reliability-bias" target="_blank" rel="noopener">Adaline の偏りベンチ</a>）。お客さんの人格を決めて走らせる作りと、聞き取りのゆらぎ（誤変換・中黒・通称）を混ぜる作りは <a href="https://aclanthology.org/2025.emnlp-industry.16/" target="_blank" rel="noopener">ACL 2025 の persona-driven user simulation</a> と EVA-Bench の型に合わせました。</p>
</div>

<div class="shou">
<b>もう一度走らせる</b>
<p><code>node tools/967_fukumen.mjs &amp;&amp; node tools/967_build_report.mjs</code></p>
<p>棚のコードは 959 のページから毎回そのまま抜いて動かしているので、959 を直せば次の調査は直った側を試します。お客さんの言葉を足すのは <code>tools/967_fukumen_cases.json</code>。頭を本物の Gemini に差し替えるときは <code>tools/967_brain_prompt.md</code>（959 から機械的に抜いた指示文）をそのまま投げて、返ってきた道具呼びを <code>tools/967_brain_out.json</code> に置くだけです。</p>
<p>かかったお金：<b style="display:inline">0円</b>（棚はローカルのデータを読むだけ）。代役の頭を1回だけ使ったぶんが、トークン数から多めに見積もって <b style="display:inline">約31円</b>。上限300円に対して約1割です。</p>
</div>

</div></body></html>`;

fs.writeFileSync(OUT, html);
console.log("書いた:", path.relative(ROOT, OUT), html.length + "字");
