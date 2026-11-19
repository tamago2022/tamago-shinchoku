#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1031番：SNS担当の机（今日出す1本＋口の実測）を1ページにする。

画像は外部ファイルにせず data: で本文に埋める。理由は2つ。
 ① 出す口（gaibu_kuchi の putfile）は **テキスト1ファイルしか通らない**（payload["text"]）。
    JPGは通せない。＝画像を別ファイルで公開する手が、そもそも無い。
 ② 1ファイルで完結していれば、たまごさんがスマホで開いたとき画像が欠けない。
上限は putfile 側の 1MB。ここで必ず実測して、超えたら品質を落として作り直す。
"""
import base64, io, json, os, sys
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Q = os.path.join(REPO, "wae_autopost", "queue.json")
OUT = os.path.join(REPO, "share", "check", "1031-sns-ippon.html")


def resolve(path):
    """queue.json の絵のパスはMacの絶対パス。サンドボックスからはマウント位置が
    違うので、見つからなければリポジトリからの相対で引き直す。"""
    if os.path.exists(path):
        return path
    i = path.find("wae_autopost/")
    if i >= 0:
        alt = os.path.join(REPO, path[i:])
        if os.path.exists(alt):
            return alt
    return path


def b64jpg(path, side, quality):
    im = Image.open(resolve(path))
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


q = json.load(io.open(Q, encoding="utf-8"))
items = q["items"]
first = items[0]
rest = items[1:]

hero = b64jpg(first["image"], 760, 70)
thumbs = {it["id"]: b64jpg(it["image"], 300, 58) for it in rest}

CSS = """
:root{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--aka:#c4483a;--ao:#3a5f7a;--midori:#3a7a52;--ki:#8a6a1f;--mi:#b0a894;}
*{box-sizing:border-box;}
body{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 14px calc(env(safe-area-inset-bottom) + 40px);background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;font-size:16px;line-height:1.7;max-width:860px;margin-left:auto;margin-right:auto;overflow-x:hidden;}
a{color:var(--ao);}
h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.3rem;letter-spacing:.04em;margin:0 0 6px;line-height:1.5;}
h2{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.05rem;letter-spacing:.04em;margin:38px 0 12px;color:var(--sub);border-bottom:1px solid var(--line);padding-bottom:6px;}
h3{font-size:.95rem;margin:20px 0 6px;color:var(--ao);}
.date{color:var(--sub);font-size:.8rem;margin-bottom:16px;word-break:break-word;}
.fix{background:#fff;border-left:4px solid var(--midori);border-radius:0 10px 10px 0;padding:14px 16px;margin:0 0 20px;font-size:1.02rem;}
.fix p{margin:0 0 10px;} .fix p:last-child{margin:0;}
.note{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 15px;font-size:.9rem;margin:0 0 14px;}
.warn{background:#fff;border-left:4px solid var(--aka);border-radius:0 10px 10px 0;padding:12px 15px;font-size:.9rem;margin:0 0 14px;}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 14px;border-radius:10px;border:1px solid var(--line);background:#fff;max-width:100%;}
table{border-collapse:separate;border-spacing:0;font-size:.84rem;min-width:560px;}
th,td{padding:8px 8px;border-bottom:1px solid var(--line);text-align:center;vertical-align:middle;white-space:nowrap;}
th{background:#efe9db;color:var(--sub);font-weight:600;font-size:.7rem;line-height:1.25;}
th.t,td.t{text-align:left;position:sticky;left:0;z-index:2;background:#fff;border-right:1px solid var(--line);font-size:.8rem;padding-left:10px;min-width:96px;font-weight:600;}
th.t{background:#efe9db;z-index:3;}
tr:last-child td{border-bottom:none;}
.yes{color:var(--midori);font-weight:700;} .no{color:var(--aka);font-weight:700;} .may{color:var(--ki);font-weight:700;}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:0 0 14px;margin:0 0 18px;overflow:hidden;}
.card img{display:block;width:100%;height:auto;}
.card .in{padding:12px 15px 0;}
.cap{white-space:pre-wrap;font-size:.88rem;line-height:1.65;background:#faf7f0;border:1px solid var(--line);border-radius:8px;padding:11px 13px;margin:8px 0 0;}
.btn{display:inline-block;margin:10px 0 0;background:var(--ao);color:#fff;border:0;border-radius:8px;padding:9px 16px;font-size:.88rem;font-weight:700;cursor:pointer;font-family:inherit;}
.btn.g{background:var(--midori);}
.meta{font-size:.78rem;color:var(--sub);margin:6px 0 0;word-break:break-all;}
details{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:0 0 9px;}
details summary{cursor:pointer;font-size:.9rem;font-weight:700;}
.row{display:flex;gap:12px;align-items:flex-start;margin-top:10px;}
.row img{width:118px;height:118px;object-fit:cover;border-radius:8px;flex:0 0 auto;}
ol.steps{margin:0 0 14px;padding-left:1.3em;}
ol.steps li{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 13px;margin:0 0 8px;font-size:.9rem;}
ol.steps li b{display:block;margin-bottom:3px;}
ul.plain{list-style:none;margin:0 0 14px;padding:0;}
ul.plain li{background:#fff;border:1px solid var(--line);border-radius:10px;padding:11px 14px;margin:0 0 9px;font-size:.9rem;}
ul.plain li b{display:block;margin-bottom:3px;}
code{background:#efe9db;padding:1px 5px;border-radius:4px;font-size:.82em;word-break:break-all;}
footer{color:var(--sub);font-size:.78rem;margin-top:44px;line-height:1.6;border-top:1px solid var(--line);padding-top:14px;}
@media (max-width:420px){body{font-size:15px;padding-left:11px;padding-right:11px;}h1{font-size:1.12rem;}.row img{width:92px;height:92px;}}
"""

rest_html = []
for it in rest:
    rest_html.append(
        '<details><summary>%s ／ %s</summary>'
        '<div class="row"><img src="%s" alt="%s の絵">'
        '<div class="cap" style="margin:0;flex:1;">%s</div></div>'
        '<button class="btn" data-cap="%s">この文面をコピー</button>'
        '<div class="meta">絵のファイル：<code>%s</code></div></details>'
        % (esc(it["id"]), esc(os.path.basename(it["image"]).replace(".jpg", "")),
           thumbs[it["id"]], esc(it["id"]), esc(it["caption"]),
           esc(it["id"]), esc(os.path.basename(it["image"])))
    )

HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>#1031 SNS ― 口は1本も開いていなかった／今日出す1本 確認ページ</title>
<style>%(css)s</style>
</head>
<body>
<!-- SHINCHOKU_BACK_LINK -->
<div id="shinchokuBackTop" style="position:sticky;top:0;left:0;right:0;z-index:9999;background:#1c1c1c;border-bottom:1px solid #3a3a3a;padding:8px 14px;text-align:left;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="https://tamago2022.github.io/tamago-shinchoku/" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.9rem;">← 進捗表に戻る</a>
</div>

<div class="date"><a href="../">共有資料の一覧</a> ／ 確認ページ #1031 ／ 元：<a href="./1030-tekizai-matrix.html">#1030 SNSが9列すべて─だった表</a></div>
<h1>SNSは「担当がいない」のではなく、口が1本も開いていなかった</h1>
<div class="date">2026-09-23 11:18 実測／叩いた結果だけを書いています。設定ファイルに書いてあることは根拠にしていません</div>

<div class="fix">
<p><b>1.</b> ★<b>叩いた結果、投稿できる口は0本でした。</b>
X＝<span class="no">鍵が無い</span>（Bearerがディスク上に1本も無い）。Instagram/Meta＝<span class="no">鍵が無い</span>。
Macの鍵ファイルに入っていたのは <code>OPENAI_API_KEY</code> と <code>XAI_API_KEY</code> の2本だけで、<b>SNSの名前が付いた鍵は1本もありません。</b>
YouTubeの鍵だけ<span class="yes">HTTP 200</span>で通りましたが、これは<b>読み取り専用の鍵で、投稿はできません。</b>
＝#1030で9列すべてが「─」だったのは、担当を決めていなかったからではなく、<b>出す穴が物理的に無かった</b>からです。</p>
<p><b>2.</b> ★<b>足りないのは鍵1本だけで、あとは全部揃っています。</b>
絵は11枚とも実在（全部ひらいて中身も見ました）。英日のキャプション11本、ハッシュタグ5個ずつ、
共同投稿の相手（<code>@wae0815</code>）も11本すべてに設定済み。<b>鍵を1本貼った瞬間に11本が動き出します。</b></p>
<p><b>3.</b> ★<b>今日出す1本を決めました。<code>wae-01</code>（黒地に藤色の龍・桜の下）です。</b>
このアカウントの1本目なので、「本人運営ではないファンのアカウントです」と名乗っている文面のものを選びました。
<b>絵も文面も、下に全部そのまま出してあります。</b>出す道は2本あります（第4節）。<b>勝手には出していません。</b></p>
</div>

<h2>1. 叩いた結果（2026-09-23 11:17:49・Mac上で実行）</h2>
<div class="wrap"><table>
<tr><th class="t">口</th><th>鍵はあるか</th><th>叩いた結果</th><th>投稿できるか</th></tr>
<tr><td class="t">Instagram / Meta</td><td class="no">無い</td><td><code>no_credential</code></td><td class="no">✕</td></tr>
<tr><td class="t">X（旧Twitter）</td><td class="no">無い</td><td><code>no_credential</code></td><td class="no">✕</td></tr>
<tr><td class="t">YouTube</td><td class="yes">ある</td><td class="yes">HTTP 200</td><td class="no">✕ 読み取り専用</td></tr>
<tr><td class="t">note / LINE</td><td class="no">無い</td><td>名前ごと存在しない</td><td class="no">✕</td></tr>
<tr><td class="t">自分のサイト</td><td class="yes">ある</td><td class="yes">HTTP 200</td><td class="yes">◯ 0円で出せる</td></tr>
</table></div>
<div class="note">
<div>★<b>「設定に書いてある」は根拠にしていません。</b>実際に <code>api.x.com/2/users/me</code> と <code>graph.facebook.com/v21.0/me</code> を叩いて、
返ってきたものだけを書いています。鍵が無い口は、叩く前に <code>no_credential</code> で落ちます。<b>これを黙って飲み込むと「動いているように見える」ので、そのまま出しました。</b></div>
<div style="margin-top:8px;border-top:1px dotted var(--line);padding-top:8px;">
★<b>止めるスイッチが2つとも入ったままです。</b><code>wae_autopost/.stop</code> と <code>.sns-autopost-stop</code> の両方があり、
<code>launchd</code> にもSNSの常駐は<b>1件も登録されていません</b>。鍵を入れても、この2つを外さないと自動では出ません（第5節でまとめて外します）。</div>
</div>

<h2>2. ★今日出す1本（wae-01）</h2>
<div class="card">
<img src="%(hero)s" alt="黒い画布に藤色と白の龍。桜の下、イーゼルに立てかけて撮られている">
<div class="in">
<div class="meta">絵のファイル：<code>%(heroname)s</code>　／　共同投稿：<b>@wae0815</b>　／　ハッシュタグ5個</div>
<div class="cap">%(herocap)s</div>
<button class="btn g" data-cap="wae-01">この文面を丸ごとコピー</button>
</div>
</div>
<div class="note">★<b>絵のファイル名に「要確認（色は赤でなくピンク紫）」と付いていた件は、ひらいて見て決着しました。</b>
藤色〜ピンクです。赤ではありません。文面の <code>lilac</code>（藤色）で合っているので、<b>文面は直していません。</b></div>

<h2>3. 残りの10本（全部そのまま出します）</h2>
<p class="date">押すとひらきます。10本とも、絵と文面をそのまま入れてあります。</p>
%(rest)s

<h2>4. ★出す道は2本あります</h2>

<h3>A｜スマホのInstagramアプリから、手で出す（鍵は要りません・2分）</h3>
<ol class="steps">
<li><b>1. 絵をスマホに移す</b>Macの <code>wae_autopost/images/%(heroname)s</code> をAirDropでスマホへ。</li>
<li><b>2. 上の「この文面を丸ごとコピー」を押す</b>英語と日本語とハッシュタグが、まとめて1回でコピーされます。</li>
<li><b>3. Instagramアプリで投稿する</b>絵を選んで、キャプションに貼り付け。</li>
<li><b>4. 共同投稿に@wae0815を招待する</b>Instagramの公式ヘルプに<b>共同投稿のページがあります</b>：
<a href="https://help.instagram.com/5861247717337470">help.instagram.com/5861247717337470</a>。
★<b>画面の手順そのものは、こちらからは開けませんでした（中身がJavaScriptで出るページで、文字が取れません）。だから手順は書いていません。</b>
招待を出すと、わえさんのスマホに「承認しますか」が届きます。</li>
</ol>
<div class="note">★<b>この道が今日いちばん速いです。</b>鍵を作る画面を1枚も開かずに、<b>今日じゅうに1本が本当に外に出ます。</b>
出たら、そのURLをこちらに貼ってください。<b>「出た」をURLで確かめるところまでが完了です。</b></div>

<h3>B｜鍵を1本貼って、以後ずっと自動にする（押すだけの並び）</h3>
<ol class="steps">
<li><b>1. Meta開発者登録</b><a href="https://developers.facebook.com/">developers.facebook.com</a> → 右上「スタート」。
今使っているFacebookでそのまま。<b>新しいアカウントは作りません。</b></li>
<li><b>2. アプリを作る</b><a href="https://developers.facebook.com/apps/create/">developers.facebook.com/apps/create</a> →
ユースケース「Instagramアカウントの管理」／アプリ名 <code>wae-autopost</code>／ビジネスポートフォリオ <b>TeamTadanowae</b>。</li>
<li><b>3. トークンをもらう</b><a href="https://developers.facebook.com/tools/explorer/">developers.facebook.com/tools/explorer</a> →
アプリで <code>wae-autopost</code> を選ぶ →「ページアクセストークン → TeamTadanowae」→
権限4つ（<code>instagram_basic</code> / <code>instagram_content_publish</code> / <code>pages_read_engagement</code> / <code>pages_manage_posts</code>）→「アクセストークンを生成」。</li>
<li><b>4. 無期限にする</b><a href="https://developers.facebook.com/tools/debug/accesstoken/">developers.facebook.com/tools/debug/accesstoken</a> に貼って「アクセストークンを延長」。</li>
<li><b>5. 貼る</b>Macの <code>wae_autopost/1_鍵を貼る.command</code> をダブルクリックして、貼ってEnter。<b>打ち込むものは他にありません。</b></li>
<li><b>6. ★OKを出す</b><code>wae_autopost/0_この11本にOKを出す.command</code> をダブルクリック。
11本が全部出るので、見てから y を1回。<b>これを押すまでは、鍵があっても1本も出ません</b>（第5節）。</li>
</ol>
<div class="warn">★<b>1〜5はこちらでは代行できません。</b>パスワードを打つ画面が必ず入るためです（憲法第5条）。
<b>画面を開くところまでは全部リンクにしてあります。押すだけです。</b>
費用は<b>0円</b>です（コンテンツ公開APIは無料・24時間100投稿まで）。</div>

<h2>5. ★関所を作りました（今日の工事・実際に効くところまで確かめました）</h2>
<div class="note">
<div>いちばん怖いのは「鍵が入った日から、見せずに勝手に出はじめる」ことです。そうならない作りに変えました。</div>
<div style="margin-top:8px;">★<b>OKが出ていない文面は、鍵があっても、時間が来ても、外に出ません。</b>
<code>post.py</code> の投稿の一本道の上に関所を置いたので、<b>思い出したときだけ守る約束ではなく、通らないと出られません。</b></div>
<div style="margin-top:8px;">★<b>関所を開けるのは、たまごさんが <code>0_この11本にOKを出す.command</code> をダブルクリックしたときだけです。</b>
押すと11本の文面と絵が全部出て、最後に1回だけ「出していいですか」と聞きます。
<b>y を押した11本だけが <code>status/sns_gate/approved.json</code> に入り、以後その11本だけが9:00と19:00に1本ずつ出ます。</b>
OKを取り消したいときは、そのファイルを消すだけです。</div>
<div style="margin-top:8px;border-top:1px dotted var(--line);padding-top:8px;">
★<b>本当に止まるか、今日その場で走らせて確かめました。</b>
OKが無い状態で投稿を走らせる → <b>「関所で止めました」で終了（終了コード5）。1バイトも外に出ません。</b>
OKを入れてから同じものを走らせる → 関所は通って、<b>その次の「鍵がない」で止まりました。</b>＝関所は素通りしていません。</div>
</div>
<ul class="plain">
<li><b>朝9時と夜19時の2回だけ出す</b><code>wae_autopost/queue.json</code> の <code>slots_jst</code> は <code>["09:00","19:00"]</code>。たまごさんの型のままです。
常駐の仕掛け（<code>launchd</code>）は <code>3_毎日9時と19時に出す_ON.command</code> を押した時点で入ります。</li>
<li><b>リンクは自分のサイトへ</b>11本とも「link in profile（プロフィールのリンクから）」で、YouTubeへの直リンクは1本もありません。
★<b>ただし、プロフィールに入っているリンクの中身は、こちらからは見えません。</b>自分のサイトになっているか、1回だけ見てください。</li>
<li><b>出たら記録する</b><code>status/dispatch_outbox.jsonl</code> に1行残して、進捗表に出します。</li>
<li><b>相互フォロー営業・いいね回りはしません</b>1件も入れていません。</li>
</ul>

<h2>6. 共同投稿（Collabs）は決着しました</h2>
<div class="note">
<div>8月に「Meta Business Suiteの画面に見当たらない」で止まっていた件です。<b>画面ではなく、APIの側に公式にあります。</b>
Meta公式リファレンスに <code>collaborators</code> のぶら下がりがあり、<b>招待の状態（<code>invite_status</code>：Pending / Accepted）まで返ってきます。</b>
＝「招待を出して、相手が承認する」形だと、公式ドキュメントに書いてあります。</div>
<div style="margin-top:8px;">出典：<a href="https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-media/collaborators/">developers.facebook.com ／ IG Media Collaborators</a>（今日こちらで開いて、中身を読んで確認しました）</div>
<div style="margin-top:8px;border-top:1px dotted var(--line);padding-top:8px;">
★<b>実際に叩いたわけではありません。</b>鍵が無いので、認証で落ちる手前までしか行けていません。
鍵を貼ったら <code>wae_autopost/6_Collabsが通るか試す.command</code> をダブルクリックすると、<b>投稿せずに通るかだけを試せます</b>（作ったものは24時間で勝手に消えます）。</div>
</div>

<h2>7. ★直したもの・見つけた傷</h2>
<ul class="plain">
<li><b>① 「6_Collabsが通るか試す.command」が消えていました → 戻しました</b>
9/22の引き継ぎに「新設した」と書いてあるのに、実物は <code>.gomi_6_collabtest.bak</code> という名前に変えられていて、
<b>ダブルクリックできる場所にありませんでした。</b>中身は無事だったので、元の名前に戻して実行できるようにしました。</li>
<li><b>② wae-04の文面に、写真に写っていない桜が書いてありました → 落としました</b>
<code>09_紫系の龍の横顔</code> の写真には<b>桜が1本も写っていません</b>（草地と海と、葉のない木です）。
なのに文面は "held up near cherry blossoms and water" でした。<b>水辺だけ残して、桜を落としました。</b>
元のファイルは <code>queue_backup_2026-09-23.json</code> に取ってあります。</li>
<li><b>③ プロフィールのリンク先は未確認です</b>11本とも「link in profile」で終わっています。
<b>そのリンクが自分のサイトを向いているかは、こちらからは見えません。</b>空欄のまま上げます。</li>
</ul>

<h2>8. できなかったこと（隠しません）</h2>
<ul class="plain">
<li><b>投稿は0本のままです</b>鍵が無いので、こちらからは1本も出せませんでした。<b>出したふりはしていません。</b></li>
<li><b>Instagramのヘルプ画面の中身が取れません</b><code>help.instagram.com</code> は文字が出てこないページで、<b>共同投稿の画面の手順は読めていません。</b>URLだけ置きました。</li>
<li><b>工場そのものは今も止まっています</b>Claudeのログインが切れていて、本物の仕事が1本も出せない状態（<code>status/no_launch.flag</code>）。<b>これはたまごさんにしか外せません。</b></li>
</ul>

<footer>
#1031 ／ 2026-09-23 作成。<br>
このページに書いた「通った・通らない」は、すべてその場で叩いて返ってきたものです。<br>
叩けなかったものは「叩けていない」と書いてあります。
</footer>

<script>
var CAPS = %(caps)s;
document.addEventListener('click', function(e){
  var b = e.target.closest ? e.target.closest('button[data-cap]') : null;
  if(!b) return;
  var t = CAPS[b.getAttribute('data-cap')] || '';
  var done = function(){ var o=b.textContent; b.textContent='コピーしました'; setTimeout(function(){b.textContent=o;},1600); };
  if(navigator.clipboard && navigator.clipboard.writeText){ navigator.clipboard.writeText(t).then(done, function(){fallback(t,done);}); }
  else { fallback(t,done); }
});
function fallback(t,done){
  var a=document.createElement('textarea'); a.value=t; a.style.position='fixed'; a.style.opacity='0';
  document.body.appendChild(a); a.select();
  try{ document.execCommand('copy'); done(); }catch(err){}
  document.body.removeChild(a);
}
</script>
</body>
</html>
""" % {
    "css": CSS,
    "hero": hero,
    "heroname": esc(os.path.basename(first["image"])),
    "herocap": esc(first["caption"]),
    "rest": "\n".join(rest_html),
    "caps": json.dumps({it["id"]: it["caption"] for it in items}, ensure_ascii=False),
}

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with io.open(OUT, "w", encoding="utf-8") as f:
    f.write(HTML)

n = len(HTML.encode("utf-8"))
print("書いた: %s" % OUT)
print("バイト数: %d （putfileの上限 1,048,576）%s" % (n, "  ★超えている" if n > 1048576 else "  OK"))
