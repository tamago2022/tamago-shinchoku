# -*- coding: utf-8 -*-
"""検品ページ share/check/979-yomi.html を作る。数字は毎回ビルド結果から取る（手で書かない）。
   使い方: python3 tools/yomi/make_check_page.py
"""
import json, os, subprocess, html, datetime, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "tools", "yomi", "out")

def j(n):
    return json.load(open(os.path.join(OUT, n), encoding="utf-8"))

def esc(s):
    return html.escape(str(s))

def main():
    st = j("yomi-stats.json")
    detail = j("yomi-artists.detail.json")
    review = j("yomi-review.json")
    try:
        test = subprocess.run(["node", os.path.join(ROOT, "tools/yomi/test_yomi.mjs")],
                              capture_output=True, text=True, cwd=ROOT, timeout=120)
        test_out, test_ok = test.stdout.strip(), test.returncode == 0
    except Exception as e:
        test_out, test_ok = "テストを走らせられませんでした: %s" % e, False

    src_count = {}
    for e in detail:
        if e["yomi"]:
            k = e["src"].split("（")[0]
            src_count[k] = src_count.get(k, 0) + 1
    src_rows = sorted(src_count.items(), key=lambda x: -x[1])

    red = [r for r in review if r["type"] == "artist" and r["band"] == "red"]
    conflict = [r for r in review if r["type"] == "artist" and r["band"] == "yellow"
                and any("割れ" in s for s in r["reasons"])]
    today = datetime.date.today().isoformat()

    P = []
    A = P.append
    A('<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">')
    A('<meta name="viewport" content="width=device-width, initial-scale=1">')
    A('<title>案内人の読み方 ― King Gnu を「キングヌー」にする</title>')
    A('''<style>
:root{--paper:#EDE6D6;--ink:#22304A;--accent:#C1442E;--ok:#2F6B4F;
--rule:rgba(34,48,74,.18);--faint:rgba(34,48,74,.60)}
*{box-sizing:border-box}
html,body{overflow-x:hidden;max-width:100%}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);
 font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.85;font-size:16px}
.wrap{max-width:60rem;margin:0 auto;padding:7vw 6vw 14vw}
.eyebrow{font-size:.68rem;letter-spacing:.42em;color:var(--faint);margin:0 0 1.6rem}
h1{font-weight:400;font-size:clamp(1.45rem,5vw,2.3rem);letter-spacing:.09em;margin:0 0 .4rem;line-height:1.5}
.sub{color:var(--faint);font-size:.8rem;letter-spacing:.12em;margin:0 0 3.2rem}
.verdict{border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);padding:2rem 0;margin:0 0 3.2rem}
.verdict p{margin:0 0 1.1rem;font-size:clamp(1rem,2.7vw,1.13rem);line-height:1.95}
.verdict p:last-child{margin-bottom:0}
.verdict .n{color:var(--accent);letter-spacing:.3em;font-size:.7rem;margin-right:.9em;vertical-align:.18em}
.big{color:var(--accent)}
h2{font-weight:400;font-size:.74rem;letter-spacing:.34em;color:var(--faint);
 margin:4.2rem 0 1.4rem;padding-bottom:.7rem;border-bottom:1px solid var(--rule)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:1px;
 background:var(--rule);border:1px solid var(--rule);margin:0 0 1.4rem}
.card{background:var(--paper);padding:1.2rem .9rem}
.card b{display:block;font-weight:400;font-size:clamp(1.5rem,6vw,2rem);letter-spacing:.02em;line-height:1.2}
.card span{display:block;font-size:.68rem;letter-spacing:.14em;color:var(--faint);margin-top:.5rem}
.card.red b{color:var(--accent)} .card.ok b{color:var(--ok)}
pre{background:rgba(34,48,74,.05);border-left:2px solid var(--ok);padding:1rem 1rem;
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;line-height:1.75;
 overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%;white-space:pre}
pre.ng{border-left-color:var(--accent)}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;max-width:100%}
.swipe{display:none;font-size:.68rem;letter-spacing:.2em;color:var(--accent);margin:0 0 .5rem}
@media(max-width:47rem){.swipe{display:block}}
table{border-collapse:collapse;width:100%;font-size:.82rem}
table.wide{min-width:34rem}
th,td{text-align:left;padding:.75rem .7rem;border-bottom:1px solid var(--rule);vertical-align:top;line-height:1.7}
th{font-weight:400;font-size:.64rem;letter-spacing:.14em;color:var(--faint);border-bottom:1px solid var(--ink);white-space:nowrap}
td.y{color:var(--accent);white-space:nowrap}
td.name{word-break:break-word}
p.note{font-size:.86rem;color:var(--faint);margin:1rem 0 0}
ol,ul{padding-left:1.2rem}
li{margin:.5rem 0}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.82em;
 background:rgba(34,48,74,.06);padding:.1em .35em;border-radius:2px;word-break:break-all}
.foot{margin-top:5rem;padding-top:1.2rem;border-top:1px solid var(--rule);
 font-size:.7rem;letter-spacing:.1em;color:var(--faint)}
</style></head><body><div class="wrap">''')

    A('<p class="eyebrow">979 ― 検品</p>')
    A('<h1>案内人の読み方<br>King Gnu を「キングヌー」にする</h1>')
    A('<p class="sub">%s ／ ごきげん補給所</p>' % today)

    A('<div class="verdict">')
    A('<p><span class="n">01</span>アーティスト <span class="big">%d件中 %d件</span>に読みが付きました。'
      '読みを渡さないのは、外国名で案内人がそのまま読める <b>%d件</b>。'
      '人（外部AI）に確かめてもらうのは <span class="big">%d件</span>だけです。</p>'
      % (st["artists_total"], st["artists_dict"], st["foreign_auto"], st["red"]))
    A('<p><span class="n">02</span>King Gnu が <b>キングヌー</b>として案内人に渡ることを、'
      '機械で確かめました（下のテスト）。<b>耳で音を聞く確認はまだです</b>'
      '（音声APIは有料。走らせる前に必ず値段を出します）。</p>')
    A('<p><span class="n">03</span>新しいアーティストが入荷したら <code>bash tools/yomi/run.sh</code> の1本で'
      '読みが付き直し、<b>危ないものだけ赤で残ります</b>。1回きりの手作業にしていません。</p>')
    A('</div>')

    A('<h2>数</h2>')
    A('<div class="cards">')
    for cls, n, lab in [
        ("ok", st["green"], "そのまま使える"),
        ("", st["yellow"], "推定・要確認"),
        ("red", st["red"], "赤・機械では読めない"),
        ("", st["foreign_auto"], "外国名（案内人が読む）"),
        ("ok", st["songs_dict"], "曲名にも読みが付いた"),
        ("", st["songs_ja"], "日本語の曲名ぜんぶ"),
    ]:
        A('<div class="card %s"><b>%d</b><span>%s</span></div>' % (cls, n, lab))
    A('</div>')
    A('<p class="note">曲名は日本語のもの %d件のうち %d件。'
      '残りは動画タイトルそのままのものが多く、読みの元が無いので案内人にまかせています。</p>'
      % (st["songs_ja"], st["songs_dict"]))

    A('<h2>どこから読みを取ったか</h2>')
    A('<div class="scroll"><table><tr><th>出どころ</th><th>件数</th></tr>')
    for k, v in src_rows:
        A('<tr><td>%s</td><td>%d</td></tr>' % (esc(k), v))
    A('</table></div>')
    A('<p class="note">いちばん大きいのは <b>すでに持っていたデータ</b>（coverGuide.ts の aliases）。'
      'King Gnu も「キングヌー」を最初から持っていました。'
      '<b>案内人がそれを見ていなかった</b>のが原因です。</p>')

    A('<h2>King Gnu が正しく渡るか（自動テスト）</h2>')
    A('<pre%s>%s</pre>' % ("" if test_ok else ' class="ng"', esc(test_out)))
    A('<p class="note">走らせ方：<code>node tools/yomi/test_yomi.mjs</code>。'
      '音声APIに送る本文そのものを組み立てて、カタカナが入っているかを見ています。</p>')

    A('<h2>赤 ― 機械では読めないので確かめてもらうもの（%d件）</h2>' % len(red))
    A('<p class="swipe">← 横にスワイプ</p><div class="scroll"><table class="wide">')
    A('<tr><th>名前</th><th>機械の案</th><th>なぜ危ないか</th></tr>')
    for r in red[:60]:
        A('<tr><td class="name">%s</td><td class="y">%s</td><td>%s</td></tr>'
          % (esc(r["name"]), esc(r["yomi"] or "—"), esc("／".join(r["reasons"])[:70])))
    A('</table></div>')
    if len(red) > 60:
        A('<p class="note">ここに出しているのは先頭60件。全部は '
          '<code>share/yomi/yomi-review.json</code> にあります。</p>')

    A('<h2>読みが2つに割れているもの（%d件）</h2>' % len(conflict))
    A('<div class="scroll"><table class="wide"><tr><th>名前</th><th>採った読み</th><th>候補</th></tr>')
    for r in conflict[:25]:
        A('<tr><td class="name">%s</td><td class="y">%s</td><td>%s</td></tr>'
          % (esc(r["name"]), esc(r["yomi"] or "—"),
             esc("／".join(r["reasons"]).replace("読みが割れている：", "")[:70])))
    A('</table></div>')

    A('<h2>仕組み</h2>')
    A('<ol>')
    A('<li><b>読みを起こす</b>（0円）― 手で入れた辞書 → 既存データの aliases → '
      'id のローマ字 → 形態素解析（Sudachi）の順。2つの結果が一致したものだけ「確定」にする。'
      '<code>tools/yomi/build_yomi.py</code></li>')
    A('<li><b>案内人が読む形にする</b> ― <code>share/yomi/yomi.js</code> を書き出す。'
      '検索結果に <code>yomi</code> を足し、指示文の末尾に読みを固定する1ブロックを付ける。</li>')
    A('<li><b>危ないものだけ外に出す</b> ― <code>tools/yomi/out/kaigi-question.md</code> を '
      'tamago2022/ai-kaigi の Issue に貼り、ChatGPT(Codex) と Gemini(Jules) に読ませる。'
      '<b>2社が一致したものは自動で採用</b>、割れたものだけ人が見る。'
      '<code>tools/yomi/merge_answers.py</code></li>')
    A('<li><b>次から自動</b> ― 入荷のたび <code>bash tools/yomi/run.sh</code>。'
      '読みが付き、テストが走り、赤だけが残る。</li>')
    A('</ol>')

    A('<h2>音声APIは読み仮名を受け取れるのか</h2>')
    A('<p>受け取れません。いま使っている <b>speech-to-speech</b>（OpenAI Realtime／xAI realtime）は '
      'SSML や発音記号のタグを持たず、<b>言葉で指示するか、渡す文字そのものを変えるか</b>の二択です。'
      'なので本筋どおり、<b>渡すテキストをカタカナにする</b>方式にしました。</p>')

    A('<div class="foot">つくり： tools/yomi/ ／ '
      '辞書： share/yomi/yomi.js ／ 赤の一覧： share/yomi/yomi-review.json</div>')
    A('</div></body></html>')

    dst = os.path.join(ROOT, "share", "check", "979-yomi.html")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w", encoding="utf-8").write("\n".join(P))
    print(dst, os.path.getsize(dst), "bytes", "／テスト:", "OK" if test_ok else "NG")

if __name__ == "__main__":
    main()
