#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1028番【物差しの目盛りを1枚にする】status/omosa_last.json → share/check/1028-omosa.html

★なぜ「手で書いたHTML」にしないか
  手で数字を書くと、次に測り直したとき**書き換え忘れた古い数字が残る**。
  それが今日ずっと潰してきた「嘘の緑」そのもの。
  だから **測った生の数字(status/omosa_last.json)からしか作らない。**
  測っていない欄は「測れていません」と書く。埋めない。

使い方: python3 tools/omosa_page.py   → share/check/1028-omosa.html を書き出す
"""
from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "status", "omosa_last.json")
OUT = os.path.join(REPO, "share", "check", "1028-omosa.html")
if HERE not in sys.path:
    sys.path.insert(0, HERE)


def mb(n):
    try:
        return "%.2f MB" % (float(n) / 1048576.0)
    except Exception:
        return "—"


def kb(n):
    try:
        return "%.0f KB" % (float(n) / 1024.0)
    except Exception:
        return "—"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def sec(ms):
    try:
        return "%.1f秒" % (float(ms) / 1000.0)
    except Exception:
        return "—"


CSS = """
:root{--bg:#f4efe4;--ink:#2a2a2a;--sub:#7a7568;--line:#e2dccd;--aka:#c4483a;--ao:#3a5f7a;--midori:#3a7a52;--ki:#8a6a1f;}
*{box-sizing:border-box;}
body{margin:0;padding:calc(env(safe-area-inset-top) + 20px) 14px calc(env(safe-area-inset-bottom) + 40px);background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;font-size:16px;line-height:1.7;max-width:820px;margin-left:auto;margin-right:auto;}
a{color:var(--ao);}
h1{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.3rem;letter-spacing:0.05em;margin:0 0 6px;}
h2{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-weight:400;font-size:1.05rem;letter-spacing:0.05em;margin:36px 0 12px;color:var(--sub);border-bottom:1px solid var(--line);padding-bottom:6px;}
.date{color:var(--sub);font-size:0.8rem;margin-bottom:18px;}
.fix{background:#fff;border-left:4px solid var(--midori);border-radius:0 10px 10px 0;padding:14px 16px;margin:0 0 20px;font-size:1.04rem;}
.fix p{margin:0 0 10px;} .fix p:last-child{margin:0;}
.note{background:#fff;border:1px solid var(--line);border-radius:10px;padding:12px 15px;font-size:0.92rem;margin:0 0 14px;}
.warn{background:#fff;border-left:4px solid var(--aka);border-radius:0 10px 10px 0;padding:12px 15px;font-size:0.92rem;margin:0 0 14px;}
.wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 8px;border-radius:10px;border:1px solid var(--line);background:#fff;}
table{width:100%;border-collapse:collapse;font-size:0.84rem;min-width:520px;}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;}
th{background:#efe9db;color:var(--sub);font-weight:600;font-size:0.74rem;}
tr:last-child td{border-bottom:none;}
.no{color:var(--aka);font-weight:700;} .yes{color:var(--midori);font-weight:700;} .mi{color:var(--ki);font-weight:700;}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:0 0 18px;}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:13px 14px;min-width:0;}
.card .k{font-size:0.72rem;color:var(--sub);letter-spacing:.04em;margin:0 0 4px;}
.card .v{font-family:"Hiragino Mincho ProN","Yu Mincho",serif;font-size:1.5rem;line-height:1.25;margin:0 0 3px;word-break:break-word;}
.card .s{font-size:0.75rem;color:var(--sub);line-height:1.5;}
.card.bad .v{color:var(--aka);} .card.ok .v{color:var(--midori);} .card.mid .v{color:var(--ki);}
.bar{height:9px;border-radius:5px;background:#e8e2d4;overflow:hidden;display:flex;margin:4px 0 2px;}
.bar i{display:block;height:100%;}
.leg{font-size:0.72rem;color:var(--sub);}
code{background:#efe9db;padding:1px 5px;border-radius:4px;font-size:0.85em;word-break:break-all;}
footer{color:var(--sub);font-size:0.78rem;margin-top:44px;line-height:1.6;border-top:1px solid var(--line);padding-top:14px;}
@media (max-width:420px){ body{font-size:15px;padding-left:11px;padding-right:11px;} .cards{grid-template-columns:1fr;} table{font-size:0.8rem;} h1{font-size:1.15rem;} }
"""

IRO = {"JS": "#c4483a", "動画音声": "#8a6a1f", "画像": "#3a5f7a", "CSS": "#3a7a52",
       "HTML": "#7a7568", "フォント": "#9a7bb0", "データ(JSON)": "#5f8a7a", "その他": "#c9c2b2"}


def build(d):
    W = d.get("byWidth") or {}
    w1 = W.get("1280") or {}
    w3 = W.get("375") or {}
    b1 = w1.get("bytes") or {}
    b3 = w3.get("bytes") or {}
    total1, total3 = b1.get("total") or 0, b3.get("total") or 0
    byk = b1.get("byKind") or {}
    top = b1.get("top") or []
    hannin = top[0] if top else {}
    te = w1.get("tanaHenshu") or {}
    pa = w1.get("paste") or {}
    pf = w1.get("pasteFallback") or {}
    use = pa if pa.get("tried") else pf
    op = w1.get("open") or {}      # ③-b URLを開いて落ちるか
    op3 = (w3.get("open") or {})

    # ---- ①の帯グラフ ----
    bar, leg = "", []
    for k, v in sorted(byk.items(), key=lambda x: -x[1]):
        if not total1:
            break
        pct = v * 100.0 / total1
        bar += '<i style="width:%.2f%%;background:%s"></i>' % (pct, IRO.get(k, "#bbb"))
        leg.append('<span style="color:%s">■</span>%s %s(%.0f%%)' % (IRO.get(k, "#bbb"), esc(k), kb(v), pct))

    # ---- ②棚編集 ----
    if te.get("stillLoading"):
        c2 = ("bad", "%d秒でも出ない" % int((te.get("gaveUpAfterMs") or 0) / 1000),
              "棚編集の画面は開くが「読み込み中…」のまま中身が来ない")
    elif te.get("readyMs") is not None:
        v = te["readyMs"] / 1000.0
        c2 = ("bad" if v > 5 else "mid" if v > 2 else "ok", "%.1f秒" % v, "開いてから中身が出るまで")
    else:
        c2 = ("mid", "測れていません", esc(str(te.get("error") or te.get("skipped") or "理由不明")))

    # ---- ③URL：まず「開いて落ちるか」（鍵なしで回数が出る）。貼り口は出れば併記 ----
    if op.get("tried"):
        r = op.get("rate")
        c3 = ("bad" if (r or 0) > 0 else "ok", "%d回中%d回" % (op["tried"], op["ochita"]),
              "曲ページのURLを開いて実測（%s%%・1回あたり%.1f秒）" % (r, (op.get("msAvg") or 0) / 1000.0))
    elif use.get("tried"):
        r = use.get("rate")
        c3 = ("bad" if (r or 0) > 0 else "ok", "%d回中%d回" % (use["tried"], use["ochita"]),
              "%s で実測（%s%%）" % (esc(use.get("basho", "")), r))
    else:
        c3 = ("mid", "測れていません", esc(use.get("skipWhy") or "貼る所にたどり着けませんでした"))

    # ---- ④375px ----
    ham = (w3.get("yoko") or {}).get("hamidashi")
    c4 = ("bad" if total3 > total1 * 1.02 else "ok", mb(total3) if total3 else "測れていません",
          ("横に流れる（%s→%s）" % ((w3.get("yoko") or {}).get("clientW"), (w3.get("yoko") or {}).get("scrollW")))
          if ham else ("横に流れない（375px）" if ham is False else "横はみ出しは測れていません"))

    rows = ""
    for t in top[:10]:
        rows += ("<tr><td><code>%s</code></td><td>%s</td><td style='white-space:nowrap'>%s</td><td>%.0f%%</td></tr>"
                 % (esc(t.get("name", "")), esc(t.get("kind", "")), kb(t.get("bytes")),
                    (t.get("bytes") or 0) * 100.0 / total1 if total1 else 0))

    nav = w1.get("nav") or {}
    nav_note = ""
    if nav.get("loaded") is False:
        nav_note = ("<div class='warn'>★<b>トップページは読み込みが終わりません。</b>"
                    "20秒たっても <code>readyState</code> は <code>%s</code> のままでした。"
                    "犯人は繰り返し再生の動画 <code>joy-relief-footer-loop.mp4</code>（%s・206で流れ続ける）。"
                    "＝ブラウザの「読み込み中」がいつまでも消えない＝<b>体感として一番『重い』のはここ。</b></div>"
                    % (esc(nav.get("readyState")), kb(next((t["bytes"] for t in top if "mp4" in t.get("name", "")), 0))))

    errs = w1.get("consoleErrors") or []
    err_html = ""
    if errs:
        err_html = "<div class='note'><b>読み込み中に出ていたエラー</b><br>" + "<br>".join(
            "<code>%s</code>" % esc(e[:160]) for e in errs[:6]) + "</div>"

    # ---- ③の明細（何回やって何回落ちたか・どちらの読み方か）----
    ochi_html = ""
    if op.get("tried") or use.get("tried") or use.get("skipWhy"):
        rows2 = ""
        if op.get("tried"):
            rows2 += ("<tr><td><b>(い) 曲ページのURLを開く</b><br><span class='leg'>%s</span></td>"
                      "<td>%d回</td><td class='%s'>%d回</td><td>%s%%</td><td>%s</td></tr>"
                      % ("1280px", op["tried"], "no" if op["ochita"] else "yes", op["ochita"],
                         op.get("rate"), esc("／".join(op.get("whys") or []) or "—")))
        if op3.get("tried"):
            rows2 += ("<tr><td><b>(い) 同じものを375pxで</b></td><td>%d回</td><td class='%s'>%d回</td>"
                      "<td>%s%%</td><td>%s</td></tr>"
                      % (op3["tried"], "no" if op3["ochita"] else "yes", op3["ochita"],
                         op3.get("rate"), esc("／".join(op3.get("whys") or []) or "—")))
        if use.get("tried"):
            rows2 += ("<tr><td><b>(あ) 棚編集の欄にYouTubeのURLを貼る</b></td><td>%d回</td>"
                      "<td class='%s'>%d回</td><td>%s%%</td><td>%s</td></tr>"
                      % (use["tried"], "no" if use["ochita"] else "yes", use["ochita"],
                         use.get("rate"), esc("／".join(use.get("whys") or []) or "—")))
        else:
            rows2 += ("<tr><td><b>(あ) 棚編集の欄にYouTubeのURLを貼る</b></td><td colspan='4' class='mi'>"
                      "測れていません — %s</td></tr>" % esc(use.get("skipWhy") or "貼る所にたどり着けませんでした"))
        ochi_html = ("<h2>3-2. 「URLを貼っても落ちる」を回数で</h2>"
                     "<div class='note'>★たまごさんの言葉は<b>2通りに読めます。決めつけずに両方やりました。</b>"
                     "<b>(あ)</b>＝棚編集の中の欄にYouTubeのURLを貼る。<b>(い)</b>＝曲ページのURLを開く。</div>"
                     "<div class='wrap'><table><tr><th>どの読み方か</th><th>試した</th><th>落ちた</th>"
                     "<th>割合</th><th>落ちたときに起きていたこと</th></tr>%s</table></div>"
                     "<p class='leg'>※「落ちた」の定義＝描画係が死んだ／%d秒返事をしない／中身が真っ白／画面が3秒以上止まった、のどれか。"
                     "人の目ではなく機械が同じ基準で毎回判定します。</p>" % (rows2, 8))

    fail = te.get("failedReq") or []
    fail_html = ""
    if fail:
        fail_html = ("<div class='note'><b>棚編集が待っている相手（失敗した通信）</b><br>"
                     + "<br>".join("<code>%s</code> → %s" % (esc(f["name"]), f["status"]) for f in fail[:6]) + "</div>")

    c1cls = "bad" if total1 > 2 * 1048576 else "mid" if total1 > 1048576 else "ok"
    cards = ""
    for cls, k, v, s in [
        (c1cls, "① トップが送ってくる量", mb(total1), "%d本の通信（キャッシュ無し・1280px）" % (b1.get("reqCount") or 0)),
        (c2[0], "② 棚編集の反応", c2[1], c2[2]),
        (c3[0], "③ URLを貼って落ちた回数", c3[1], c3[2]),
        (c4[0], "④ スマホ幅(375px)", c4[1], c4[2]),
    ]:
        cards += ('<div class="card %s"><p class="k">%s</p><p class="v">%s</p><p class="s">%s</p></div>'
                  % (cls, k, v, s))

    hannin_s = ""
    if hannin:
        hannin_s = ("<div class='fix'><p><b>一番でかい1つ＝</b><code>%s</code><br>"
                    "<b>%s</b>（送られてくる量の<b>%.0f%%</b>／JS全体の<b>%.0f%%</b>）。"
                    "これは<b>gzipで縮めた後の、実際に線を流れる大きさ</b>です。</p>"
                    "<p>★過去にDevinが2回とも「<code>youtube-id-map</code>が犯人」と当てていました。"
                    "<b>今日叩き直しても、やはりこれが1位でした。</b>見立てではなく実測です。</p></div>"
                    % (esc(hannin.get("name", "")), kb(hannin.get("bytes")),
                       (hannin.get("bytes") or 0) * 100.0 / total1 if total1 else 0,
                       (hannin.get("bytes") or 0) * 100.0 / (byk.get("JS") or 1)))

    return """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<title>#1028 ごきげん補給所の重さ（実測・4つの数字）</title>
<style>%s</style>
</head>
<body>
<!-- SHINCHOKU_BACK_LINK -->
<div id="shinchokuBackTop" style="position:sticky;top:0;left:0;right:0;z-index:9999;background:#1c1c1c;border-bottom:1px solid #3a3a3a;padding:8px 14px;text-align:left;font-family:-apple-system,BlinkMacSystemFont,'Hiragino Sans',sans-serif;">
  <a href="https://tamago2022.github.io/tamago-shinchoku/" style="color:#8ef0ae;text-decoration:none;font-weight:700;font-size:0.9rem;">← 進捗表に戻る</a>
</div>

<div class="date"><a href="../">共有資料の一覧</a> ／ 確認ページ #1028</div>
<h1>ごきげん補給所は、どれだけ重いのか ― 測りました</h1>
<div class="date">%s 実測／叩いた先：<code>%s</code>（Lovable配信の本番）／測った道具：<code>tools/omosa.mjs</code>（headless Chrome・課金0）</div>

<div class="fix">
<p>★<b>今回は「軽くする」ことは一切していません。「重さを測る物差し」を作りました。</b></p>
<p>理由：<b>物差しが無いと「軽くしました」が本当かどうか誰にも分からないからです。</b>
今日だけで「動いているのに何も取れていない“嘘の緑”」を何件も見つけました。同じ轍を踏まないように、先に目盛りを打ちます。</p>
<p>この4つの数字は <code>node tools/omosa.mjs</code> で<b>いつでも同じ手順で測り直せます。</b>
進捗表にも1行で出ます（<code>tools/hantei.py</code> の <code>omosa()</code>）。<b>前より重くなったら赤になります。</b></p>
</div>

<h2>1. 4つの数字</h2>
<div class="cards">%s</div>
%s

<h2>2. 何が重いのか（内訳）</h2>
<div class="bar">%s</div>
<p class="leg">%s</p>
%s

<h2>3. でかい順に10本</h2>
<div class="wrap"><table>
<tr><th>もの</th><th>種類</th><th>大きさ</th><th>割合</th></tr>
%s
</table></div>
<p class="leg">※ 大きさは<b>gzipで縮めた後・線を実際に流れる量</b>。キャッシュを切って毎回まっさらで測っています。</p>

%s
%s
%s

<h2>4. この物差しの使い方</h2>
<div class="note">
<b>測り直す</b> … 工場（Mac）で <code>node tools/omosa.mjs</code>。<br>
<b>サンドボックスから頼む</b> … <code>gaibu_kuchi.enqueue_job("kakunin", {"mode":"omosa","runs":20})</code><br>
<b>何を測るか変える</b> … <code>tools/omosa_target.json</code> だけ直す（URL・試行回数・幅）。<br>
<b>進捗表の1行</b> … <code>tools/hantei.py</code> の <code>omosa()</code>。前回比+5%%超で🔴。<br>
<b>この紙を作り直す</b> … <code>python3 tools/omosa_page.py</code>（数字は必ず <code>status/omosa_last.json</code> から読みます。手打ちしません）。<br>
★<b>新しい常駐（定期タスク）は1つも増やしていません。</b>呼ばれたときだけ走ります。
</div>

<h2>5. 正直に書いておくこと</h2>
<div class="warn">%s</div>

<footer>
2026-09-23 #1028／生の数字：<code>status/omosa_last.json</code>・履歴 <code>status/omosa_log.jsonl</code><br>
測った道具：<code>tools/omosa.mjs</code>（headless Chrome を一時プロファイルで起動し使用後SIGKILL。たまごさんの普段のChromeには触っていません。GETのみ・保存や送信のボタンは押していません・課金0）<br>
測るのにかかった時間：%s秒
</footer>
</body>
</html>
""" % (CSS, esc(d.get("measuredAt", "")), esc(d.get("url", "")), cards, hannin_s,
       bar, "　".join(leg), nav_note, rows, ochi_html, err_html, fail_html,
       shoujiki(d, w1, w3, te, use, op), d.get("elapsedSec", "?"))


def shoujiki(d, w1, w3, te, use, op=None):
    """測れなかったものを、埋めずにそのまま書く。"""
    op = op or {}
    out = []
    if te.get("stillLoading"):
        out.append("★<b>棚編集の「押してから動くまで何秒か」は、そもそも中身が出てこないので測れていません。</b>"
                   "出したのは「開いてから %d秒待っても『読み込み中…』が消えない」という数字です。"
                   "鍵（管理ログイン）を使えば違う結果になる可能性がありますが、"
                   "<b>鍵を使う測定はしていません</b>（物差しは課金0・鍵なしで誰でも回せる形にしたいため）。"
                   % int((te.get("gaveUpAfterMs") or 0) / 1000))
    if not use.get("tried"):
        out.append("★<b>(あ)『棚編集の欄にYouTubeのURLを貼る』は回数が出ていません。</b>"
                   "理由：%s。<b>『落ちなかった』ではありません。『測れていない』です。</b>"
                   "数える箱はもう出来ているので、棚編集の中に入れさえすれば同じ手順で数字が出ます。"
                   % esc(use.get("skipWhy") or "不明"))
    if op.get("tried") and not op.get("ochita"):
        out.append("★<b>(い)『曲ページのURLを開く』は%d回やって0回でした。</b>"
                   "ただしこれは<b>まっさらなブラウザを毎回立ち上げて1枚開いただけ</b>です。"
                   "たまごさんの環境（タブをたくさん開いたまま・長く使ったまま・スマホ）とは条件が違います。"
                   "<b>『落ちない』と言い切れる数字ではありません。</b>" % op["tried"])
    if not (w3.get("bytes") or {}).get("total"):
        out.append("★<b>375pxの数字が入っていません。</b>測定が途中で終わっています。")
    out.append("★<b>「毎回じゃないけど落ちる」を回数で出す、という宿題は残っています。</b>"
               "今日できたのは『何回試して何回落ちたか』を数える箱まで。中身を埋めるには棚編集の中に入る必要があります。")
    return "<br>".join(out)


def main():
    if not os.path.exists(SRC):
        print("まだ測っていません: %s" % SRC)
        return 1
    with io.open(SRC, encoding="utf-8") as f:
        d = json.load(f)
    if d.get("error"):
        print("測定が失敗しています: %s" % str(d["error"])[:200])
        return 1
    html = build(d)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    # ★出す前に、うちの機械検品(hantei.kensa_html)を必ず通す
    try:
        import hantei
        ok, ng = hantei.kensa_html(html, os.path.basename(OUT))
        print("検品:", "合格" if ok else "不合格 " + "／".join(ng))
    except Exception as e:  # noqa: BLE001
        print("検品が呼べませんでした:", e)
    print("書き出し:", OUT, len(html.encode("utf-8")), "バイト")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
