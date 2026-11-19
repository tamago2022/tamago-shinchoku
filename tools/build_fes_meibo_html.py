#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""フェスの穴を1枚で見えるようにする。

★数字は status/fes_meibo/_coverage.json から取る。手で書かない。
★「それはありませんね率」が下がっていくのが見えることが、この画面の仕事。
"""

import io
import json
import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "status", "fes_meibo", "_coverage.json")
OUT = os.path.join(REPO, "share", "check", "991-fes-meibo.html")


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    if not os.path.exists(SRC):
        subprocess.call([sys.executable, os.path.join(REPO, "tools", "fes_meibo.py")])
    r = json.load(io.open(SRC, encoding="utf-8"))
    secs = []
    for f in r["festivals"]:
        q = "".join(
            '<li><span class="r">%d</span>%s%s</li>' % (
                h["rank"], esc(h["name"]),
                ' <span class="dj">DJ・別形態</span>' if h["kind"] != "出演者" else "")
            for h in f["queue"])
        al = "".join('<li>%s</li>' % esc(h["name"]) for h in f["already"])
        rate = f["naiRate"]
        cls = "bad" if rate >= 70 else ("mid" if rate >= 30 else "good")
        secs.append(
            '<section><h2>%s</h2>'
            '<p class="src">名簿の出どころ：<a href="%s" target="_blank" rel="noopener">公式ラインナップ</a>（%s 取得）</p>'
            '<div class="rate %s"><b>%.1f%%</b><span>「それはありませんね」率</span>'
            '<em>出演%d組のうち、棚にまだ1曲も無いのが%d組</em></div>'
            '<h3>仕入れ待ち（上から有名な順）%d組</h3><ol class="q">%s</ol>'
            '<details><summary>もう棚にある %d組（※名前が一致しただけ。同定はこれから）</summary><ul class="al">%s</ul></details>'
            '</section>' % (
                esc(f["festival"]), esc(f["source"]), esc(f["takenAt"]), cls,
                rate, f["counted"], f["holes"], f["holes"], q, f["have"], al))

    html = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>フェスの名簿と、棚の穴</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}
body{margin:0;background:#f6f4ef;color:#1c1a17;
 font:16px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
header{background:#1c1a17;color:#f6f4ef;padding:22px 18px}
header h1{margin:0;font-size:20px;letter-spacing:.04em}
header p{margin:6px 0 0;font-size:13px;opacity:.78}
.badge{display:inline-block;margin-top:10px;padding:4px 10px;border-radius:999px;
 background:#c8a44a;color:#1c1a17;font-size:12px;font-weight:700}
main{padding:18px;max-width:900px;margin:0 auto}
section{margin:0 0 34px}
h2{font-size:17px;margin:0 0 4px;padding-bottom:8px;border-bottom:2px solid #1c1a17}
.src{margin:8px 0 14px;font-size:12px;opacity:.7}.src a{color:#7a5c12}
.rate{background:#fff;border:1px solid #e3ded2;border-left-width:6px;border-radius:10px;
 padding:14px 16px;margin:0 0 18px}
.rate b{display:block;font-size:34px;line-height:1.1}
.rate span{font-size:12px;opacity:.7}
.rate em{display:block;margin-top:6px;font-style:normal;font-size:12px;opacity:.65}
.bad{border-left-color:#b4332b}.bad b{color:#b4332b}
.mid{border-left-color:#c8a44a}.mid b{color:#8a6f1d}
.good{border-left-color:#3f7a4a}.good b{color:#3f7a4a}
h3{font-size:13px;margin:0 0 8px;opacity:.75;font-weight:700}
.q{list-style:none;margin:0;padding:0;display:grid;
 grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:6px}
.q li{background:#fff;border:1px solid #e3ded2;border-radius:8px;padding:7px 10px;font-size:13px}
.r{display:inline-block;min-width:28px;font-size:10px;opacity:.45}
.dj{font-size:10px;background:#efeadd;border-radius:4px;padding:1px 5px;opacity:.75}
details{margin:14px 0 0;font-size:13px}summary{cursor:pointer;opacity:.75}
.al{columns:2;font-size:12px;opacity:.8;margin:8px 0 0;padding-left:18px}
footer{padding:18px;font-size:11px;opacity:.6;text-align:center}
@media(max-width:400px){main{padding:12px}.q{grid-template-columns:1fr}.al{columns:1}}
</style></head><body>
<header><h1>フェスの名簿と、棚の穴</h1>
<p>「誰が好きですか？」に『それはありませんね』と答えないための台帳。</p>
<span class="badge">★名簿です。まだ棚には入れていません</span></header>
<main>%s</main>
<footer>棚の突き合わせ元：%s ／ 棚のアーティスト %d組 ／ %s に組み直し<br>
※突き合わせは数を数えるためのもの。実際に曲を入れるときは入荷の関所（門2・別人を止める）を必ず通す。</footer>
</body></html>""" % ("".join(secs), esc(r.get("shelfSource")),
                     r.get("shelfArtists", 0), time.strftime("%Y-%m-%d %H:%M"))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(html)
    print("書いた: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
