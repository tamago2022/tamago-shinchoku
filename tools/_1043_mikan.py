#!/usr/bin/env python3
# 1043番：未完の一覧を1枚にする
import json, re, datetime, html, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date(2026, 9, 24)

d = json.load(open(os.path.join(ROOT, 'status/queue.json')))
items = d['items']
done = [i for i in items if i.get('status') in ('done', 'merged')]
nd = [i for i in items if i.get('status') not in ('done', 'merged')]


def mindate(i):
    c = []
    for k in ('createdAt', 'startedAt', 'stuckAt', 'cutAt', 'demotedAt', 'heldAt',
              'costAskedAt', 'urakataBlockedAt', 'checkedAt', 'finishedAt'):
        v = i.get(k)
        if isinstance(v, str):
            m = re.match(r'(\d{4})-(\d{2})-(\d{2})', v)
            if m:
                c.append(datetime.date(*map(int, m.groups())))
    txt = (i.get('what') or '') + (i.get('why') or '') + (i.get('holdNote') or '')
    for m in re.finditer(r'(?<!\d)(0[1-9]|1[0-2])-([0-3]\d)(?!\d)', txt):
        try:
            dt = datetime.date(2026, int(m.group(1)), int(m.group(2)))
            if dt <= TODAY:
                c.append(dt)
        except ValueError:
            pass
    return min(c) if c else None


AI_PAT = re.compile(r'Jules|Devin|Codex|Genspark|Grok|Copilot|ChatGPT|Gemini|google-labs|bot\]', re.I)
MONEY_PAT = re.compile(r'残高切れ|残高が|insufficient_quota|上限0円|クレジット切れ|team_blocked|403|支払い|課金が必要', re.I)
KEY_PAT = re.compile(r'鍵|ログイン|パスワード|権限|OAuth|token|認証', re.I)


def classify(i):
    blob = json.dumps(i, ensure_ascii=False)
    if i.get('costsMoney') and not i.get('costApproved'):
        if MONEY_PAT.search(blob):
            return 'お金'
        return 'たまごさん'
    if i.get('costAskedAt') and not i.get('costApproved'):
        return 'たまごさん'
    if i.get('status') == 'awaiting_check':
        return 'たまごさん'
    if MONEY_PAT.search(blob):
        return 'お金'
    if AI_PAT.search(i.get('title') or ''):
        return '外のAI'
    if i.get('holdNote') and KEY_PAT.search(i['holdNote']):
        return 'たまごさん'
    return 'こちら'


def where(i):
    st = i.get('status')
    s = (i.get('stuckReasonSummary') or '').strip()
    h = (i.get('holdNote') or '').strip()
    fr = i.get('failReasons') or []
    if st == 'stuck':
        base = s or (str(fr[-1]) if fr else '落ちた理由の記録なし')
        return '落ちて止まっている：' + base
    if st == 'hold':
        return '保留：' + (h or '保留の理由が書かれていない')
    if st == 'awaiting_check':
        return '確認待ちの列に置いたまま：' + (h or 'たまごさんのOK待ち')
    if st == 'running':
        return 'いま走っている（結果は未確認）'
    return '発車待ちの列に積んだまま（走っていない）'


def nextstep(i):
    st = i.get('status')
    if st == 'stuck':
        return '落ちた理由を1つ直して、本番URLを叩いてから再発車'
    if st == 'hold':
        return '保留の理由が今も生きているか見て、生きていなければ列へ戻す'
    if st == 'awaiting_check':
        return 'たまごさんに1タップで可否が返せる形にして出す'
    if re.match(r'^GH\d+', i.get('title') or ''):
        return '返ってきた中身を読んで、棚か進捗表に取り込む'
    return '列の上へ上げて着火する'


rows = []
for i in nd:
    md = mindate(i)
    rows.append({
        'src': f"発車待ち #{i['n']}",
        'date': md.isoformat() if md else '不明',
        'days': (TODAY - md).days if md else None,
        'what': i['title'],
        'where': where(i),
        'who': classify(i),
        'next': nextstep(i),
        'origin': i.get('origin') or '不明',
    })

# ---- 発車待ちの列に載っていないもの（引き継ぎ・GitHub・実測から拾った）----
EX = [
 # date, what, where, who, next, src
 ('2026-09-07', 'ごきげん補給所の本番が古いまま（フッター軽量化などがmainに入っているのに公開されていない）',
  'Lovableの公開を押していない。1040番で鍵（~/.tamago/lovable_oauth.json・refreshあり）も企画IDも押す台本も揃っている',
  'こちら', 'tools/kohyou.py で公開を押して、本番URLを自分で叩いて200を確認する', '1040番 引き継ぎ'),
 ('2026-09-18', 'カードページ：動画が出ていない／案内所ブロックの誤配置',
  'mainには入ったが本番の画面で確かめていない。Lovableの公開が止まっている',
  'こちら', '公開を押したあと、①黒い箱が無い②案内所ブロックが無い③見出しとおすすめは残っている、の3点を本番で見る', '1023番 引き継ぎ'),
 ('2026-09-23', '棚編集（/admin/shelves）が28秒待っても中身が出てこない',
  '画面は開くが中身が「読み込み中…」のまま来ない。鍵を使う測定はしていない',
  'こちら', '棚編集の中に入る道を作って、開くまでの秒数を実測する', '1028番 実測'),
 ('2026-09-23', '曲ページが6回中6回止まる',
  '前便の実測。原因は videoHealthReport.generated.ts 489KB あたりの可能性が高い（未検証）',
  'こちら', 'youtubeIdMap と videoHealthReport の読み込みを外して、6回測り直す', '1032番 引き継ぎ'),
 ('2026-09-23', 'URL貼りは「落ちなかった」ではなく「測れていない」',
  '棚編集の中身が出てこないので、URLを貼る欄までたどり着けず回数が0のまま',
  'こちら', '上の棚編集の道が通ったら、同じ手順で10回貼って回数を出す', '1028番 実測'),
 ('2026-09-23', '375px（スマホ幅）での見え方が未取得',
  '200は確認済み。375pxは一度も撮っていない',
  'こちら', 'headless Chrome を375px幅で開いて主要ページのスクショを撮る', '1030番 絵の門 引き継ぎ'),
 ('2026-09-23', '案内人のトンチンカン（泣ける曲→猫の爪切り／シティポップ→氷点下71℃の村／King Gnu→無反応）',
  '採点の物差し（トンチンカン率）は作ったが、直す工事に入っていない',
  'こちら', '300問を流してトンチンカン率を1回出し、ワースト3の棚の結びつきを直す', '案内人採点基準'),
 ('2026-09-23', 'SNS投稿が0本（鍵が1本も無い）',
  '投稿の配管はあるが、Xにも Instagram にも投稿できる鍵が1本も入っていない',
  'たまごさん', 'たまごさんがX／Instagramの鍵を1本置く。置き場は ~/.tamago/keys/api_keys.env', '1029番 開通 引き継ぎ'),
 ('2026-09-23', '絵を1枚も出していない（門が開いていない）',
  'OpenAI直は残高切れ（429）。Grok／Genspark掲示板は閉。外部の判定も取れていない',
  'お金', 'OpenAIに入金するか、Gensparkの残1,925クレジット（10/4で消える）で1枚出す', '1030番 絵の門 引き継ぎ'),
 ('2026-09-23', '政治家の相続税のページ／庶民版（2回落ちた）',
  'share/check/1035-souzokuzei.html が存在しない＝2回とも成果物まで届いていない',
  'こちら', '別便に任せず、こちらで1枚だけ書いて share/check に出す', '1036番 引き継ぎ＋実測'),
 ('2026-09-23', 'Gensparkのリサーチの返り（出典URLが未確認）',
  '「裏取り待ち／裏が取れた／取れなかった」を返す形は作ったが、進捗表に差し込んでいない',
  'こちら', '返ってきた出典URLを1本ずつ叩いて、200だったものだけ残す', '1036番 引き継ぎ'),
 ('2026-09-23', 'Julesの出典URLが未確認',
  'PR #464 は検品16秒で合格（91.3%）したが、出典URLそのものは叩いていない',
  'こちら', '出典URLを全部叩いて、落ちたものを外してから受け取り待ちに出す', '1030番 引き継ぎ'),
 ('2026-09-23', 'PR #462 が未マージ',
  'mainに入れる＝Lovable＝本番公開で不可逆。憲法第5条で止まってよい側',
  'たまごさん', '中身の要約と差分を1画面にして、マージしてよいかを1タップで聞く', '1030番 引き継ぎ'),
 ('2026-09-23', 'xAIの「0のチーム」（goodvibes／3e0b4d97-…）がどのログインのものか特定できていない',
  'Chromeが未ログインで console.x.ai の該当チーム画面が開けない',
  'たまごさん', 'たまごさんが console.x.ai に1回ログインする。その後はこちらで読める', '1037番 報告'),
 ('2026-09-23', 'Supabaseの service role 鍵が無くて棚に書けない',
  'Macの .env にあるのは SUPABASE_PUBLISHABLE_KEY まで。入れる係は完成していて鍵だけが無い',
  'たまごさん', 'Supabaseのダッシュボードから service_role 鍵を1本出して置く。置いた日から動く', '1039番 棚入れ 引き継ぎ'),
 ('2026-09-23', '中継所（スマホから投げる口）の200を確認していない',
  'status/public/relay.json の url は https://tamago-shinchoku.loca.lt（最終更新 09-23 20:54）。叩いていない',
  'こちら', 'URLを叩いて200を確認する。落ちていたらトンネルを張り直す', 'status/public/relay.json'),
 ('2026-09-23', 'Claudeのログインが切れている（工場が止まっている）',
  'OAuth session expired。直近6時間で走った148本→取れた0本（09-23 23:46 時点の現在地）',
  'たまごさん', 'いつものClaudeのアプリで1回ログインし直す。こちらが気づいて自動で再開する', 'status/genzaichi.md'),
 ('2026-09-23', '1年もつ鍵（setup-token）への入れ替えが未着手＝また必ず切れる',
  'キーチェーンの更新用の鍵（refreshToken）まで長さ0。CLIは自力で作り直せない',
  'たまごさん', '端末で setup-token を1本作って置く。9/5に置いた形跡はあるが use_token が無く一度も使われていない', '1029番 開通 引き継ぎ'),
 ('2026-09-23', 'Gmailの鍵が無くて見張り4本が閉じたまま（LINE審査結果の見張りを含む）',
  '/Users/mac/.tamago/gmail_app_password が空',
  'たまごさん', 'Gmailのアプリパスワードを1本作って置く', '1026番 引き継ぎ'),
 ('2026-09-23', 'Metaの鍵がまだ作られていない',
  '「見つからなかったのは隠れていたからではなく、誰も見ていなかったから」',
  'たまごさん', 'Meta（Instagram）の鍵を作るか、作らない判断をする', '1029番 開通 引き継ぎ'),
 ('2026-09-23', 'OpenAIが残高切れ（429 insufficient_quota）',
  '1回も鳴らせていない。絵も声も止まる',
  'お金', '入金するか、使わない判断をする', '1031番 引き継ぎ'),
 ('2026-09-23', 'Grokのクレジット：Macの鍵は team_blocked（goodvibesチーム）',
  'お金が入っているのは TAMAGO\'s team（$9.41）で、その鍵は Supabase の中。別の財布',
  'たまごさん', 'Macの鍵を TAMAGO\'s team の鍵に差し替える（~/.tamago/keys/api_keys.env がマウント外でこちらから書けない）', '1034番 引き継ぎ'),
 ('2026-09-23', 'xAIの残高 $9.41 を使い切ると声が止まる（auto top-upを切った）',
  '残高が減る一方。$2を割ったら知らせる仕組みも入っていない',
  'こちら', '$2を割ったら1回だけ知らせる見張りを入れる（自動で足さない）', '1037番 引き継ぎ'),
 ('2026-09-23', 'Copilotの権限が無い',
  'tools/nageru.py の copilot を how="blocked" にしたので、以後は投げずに止まる',
  'たまごさん', 'Copilotの権限を取るか、使わない判断をする', '1025番 引き継ぎ'),
 ('2026-09-23', '今日の外部の口の上限が0円に落ちていて、コピーの書き手が2人とも止まっている',
  'gemini 鍵なし／grok 上限で停止。鍵が来ても0円のままだとコピーが書けない',
  'お金', 'tools/yosan.py の上限を1日いくらまでにするか決めて入れる', '1039番 棚入れ 引き継ぎ'),
 ('2026-09-22', '関所を3回連続で落ちた11件が「他社AIへ出す候補」のまま放置',
  'REPEATED_UNFIXED.md に11件。ほぼ全部「px/%の数字を主張しているが実測した跡が無い」',
  'こちら', '実測の生データを貼る形に直して1件ずつ通す。同じ経路で4回目を試さない', 'status/REPEATED_UNFIXED.md'),
 ('2026-09-23', 'Devinの返事待ち1件（devin-30896e69…）が24時間近く放置',
  '取りに行くか閉じるかを決めていない',
  'こちら', '取りに行って中身を読むか、閉じる。どちらかを今日中に決める', '1027番 引き継ぎ'),
 ('2026-09-23', 'Julesにコピー書きだけを切り出して投げる（コピー単体の質が未実測）',
  '1本も投げていない',
  'こちら', '曲の選定はこちらでやって、コピー書きだけ1本投げて質を見る', '1027番 引き継ぎ'),
 ('2026-09-23', '動画の検品（素人カバー・静止画だけの動画を弾く）が全件「未確認」',
  '判定する仕組みが無い',
  'こちら', '1日分だけ手で検品して、弾く条件を決めてから機械にする', '1026番 引き継ぎ'),
 ('2026-09-23', '曲の初出年を取り直す',
  '手を付けていない',
  'こちら', 'mbid経由で取り直す。ただし下のmbid未確認が先', '1026番 引き継ぎ'),
 ('2026-09-23', 'mbid（MusicBrainzのID）の正しさが未確認',
  'この環境から musicbrainz.org に出られない',
  'こちら', '工場側（gaibu_runner）に代行させて1件ずつ確かめる', '1027番 引き継ぎ'),
 ('2026-09-23', '絵と文字が合っているかの判定が機械でできていない',
  'tools/mainichi_kuchi.py:146 で「未判定」と出している',
  'こちら', '判定できないなら「未判定」と出し続けるのではなく、判定の型を1つ決める', '1038番 引き継ぎ'),
 ('2026-09-23', '発車待ちの「毎日やること」重複12件を消す許可待ち',
  'n=788,815,818,844,877,903,938,948,977,1004,1016,1037。今日から積まれないが古い分が残っている',
  'たまごさん', '12件まとめて「消していいですか」を1タップで聞く', '1038番 引き継ぎ'),
 ('2026-09-22', 'origin=factory の票を確認列から外す実装が提案止まり',
  'たまごさんの目に入る物を変える変更なので、本人の一言を取っていない',
  'たまごさん', '「機械が自分で作った票は確認列に出さない」でよいかを1回聞く', '1022番 引き継ぎ'),
 ('2026-09-22', '古い git_lock_reaper.py と5分便の find -delete をそのまま残してある',
  'gitを叩く口が2つある状態が続いている＝index.lockがまた残る',
  'こちら', '新しい口だけに寄せて、古い2つを止める', '1023番 引き継ぎ'),
 ('2026-09-23', '進捗表の配信係が黙って止まることがある（止まったことが記録に残らない）',
  '「公開しました」も「公開のpushに3回とも失敗しました」も、どちらも残さずに消える',
  'こちら', '成功と失敗の両方を必ず1行残す。残っていなければ赤を出す', '1027b番 引き継ぎ'),
 ('2026-09-23', 'おかねの流れ一枚地図：ページは出来ているが公開できていない',
  '画像1枚（share/check/img/1029-okane-chizu.jpg・199KB）が commit_inbox に残ったまま',
  'こちら', '画像を通してから、ページのURLを叩いて200を確認して渡す', '1029番 引き継ぎ'),
 ('2026-09-23', 'おかねの流れ地図の設計（1028_okane_chizu_sekkei.md）がたまごさん未確認',
  '実装済・🟡のまま',
  'たまごさん', '見て、これでいいかを1回返す', '1028番 引き継ぎ'),
 ('2026-09-23', '財務省 予算書・決算書DB／官報が未確認のまま（おかねの地図の材料）',
  'フレーム構成で本文が取れない／官報はPDFのみ',
  'こちら', 'frame src を個別に特定して取り直す。取れなければ「取れない」と書いて閉じる', '1028番 実測'),
 ('2026-09-23', 'さとうさおり氏の辞職日・辞職理由が一次資料で未確認（特別会計の件）',
  '公的な一次資料に当たれていない。因果関係も未確認',
  'こちら', '令和8年第3回都議会定例会の会議録か都選管の告示PDFを開く', '1028番 特別会計 引き継ぎ'),
 ('2026-09-23', 'たまごさんが送ったX投稿（hasibiro_maga）の主張の棚卸しが未着手',
  '手を付けていない',
  'こちら', '主張を1行ずつ並べて、裏が取れたもの／取れないものに分ける', '1028番 特別会計 引き継ぎ'),
 ('2026-09-23', '棚入れの「戻し」の実測ができていない',
  '鍵が無くて入れられていないので、戻すものが無い',
  'たまごさん', 'Supabaseのservice_role鍵が来た日に、入れて戻す往復を1回実測する', '1039番 棚入れ 引き継ぎ'),
 ('2026-09-23', 'わえちゃん（Cosmic Wae）のCollabsが動いていない',
  '675番と同じ根。Metaの鍵が無いので投稿の口が開いていない',
  'たまごさん', 'Metaの鍵が来てから。来るまでは下書きだけ溜める', '1029番 開通＋発車待ち675'),
 ('2026-09-24', '仕組み系タスク #842「憲法点検：工場が止まったまま放置されていないか」が170時間waiting',
  '発車待ちのまま誰も着火していない',
  'こちら', '今日の一番上に上げて着火する', 'status/genzaichi.md'),
]

for (dt, what, wh, who, nx, src) in EX:
    md = datetime.date(*map(int, dt.split('-')))
    rows.append({'src': src, 'date': dt, 'days': (TODAY - md).days, 'what': what,
                 'where': wh, 'who': who, 'next': nx, 'origin': 'user'})

GH = [
 (1, '2026-09-20', '【調査依頼】喋る卵のキャラクターをWebサイトに置きたい'),
 (2, '2026-09-21', '【リサーチ依頼】AIソロプレナーの勝ち筋を世界の最先端で調べる'),
 (3, '2026-09-21', '【読み】案内人が名前を正しく読むためのカタカナの読み'),
 (4, '2026-09-22', '【Grokに聞く】この掲示板が通っているかの確認（977号）'),
 (5, '2026-09-22', '【Gensparkに頼む】この掲示板が通っているかの確認（977号）'),
 (6, '2026-09-22', '【Grokに聞く】AIエージェント多数運用で人間の意思決定ボトルネックを外す'),
 (7, '2026-09-22', '【チャッピー(ChatGPT直)に聞く】同上（977号）'),
 (8, '2026-09-22', '【チャッピー(ChatGPT直)に聞く】同上（第2回・モデル指定あり）'),
]
for (n, dt, t) in GH:
    md = datetime.date(*map(int, dt.split('-')))
    rows.append({'src': f'GitHub ai-kaigi #{n}', 'date': dt, 'days': (TODAY - md).days,
                 'what': t, 'where': 'Issueが開いたまま。返事が返っていないか、返っても取り込んでいない',
                 'who': '外のAI', 'next': '返事を読んで棚か進捗表に取り込む。返っていなければ閉じる',
                 'origin': 'user'})

ORDER = ['こちら', 'たまごさん', '外のAI', 'お金']
for r in rows:
    r['_k'] = (r['date'] if r['date'] != '不明' else '9999-99-99')
rows.sort(key=lambda r: r['_k'])

cnt = {k: sum(1 for r in rows if r['who'] == k) for k in ORDER}
TOTAL_ASKED = len(items) + len(EX) + len(GH)
TOTAL_DONE = len(done)
TOTAL_MIKAN = len(rows)

CLS = {'こちら': 'w-us', 'たまごさん': 'w-you', '外のAI': 'w-ai', 'お金': 'w-mo'}


def esc(s):
    return html.escape(str(s))


def card(r, idx):
    dd = f"{r['days']}日" if r['days'] is not None else '不明'
    return f"""<li class="it">
<div class="hd"><span class="no">{idx}</span><span class="w {CLS[r['who']]}">{esc(r['who'])}</span><span class="dt">{esc(r['date'])}・<b>{dd}止まっている</b></span></div>
<div class="wt">{esc(r['what'])}</div>
<dl>
<dt>今どこで止まっているか</dt><dd>{esc(r['where'])}</dd>
<dt>次の1手</dt><dd>{esc(r['next'])}</dd>
<dt>出どころ</dt><dd>{esc(r['src'])}</dd>
</dl></li>"""


secs = []
for k in ORDER:
    rs = [r for r in rows if r['who'] == k]
    body = '\n'.join(card(r, i + 1) for i, r in enumerate(rs))
    secs.append(f"""<section id="s-{CLS[k]}">
<h2 class="{CLS[k]}">止めているのは「{esc(k)}」<span class="c">{len(rs)}件</span></h2>
<ol class="list">{body}</ol></section>""")

HTML = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1043 未完の一覧</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;padding:14px 12px 60px;background:#12110f;color:#efe9df;
font:15px/1.65 -apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}}
h1{{font-size:19px;margin:0 0 4px}}
.sub{{font-size:12px;color:#9a938a;margin:0 0 16px}}
.nums{{display:flex;gap:6px;margin:0 0 10px}}
.nums div{{flex:1;background:#1c1a17;border:1px solid #2e2a25;border-radius:10px;padding:10px 6px;text-align:center}}
.nums b{{display:block;font-size:26px;line-height:1.1}}
.nums span{{font-size:11px;color:#9a938a}}
.hl{{background:#2a1512;border:1px solid #7a2f22;border-radius:10px;padding:12px;margin:0 0 18px;font-size:14px}}
.hl b{{font-size:24px;color:#ff8a6e}}
h2{{font-size:15px;margin:26px 0 10px;padding:8px 10px;border-radius:8px;background:#1c1a17;border-left:5px solid #666}}
h2 .c{{float:right;font-weight:700;color:#efe9df;font-size:13px}}
h2.w-us{{border-left-color:#ff6b4a}} h2.w-you{{border-left-color:#f0c040}}
h2.w-ai{{border-left-color:#5aa9e6}} h2.w-mo{{border-left-color:#7ac47a}}
.list{{list-style:none;margin:0;padding:0}}
.it{{background:#191714;border:1px solid #2a2622;border-radius:10px;padding:10px 11px;margin:0 0 8px}}
.hd{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:5px}}
.no{{font-size:11px;color:#6f6960;min-width:24px}}
.w{{font-size:11px;padding:1px 7px;border-radius:99px;color:#12110f;font-weight:700}}
.w.w-us{{background:#ff6b4a}} .w.w-you{{background:#f0c040}} .w.w-ai{{background:#5aa9e6}} .w.w-mo{{background:#7ac47a}}
.dt{{font-size:11px;color:#9a938a}}
.wt{{font-size:14.5px;font-weight:700;margin:0 0 6px;word-break:break-word}}
dl{{margin:0;font-size:12.5px}}
dt{{color:#8d867d;font-size:11px;margin-top:5px}}
dd{{margin:0;color:#d8d1c7;word-break:break-word}}
.note{{margin-top:30px;font-size:12.5px;color:#b5ada2;background:#1c1a17;border:1px solid #2e2a25;border-radius:10px;padding:12px}}
.note h3{{font-size:13px;margin:0 0 6px;color:#efe9df}}
</style></head><body>
<h1>頼まれたのに終わっていないもの</h1>
<p class="sub">2026-09-24 時点。発車待ちの列・引き継ぎ・GitHub・実測から機械で拾った全件。1件も落としていない。</p>
<div class="nums">
<div><b>{TOTAL_ASKED}</b><span>頼まれた総数</span></div>
<div><b>{TOTAL_DONE}</b><span>終わった</span></div>
<div><b>{TOTAL_MIKAN}</b><span>終わっていない</span></div>
</div>
<div class="hl">うち、止めているのが<b>こちら＝{cnt['こちら']}件</b><br>
たまごさん {cnt['たまごさん']}件 ／ 外のAI {cnt['外のAI']}件 ／ お金 {cnt['お金']}件</div>
{''.join(secs)}
<div class="note">
<h3>洗えなかった場所（正直に）</h3>
<p>・たまごさんのObsidian（tamago_brain の 00 inbox と最近7日のノート）は、この口からファイルに届かないので<b>1件も見ていません</b>。ここに未完が入っていれば、上の数字はその分だけ少ないです。</p>
<p>・GitHub の joy-relief-station は、Chromeが未ログインで404。<b>開いているIssueとPRを1件も確認できていません</b>（PR #462・#464・#467・#468 の状態も取れていません）。上のPR関連の行は引き継ぎの記録から拾ったものです。</p>
<p>・GitHub ai-kaigi の8件は、発車待ちの GH### 行と同じ依頼が混ざっている可能性があります。少なく見せないため<b>両方残しました</b>。</p>
<p>・日数は「いつ頼まれたか」が記録から取れた最古の日付で計算しています。記録が無いものは「不明」と出しています。</p>
</div>
</body></html>"""

out = os.path.join(ROOT, 'share/check/1043-mikan.html')
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, 'w').write(HTML)
print('wrote', out, len(HTML), 'bytes')
print('asked', TOTAL_ASKED, 'done', TOTAL_DONE, 'mikan', TOTAL_MIKAN, cnt)
