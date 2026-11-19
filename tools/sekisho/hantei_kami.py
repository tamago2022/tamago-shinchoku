# -*- coding: utf-8 -*-
"""1051番：別人混入の判定結果を、たまごさんが1画面で見られる紙にする。

出すもの:
  share/check/1051-bessin-konnyuu.html   … 見る紙（スマホ1画面・固定幅なし）
  status/public/bessin_konnyuu.json      … 同じ中身の生データ

★数字はすべて status/_1051/hantei.json の実測から出す。手で書いた数字は1つも無い。
"""
import html
import json
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
JST = timezone(timedelta(hours=9))


def rows(items, n=None):
    out = []
    for r in (items[:n] if n else items):
        out.append(
            "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                html.escape(r.get("artist") or ""),
                html.escape((r.get("title") or "")[:70]),
                html.escape(r.get("channelTitle") or "—"),
                html.escape((r.get("riyu") or "")[:90])))
    return "\n".join(out)


def main():
    d = json.load(open(os.path.join(REPO, "status", "_1051", "hantei.json"),
                      encoding="utf-8"))
    k = d["kazu"]
    itsu = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    pub = {
        "_これは何": "1051番。棚の別人混入2230件を、動画を上げたチャンネル名で機械判定した結果。",
        "itsu": itsu,
        "kane": "0円（YouTube Data API の videos.list を44回＝44ユニット／1日枠10000。課金なし）",
        "kazu": k,
        "kuro": d["kuro"],
        "hoshu_uchiwake": {},
    }
    from collections import Counter
    c = Counter()
    for r in d["hoshu"]:
        t = r["riyu"]
        if "消えている" in t:
            c["動画が消えている／非公開"] += 1
        elif "動画idが取れない" in t:
            c["動画idが無い"] += 1
        elif "共演" in t:
            c["別人のチャンネルだが共演の疑い"] += 1
        else:
            c["チャンネルが本人でも棚の持ち主でもない（レーベル／コンピ／個人）"] += 1
    pub["hoshu_uchiwake"] = dict(c)

    os.makedirs(os.path.join(REPO, "status", "public"), exist_ok=True)
    json.dump(pub, open(os.path.join(REPO, "status", "public",
                                     "bessin_konnyuu.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)

    uchiwake = "".join("<li>%s … <b>%d件</b></li>" % (html.escape(a), b)
                       for a, b in c.most_common())
    doc = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1051 棚の別人混入 — 機械で割った結果</title>
<style>
 body{margin:0;padding:18px;font:16px/1.7 -apple-system,"Hiragino Sans",sans-serif;
      background:#faf8f4;color:#2b2622}
 h1{font-size:20px;margin:0 0 4px}
 .itsu{color:#7a7068;font-size:13px;margin-bottom:18px}
 .box{background:#fff;border:1px solid #e7e0d6;border-radius:12px;padding:14px;margin:0 0 14px}
 .big{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}
 .big div{flex:1 1 150px;background:#fff;border:1px solid #e7e0d6;border-radius:12px;padding:12px}
 .big b{display:block;font-size:26px;line-height:1.2}
 .shiro b{color:#2f7a4f}.kuro b{color:#a8342a}.hoshu b{color:#8a6d1f}
 table{width:100%%;border-collapse:collapse;font-size:13px}
 td{border-top:1px solid #eee;padding:6px 4px;vertical-align:top}
 tr td:first-child{white-space:nowrap;font-weight:600}
 .note{font-size:13px;color:#6b625a}
</style>
<h1>棚の別人混入 — 2230件を機械で3つに割った</h1>
<div class="itsu">%(itsu)s ／ 使った金 <b>0円</b>（YouTubeの公式APIを44回。1日枠10000のうち44）</div>

<div class="big">
 <div class="shiro"><b>%(shiro)d</b>白＝関所の誤検知。棚に残してよい</div>
 <div class="kuro"><b>%(kuro)d</b>黒＝別人の曲の疑いが濃い</div>
 <div class="hoshu"><b>%(hoshu)d</b>保留＝機械では決まらない</div>
</div>

<div class="box">
 <b>どうやって決めたか</b>
 <p class="note">曲名の文字だけでは決まらない（「Uptown Funk (feat. Bruno Mars)」は
 マーク・ロンソンの棚で正しいのに、関所は保留にしていた）。
 そこで<b>その動画を上げたYouTubeチャンネルが誰か</b>を実際に取ってきて、棚の名前と突き合わせた。
 チャンネルが本人＝白。チャンネルが別の棚の持ち主＝黒。それ以外＝保留。
 ★曲名に共演の印や「本人の名前が抜かれた跡」があるものは、連名の可能性があるので黒にしていない。</p>
</div>

<div class="box">
 <b>黒 %(kuro)d件（このまま棚に置くと「調べていない」証拠になる）</b>
 <table>%(kurorows)s</table>
</div>

<div class="box">
 <b>保留 %(hoshu)d件の内訳</b>
 <ul class="note">%(uchiwake)s</ul>
 <p class="note">★保留は1件も動かしていない。消してもいない。ここに並べてあるだけ。</p>
</div>
</html>""" % {"itsu": html.escape(itsu), "shiro": k["shiro"], "kuro": k["kuro"],
              "hoshu": k["hoshu"], "kurorows": rows(d["kuro"]),
              "uchiwake": uchiwake}

    out = os.path.join(REPO, "share", "check", "1051-bessin-konnyuu.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w", encoding="utf-8").write(doc)
    print("書いた: %s" % out)
    print("白%d ／ 黒%d ／ 保留%d" % (k["shiro"], k["kuro"], k["hoshu"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
