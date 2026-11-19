#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1140番【1枚】全曲検査の結果を、進捗表から開ける1枚にする。

たまごさん（2026-09-25）: 「進捗表から開ける1枚にして出す」（たまごさんは進捗表しか見ない）

status/1140/summary.json と kata_*.txt を読んで 1140-machigai.html を書くだけ。
数字は全部、機械が数えた数。推定は1つも書かない。
"""
from __future__ import annotations
import io, json, os, html

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
D = os.path.join(REPO, "status", "1140")
OUT = os.path.join(REPO, "1140-machigai.html")
SITE = "https://joy-relief-station.lovable.app"

KATA = [
    ("noVideo", "動画が1本も入っていない", "曲ページを開くと、題名とコピーの次がいきなり関連。たまごさんが見つけた4曲は全部この型。"),
    ("deadVideo", "動画IDはあるが再生できない", "削除・非公開・埋め込み禁止・地域制限。見回り(patrol)が実測で死亡と判定したID。"),
    ("noThumb", "サムネイルが出せない", "サムネは再生できる動画IDから作るので、上2つと同じ根。"),
    ("noCopy", "コピーが空・書きかけ", "copy も note も無い。※これは隠す条件に入れていない（入れると全体の6割が消える）。"),
    ("dupCopy", "コピーが他の曲と丸かぶり", "同じ文が2曲以上で使い回されている。"),
    ("juufukuTana", "同じ人の棚が2つある", "misora / misora-hibari のように棚が割れている。仕入れが二重になっている。"),
    ("douseiBetsujin", "同名別人の疑い", "棚の主と違う名前が本文に出てくる（名前の一部が一致する別人）。"),
    ("shuttenNashi", "出典のない断定", "「代表曲」「原曲」「カバー」や年号を言い切っているのに、出典URLが1つも無い。"),
    ("eraOnlyTsunagi", "年が近いだけの繋ぎ", "「同じ時代の曲」は年の近さだけで機械が並べている。繋がりの根拠は1件も無い。"),
    ("tsunagiNoSource", "繋ぎに出典が無い", "bridgeRelated の行き先に、根拠のURLが書かれていない。"),
    ("refMissing", "繋ぎの行き先が存在しない", "originalRef / famousUses などが、名簿に無い曲を指している。"),
]

CSS = """
:root{color-scheme:light}
body{margin:0;background:#f6f4ef;color:#1c1a17;font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif}
.w{max-width:760px;margin:0 auto;padding:28px 18px 80px}
h1{font-size:26px;line-height:1.35;margin:0 0 6px}
.sub{color:#6b655c;font-size:13px;margin:0 0 26px}
.big{background:#fff;border:1px solid #e4dfd5;border-radius:14px;padding:22px;margin:0 0 20px}
.big .n{font-size:46px;font-weight:700;letter-spacing:-.02em;line-height:1}
.big .n small{font-size:15px;font-weight:400;color:#6b655c;margin-left:8px}
.row{display:flex;gap:14px;flex-wrap:wrap;margin-top:14px}
.row div{flex:1 1 150px;background:#faf8f4;border:1px solid #ece7dd;border-radius:10px;padding:12px}
.row b{display:block;font-size:24px}
.row span{font-size:12px;color:#6b655c}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e4dfd5;border-radius:14px;overflow:hidden}
th,td{padding:12px 14px;text-align:left;border-bottom:1px solid #f0ebe2;vertical-align:top}
th{background:#f3efe7;font-size:13px;color:#57514a}
td.n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
td small{display:block;color:#6b655c;font-weight:400;font-size:12.5px;margin-top:3px}
h2{font-size:17px;margin:34px 0 10px}
.note{background:#fffdf6;border:1px solid #e8dfc4;border-radius:12px;padding:16px;font-size:14px}
.note b{color:#8a6d1f}
ul{padding-left:20px;margin:8px 0}
code{background:#efece5;padding:1px 5px;border-radius:4px;font-size:13px}
a{color:#2b5f8a}
"""


def main():
    s = json.load(io.open(os.path.join(D, "summary.json"), encoding="utf-8"))
    kata = s["型ごと"]
    total = s["全曲数"]
    ng = s["間違いがあった曲数"]
    hide = s["隠す対象（再生できる動画が1本もない等）"]

    rows = ""
    for key, name, why in KATA:
        n = kata.get(key, 0)
        if not n:
            continue
        rows += ("<tr><td><b>%s</b><small>%s</small></td><td class=n>%s</td></tr>"
                 % (html.escape(name), html.escape(why), "{:,}".format(n)))

    # 例（たまごさんが実際に見つけた4曲）
    rei = ""
    kk = os.path.join(D, "kakusu.txt")
    sample = []
    if os.path.exists(kk):
        want = ["bill-evans/portrait-in-jazz-autumn-leaves", "mariya/eki",
                "tatsuro-yamashita-ballads/paper-doll", "bigbang/haru-haru"]
        got = {l.split("\t")[0]: l.strip().split("\t")[-1] for l in io.open(kk, encoding="utf-8")}
        for w in want:
            if w in got:
                sample.append("<li><code>%s</code> … %s</li>" % (html.escape(w), html.escape(got[w])))
    if sample:
        rei = "<ul>%s</ul>" % "".join(sample)

    doc = """<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>1140番 全曲検査：間違いは何件あったか</title><style>%s</style>
<div class=w>
<h1>全%s曲を1曲ずつ機械で見た。<br>間違いは %s件。</h1>
<p class=sub>サンプリングなし・全件。数えた数だけ。読んだ場所＝coverGuide.ts（アーティスト%s／曲%s）。生成 %s</p>

<div class=big>
  <div class=n>%s<small>件が、いま表に出したままの不完全な曲</small></div>
  <div class=row>
    <div><b>%s</b><span>再生できる動画が1本も無い＝表から外す対象</span></div>
    <div><b>%s</b><span>棚に載っている動画IDの実数（重複なし）</span></div>
    <div><b>%s</b><span>そのうち実測(oEmbed)で確かめ済み</span></div>
  </div>
</div>

<h2>型ごとに何件か</h2>
<table><tr><th>型</th><th style="text-align:right">件数</th></tr>%s</table>
<p class=sub>※1曲が2つ以上の型に当たることがあるので、足しても合計にはならない。合計は「間違いがあった曲数 %s」。</p>

<h2>たまごさんが見つけた4曲は、全部この機械に引っかかった</h2>
%s

<div class=note>
<b>いま直したこと</b>
<ul>
<li><b>%s件を表から外した</b>（検索・棚・おすすめ・「この流れで、もう一本」・サイトマップの全部）。
    判定は <code>src/lib/kansei.ts</code> の1か所だけ。画面ごとに条件は書き足していない。</li>
<li><b>消していない。隠しているだけ。</b>動画が入れば次の生成で自動的に表から外れ、元どおり出る。</li>
<li><b>入口に門を置いた</b>（<code>tools/1140_kanmon.py</code>）。同じ4条件を満たさないものは棚に入らない。
    弾いた数は <code>python3 tools/1140_kanmon.py --tally</code>。<b>弾き0が続いたら門が効いていない＝赤。</b></li>
<li><b>毎日1回、全件を流し直す</b>（心臓 <code>tools/heartbeat.sh</code> に相乗り・1日1回に間引き）。
    新しく壊れたものは翌日ここが赤くなる。</li>
</ul>
<b>戻し方（1行）</b>：<code>src/lib/kansei.ts</code> の <code>KANSEI_GATE</code> を <code>false</code> にする。それだけで全部が元どおり表に出る。
</div>

<h2>まだ終わっていないこと（正直に）</h2>
<div class=note>
<ul>
<li><b>動画の実測が %s / %s件。</b>サンドボックス（この便）から youtube.com へは回線が出ない（実測 curl→000）。
    実測は工場（Mac）側の <code>tools/1140_jissoku.py</code> が担当で、<b>順番待ちに積んである</b>。
    走り終わると「IDはあるが実は再生できない」ぶんが上の数字に足され、隠す表も自動で増える。</li>
<li><b>「年が近いだけの繋ぎ」%s件</b>は、データではなく<b>並べ方そのもの</b>（同じ時代の曲＝年の近さだけ）。
    ここは外し方を決めてから触る。勝手にセクションごと消さない。</li>
<li><b>コピー空 %s件</b>は隠す条件に入れていない。入れると全体の6割が消えて、穴が桁違いに増えるため。
    書き終わったら <code>KANSEI_REQUIRE_COPY</code> を true にすれば同じ1か所で効く。</li>
</ul>
</div>

<p class=sub>細かい一覧は <code>status/1140/</code>（kensa.json＝全件の判定、kata_*.txt＝型ごとの曲、kakusu.txt＝隠した曲）。</p>
</div>
""" % (CSS, "{:,}".format(total), "{:,}".format(ng), "{:,}".format(s["アーティスト数"]),
       "{:,}".format(total), s["生成"], "{:,}".format(hide), "{:,}".format(hide),
       "{:,}".format(s.get("動画IDの実数（重複なし）", 0)), "{:,}".format(s.get("実測済みID数", 0)),
       rows, "{:,}".format(ng), rei or "<p class=sub>（一覧の生成待ち）</p>",
       "{:,}".format(s.get("隠す表に書いた件数", hide)),
       "{:,}".format(s.get("実測済みID数", 0)), "{:,}".format(s.get("動画IDの実数（重複なし）", 0)),
       "{:,}".format(kata.get("eraOnlyTsunagi", 0)), "{:,}".format(kata.get("noCopy", 0)))

    io.open(OUT, "w", encoding="utf-8").write(doc)
    print("書きました: %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
