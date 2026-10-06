#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

WHAT_HTML = """
<p><b>結論（Dispatchの推奨）</b>：<b>B案（フォーム入力・画像アップロードまでは自動化し、最後の「審査リクエスト」ボタンだけたまごさん本人が押す）</b>を採用する。
理由は下の比較表のとおり。規約に自動化そのものを名指しで禁止する条文は無いが、「BOTで不正操作」という広い条文があり解釈のリスクは残るため、
最後の1クリックだけ人の意思を残してリスクを最小化する。</p>

<h2 style="margin-top:28px;">① 規約の原文（LINE Creators Market利用規約）</h2>
<p>出典：<a href="https://creator.line.me/ja/terms/" target="_blank">https://creator.line.me/ja/terms/</a>（2026-09-12取得。フッターの「利用規約」リンクから到達、クリエイター向け本規約と確認済み）</p>
<div class="note">
<b>12. 禁止事項（抜粋）</b><br>
12.11.「本サービスのサーバやネットワークシステムに支障を与える行為、<b>BOT、チートツール、その他の技術的手段を利用して本サービスを不正に操作する行為</b>、本サービスの不具合を意図的に利用する行為、同様の質問を必要以上に繰り返す等、当社に対し不当な問い合わせまたは要求をする行為、その他当社による本サービスの運営または他のクリエイターによる本サービスの利用を妨害し、これらに支障を与える行為。」<br><br>
12.13.「不当な目的または態様でのリバースエンジニアリング、逆アセンブルを行う行為、その他の方法でソースコードを解読する行為」
</div>
<p><b>読み方（推測ではなく条文どおり）</b>：この条項は「BOT等を使うこと」自体ではなく「BOT等を使って<u>不正に操作する行為</u>」を禁止している。文脈（同じ条項内にランキング操作・過剰な問い合わせ・サーバー負荷への言及）から見て、主にランキング水増しや嫌がらせ的な大量アクセスを想定した条文と読める。
<b>ただし「申請フォームの自動入力」がここに含まれるかどうかは規約に明記が無く、断定できない＝「不明」とする。</b>
規約全文（禁止事項12.1〜12.14、審査基準、ガイドライン各種）を読んだが、「ブラウザ自動化を明示的に禁止する」条文・「スクリプトによる申請を認める／認めない」を名指しした条文は<b>見つからなかった</b>。</p>

<h2 style="margin-top:28px;">② 実際にやっている人（3件・出典つき）</h2>
<ul class="links" style="list-style:none;padding:0;">
<li><b>1. GitHub「line-sticker-skills」（作者:rnmkg-cmyk）</b><br>
写真からスタンプ画像を生成する<code>line-sticker-generate</code>と、<b>「Codex in Chromeでフォーム入力・ZIP一括アップロード・審査リクエストまで進める」line-sticker-submit</b>という2つの手順書（AIエージェント向けスキル）を公開。
実装は「ログインだけ人間、以降の入力・アップロード・審査リクエストのクリックまで全部自動」という<b>B〜A寄りの自動化を実際に行っている一次資料</b>。
<br>出典：<a href="https://github.com/rnmkg-cmyk/line-sticker-skills" target="_blank">https://github.com/rnmkg-cmyk/line-sticker-skills</a>（README・SKILL.md本文で確認）</li>

<li><b>2. note「ChatGPT・Geminiで作ったLINEスタンプを、申請できる形に」（moreoweb）</b><br>
画像の切り出し・透過・規格変換・ZIP化までをブラウザ完結ツールで自動化。本人の言葉：「ダウンロードしたZIPを、LINE Creators Marketにアップロードすれば、画像の申請はほぼ完了」＝<b>申請フォームへのアップロード自体は人間が手動で行っている（C寄り）</b>実例。
<br>出典：<a href="https://note.com/moreoweb/n/ncce188229732" target="_blank">https://note.com/moreoweb/n/ncce188229732</a></li>

<li><b>3. note「生成AIでLINEスタンプ制作を自動化｜画像生成から申請までの全手順」（knorq_ai）</b><br>
画像生成〜検品までをCodex用スキルで自動化し、実際に16個・40個のスタンプを審査通過・販売開始まで済ませた記録。本人の言葉：「画像の確認と修正は、人が判断しながら進めます」＝<b>完全無人ではなく人の判断を残す半自動</b>の実例。
<br>出典：<a href="https://note.com/knorq_ai/n/na50afe19e1b2" target="_blank">https://note.com/knorq_ai/n/na50afe19e1b2</a></li>
</ul>
<p><b>アカウント停止の実例</b>：note検索・Bing検索で複数クエリを試したが、「自動化ツールを使ってLINEクリエイターアカウントが停止された」という実例・報告は<b>見つからなかった＝不明</b>（見つからなかった＝安全という意味ではない。単に確認できた事実がゼロ件ということ）。</p>

<h2 style="margin-top:28px;">③ 公式API・一括アップロードの口</h2>
<p>LINE Creators MarketのFAQ・審査ガイドラインを確認したが、<b>外部連携用の公式APIや一括アップロード機能への言及は見つからなかった</b>。申請は現状、Web画面からの手作業（またはそれをブラウザ自動操作で代行する非公式な方法）以外に道が無いと見られる。</p>

<h2 style="margin-top:28px;">④ 3案比較（たまごさんの手数を軸に）</h2>
<table>
<tr><th>案</th><th>たまごさんの手数</th><th>規約リスク</th><th>実現できるか</th><th>出典</th></tr>
<tr><td><b>A 完全自動</b><br>ログイン〜審査リクエストまで無人</td><td>0回</td><td class="no">不明（12.11条のBOT条項に抵触する解釈の余地あり。実例も見つからず＝誰もやっていない可能性）</td><td>技術的には実装例1と同系統で可能</td><td>規約12.11条</td></tr>
<tr><td><b>B 半自動（推奨）</b><br>入力・アップロードまで自動、最後の「審査リクエスト」だけたまごさんが押す</td><td class="yes">1回</td><td>不明だが最小（人間の最終クリックが残るため「本人の意思による申請」と説明できる。実例1のスキルを、審査リクエスト直前で止める運用に変更すれば実現）</td><td class="yes">実装例1（GitHub）が土台として実在</td><td>実例1・実例3</td></tr>
<tr><td><b>C 今の貼るだけシート</b></td><td>24回以上</td><td class="yes">なし（全部人間操作）</td><td class="yes">できている（769番実装済み）</td><td>実例2</td></tr>
</table>

<h2 style="margin-top:28px;">⑤ 代替の販路（簡潔に）</h2>
<p><b>Telegramステッカー</b>は公式Bot API（<code>addStickerToSet</code>等）が用意されており、規約内で完全自動投稿ができる（LINEのようなブラウザ自動化のグレーゾーンが無い）。ただし国内ユーザーのリーチはLINEに遠く及ばない。<b>Apple Messages（iMessage）用ステッカー</b>はApp Store Connectへの提出が必要で、別種の手間（Xcode署名等）が発生するため今回は優先度低。</p>

<h2 style="margin-top:28px;">この件で分かったこと（769番の指摘への対応）</h2>
<p>769番が「規約で自動化禁止」と判断した根拠は、規約原文の特定条文ではなく<b>一般的な理解（ブラウザ自動化は禁止という思い込み）</b>だったと見られる（実際の12.11条はBOTによる「不正操作」を禁止しているだけで、申請フォーム入力を名指しで禁止していない）。
「止めた理由をその場でDispatchへ出す」仕組み化は786番の完了条件には含まれないため今回は実装していないが、次にこの手の判断が起きた時のために申し送る。</p>
"""

cfg = {
    "n": 786,
    "slug": "line-stamp-automation-research",
    "title": "LINE申請の自動化はどこまで可能か（規約原文＋実例＋3案比較）",
    "what": WHAT_HTML,
    "nums": [
        {"value": "3件", "label": "出典つき実例"},
        {"value": "1", "label": "見つかった該当条項（12.11）"},
        {"value": "1回", "label": "推奨B案でのたまごさんの手数"},
    ],
    "links": [
        {"label": "規約原文（LINE Creators Market利用規約）", "url": "https://creator.line.me/ja/terms/"},
        {"label": "実例1: GitHub line-sticker-skills（審査リクエストまで自動化）", "url": "https://github.com/rnmkg-cmyk/line-sticker-skills"},
        {"label": "実例2: note「申請できる形に」（画像変換のみ自動）", "url": "https://note.com/moreoweb/n/ncce188229732"},
        {"label": "実例3: note「画像生成から申請までの全手順」（半自動）", "url": "https://note.com/knorq_ai/n/na50afe19e1b2"},
        {"label": "審査ガイドライン", "url": "https://creator.line.me/ja/review_guideline/"},
    ],
    "footer": "調査タスク（786番）。画面変更を伴わない調査のため前後スクショは無し。証拠は全て本文中のリンク先。",
    "allow_no_screenshot": "調査タスクのため画面変更なし。規約原文・実例はリンク先で本人確認できる",
}

with open("/tmp/786_cfg.json", "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=1)
print("wrote /tmp/786_cfg.json")
