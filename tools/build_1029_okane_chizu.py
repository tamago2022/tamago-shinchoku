#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""share/check/1029-okane-chizu.html を組む。画像はインライン。"""
import base64, pathlib

ROOT = pathlib.Path("/sessions/awesome-epic-cori/mnt/tamago-shinchoku")
b64 = pathlib.Path("/tmp/chizu.b64").read_text().strip()

HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>おかねの流れ・一枚地図</title>
<style>
  :root{
    --paper:#ede6d6; --ink:#22304a; --shu:#c1442e;
    --line:#c9bfa8; --mute:#6b6a63;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0}
  body{
    background:var(--paper); color:var(--ink);
    font-family:"Hiragino Mincho ProN","Yu Mincho","Noto Serif JP",serif;
    line-height:1.85; font-size:16px; -webkit-text-size-adjust:100%;
  }
  .wrap{max-width:860px;margin:0 auto;padding:34px 20px 90px}

  /* 扉 */
  header{margin-bottom:34px}
  .kicker{font-size:11.5px;letter-spacing:.34em;color:var(--mute);margin:0 0 14px}
  h1{font-size:30px;line-height:1.5;margin:0 0 16px;font-weight:400;letter-spacing:.04em}
  .lead{font-size:14.5px;color:#4a5468;margin:0;max-width:44em}
  .rule{border:0;border-top:1px solid var(--line);margin:26px 0 0}

  /* 主役の画 */
  figure{margin:38px 0 0}
  figure img{
    width:100%;height:auto;display:block;
    box-shadow:0 2px 18px rgba(34,48,74,.16);
  }
  figcaption{font-size:12.5px;color:var(--mute);margin:12px 2px 0;line-height:1.75}

  /* 質問 */
  .q{
    margin:54px 0 0;padding:30px 26px;
    border:2px solid var(--shu);background:rgba(255,255,255,.34);
  }
  .q .lbl{font-size:11.5px;letter-spacing:.3em;color:var(--shu);margin:0 0 14px}
  .q p{margin:0;font-size:21px;line-height:1.72;letter-spacing:.02em}

  /* 章 */
  h2{
    font-size:13px;letter-spacing:.24em;font-weight:400;color:var(--mute);
    margin:64px 0 4px;padding:0 0 10px;border-bottom:1px solid var(--line);
  }
  h2 .no{color:var(--shu);margin-right:12px;font-style:italic}
  .note{font-size:13px;color:var(--mute);margin:14px 0 20px}

  table{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0 0}
  th,td{border-bottom:1px solid var(--line);padding:11px 8px;text-align:left;vertical-align:top}
  th{font-weight:600;font-size:12px;letter-spacing:.1em;color:var(--mute);white-space:nowrap}
  td.mk{width:2.2em;text-align:center;font-size:17px}
  .ok{color:#1d5c3f}
  .ng{color:var(--shu)}
  td.nm{white-space:nowrap;font-size:14.5px}
  td.rs{color:#4a5468;font-size:13.5px;line-height:1.7}

  .who{margin:6px 0 0}
  .who .row{padding:16px 0;border-bottom:1px solid var(--line)}
  .who .row:last-child{border-bottom:none}
  .who a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--shu);
         font-size:16.5px;letter-spacing:.02em}
  .who .d{font-size:13.5px;color:#4a5468;margin:7px 0 0;line-height:1.75}
  .who .u{font-size:11.5px;color:var(--mute);margin:5px 0 0;word-break:break-all}
  .dead{
    margin:24px 0 0;padding:16px 18px;border-left:3px solid var(--shu);
    background:rgba(255,255,255,.3);font-size:13.5px;line-height:1.8;color:#4a5468;
  }
  .dead b{color:var(--ink);font-weight:600}

  footer{margin-top:70px;padding-top:18px;border-top:1px solid var(--line);
         font-size:12px;color:var(--mute);line-height:1.9}
  footer a{color:var(--mute);word-break:break-all}

  @media (max-width:420px){
    body{font-size:15px}
    .wrap{padding:26px 15px 64px}
    h1{font-size:23px}
    .q{padding:22px 18px}
    .q p{font-size:17.5px}
    table{font-size:13px}
    th,td{padding:9px 5px}
    td.nm{white-space:normal;font-size:13.5px}
    td.rs{font-size:12.5px}
    .who a{font-size:15px}
  }
</style>
</head>
<body>
<div class="wrap">

<header>
  <p class="kicker">おかねの流れ　一枚地図　／　N o . 0 0 1</p>
  <h1>公開されている数字を、<br>ならべるだけの道具。</h1>
  <p class="lead">誰かを悪者にするためではありません。国が自分で公開している資料から、
  「いつ・どこへ・いくら」だけを取り出してならべ、最後に質問をひとつ置きます。
  ここに出ている数字は、すべて一次資料のままです。</p>
  <hr class="rule">
</header>

<figure>
  <img src="data:image/jpeg;base64,__B64__" alt="おかねの流れ 一枚地図 No.001">
  <figcaption>試作 #001／原子力防災体制等構築事業（内閣府・特別会計：エネルギー対策 電源開発促進勘定）。
  出典は行政事業レビュー（RSシステム・内閣官房）。千円→万円の単位換算以外、加工はしていません。</figcaption>
</figure>

<div class="q">
  <p class="lbl">こ の 紙 の 出 口</p>
  <p>予算をふやしたのに、使ったお金がへったのは、なぜですか。</p>
</div>

<h2><span class="no">01</span>機械で引ける口・引けない口</h2>
<p class="note">2026-09-23、実際に叩いて確かめたものだけ。</p>
<table>
  <tr><th></th><th>データ</th><th>理由</th></tr>
  <tr><td class="mk ok">◯</td><td class="nm">行政事業レビュー<br>（RSシステム）</td>
      <td class="rs">年度別ZIP＋CSVが認証なしで落ちる。国の約5,000事業の予算・執行額・支出先・法人番号・落札率まで入っている。</td></tr>
  <tr><td class="mk ok">◯</td><td class="nm">調達ポータル<br>落札実績</td>
      <td class="rs">全省庁の落札（案件名・相手方・金額）が年次全件＋日次差分のCSVで公開されている。</td></tr>
  <tr><td class="mk ok">◯</td><td class="nm">jGrants</td>
      <td class="rs">キー不要のJSON APIが、そのまま実データを返した。ただし取れるのは補助金の「公募」で、交付先ではない。</td></tr>
  <tr><td class="mk ok">◯</td><td class="nm">国会会議録</td>
      <td class="rs">キー不要のJSON API。国会の全発言が全文で引ける（「特別会計」で85,951件）。</td></tr>
  <tr><td class="mk ok">◯</td><td class="nm">e-Gov 法令</td>
      <td class="rs">キー不要のJSON API。法令本文と改正履歴を条文横断で引ける。</td></tr>
  <tr><td class="mk ng">✕</td><td class="nm">政治資金<br>収支報告書</td>
      <td class="rs">スキャンしただけのPDF。一覧のページは取れるが、中の金額は機械では読めない。日本で一番大きい壁。</td></tr>
  <tr><td class="mk ng">✕</td><td class="nm">官報</td>
      <td class="rs">当日の見出し一覧までは取れるが、中身は全部PDF。検索APIがない。</td></tr>
  <tr><td class="mk ng">✕</td><td class="nm">東京都議会<br>会議録</td>
      <td class="rs">検索結果がJavaScriptで描かれるため、通常の取得では中身が空で返ってくる。</td></tr>
</table>

<h2><span class="no">02</span>もうやっている人</h2>
<p class="note">オリジナルを考えない。生き残っている型を借りる。</p>
<div class="who">
  <div class="row">
    <a href="https://judgit.net/" target="_blank" rel="noopener">JUDGIT!（ジャジット）</a>
    <p class="d">国の約5,000事業の行政事業レビューシートを横断検索できる。無料。2026年のデータまで更新が続いている。</p>
    <p class="u">https://judgit.net/</p>
  </div>
  <div class="row">
    <a href="https://political-finance-database.com/" target="_blank" rel="noopener">政治資金収支報告書データベース</a>
    <p class="d">読めないPDFをOCRで表に変え、政治家別・団体別に検索できるようにしている。実質1〜2人体制で、無料のまま続いている。</p>
    <p class="u">https://political-finance-database.com/</p>
  </div>
  <div class="row">
    <a href="https://search.openpolitics.or.jp/home" target="_blank" rel="noopener">政治資金収支報告書検索システム（政治資金センター）</a>
    <p class="d">提出されたPDF原本そのものを検索できる。都道府県によってはネット公開がなく、その分は手作業で集めていると公式に書かれている。</p>
    <p class="u">https://search.openpolitics.or.jp/home</p>
  </div>
  <div class="row">
    <a href="https://spending.jp/" target="_blank" rel="noopener">税金はどこへ行った？（spending.jp）</a>
    <p class="d">避ける道のほうの見本。</p>
    <p class="u">https://spending.jp/</p>
  </div>
</div>
<p class="dead"><b>死んだ理由。</b>2012年ごろ、自治体ごとに有志がそれぞれサイトを立ち上げたあと活動が衰退し、
サーバーが止まって多くが開けなくなった——と、本人たちがサイトに書いている。
<b>サイトを増やすと死ぬ。1本を無人で回す。</b></p>

<footer>
  試作の出典：<a href="https://rssystem.go.jp/project/b0acbd95-9765-4fea-a102-12002cdb9245?activeKey=detailed-breakdown" target="_blank" rel="noopener">rssystem.go.jp（予算と執行額）</a>／<a href="https://rssystem.go.jp/project/b0acbd95-9765-4fea-a102-12002cdb9245?activeKey=payment" target="_blank" rel="noopener">同（支出先）</a><br>
  この紙は、国が公開している資料の数字をならべたものです。だれかが悪いことをした、とは書いていません。
</footer>

</div>
</body>
</html>
"""

out = ROOT / "share/check/1029-okane-chizu.html"
out.write_text(HTML.replace("__B64__", b64), encoding="utf-8")
print("written", out, out.stat().st_size)
