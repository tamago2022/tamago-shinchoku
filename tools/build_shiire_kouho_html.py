#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仕入れ候補を1枚で見えるようにする。

status/shiire_kouho/*.json から share/check/990-shiire-kouho.html を組む。
★手でHTMLを書かない。データから組む（данные と表示がずれないように）。
★375pxでも読める。棚ではなく「候補」だと一目で分かる見た目にする。
"""

import io
import json
import os
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(REPO, "status", "shiire_kouho")
OUT = os.path.join(REPO, "share", "check", "990-shiire-kouho.html")


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def main():
    files = sorted(f for f in os.listdir(SRC)
                   if f.endswith(".json") and not f.startswith("_"))
    blocks, total, asia_total, novideo = [], 0, 0, 0
    for fn in files:
        d = json.load(io.open(os.path.join(SRC, fn), encoding="utf-8"))
        ent = d.get("entry") or {}
        cands = d.get("candidates") or []
        total += len(cands)
        asia_total += len([c for c in cands if c.get("asia")
                           or str(c.get("axis", "")).endswith("アジア")])
        novideo += len([c for c in cands if c.get("video") == "未確認"])
        rows = []
        for c in cands:
            asia = "アジア" if (c.get("asia") or str(c.get("axis", "")).endswith("アジア")) else ""
            # ★出典がURLでないものを「出典」のリンクにしない（2026-09-24・1045番）。
            #   押しても何も無いリンクに「出典」と書いてあるのは、出典が有るように見えて
            #   実際は無い＝一番たちの悪い形。**取れていないなら、取れていないと字で出す。**
            #   （関所 sekisho-jijitsu-shutten「取れなければ、その語を落とす」）
            _src = str(c.get("src") or "")
            _srchtml = ('<a href="%s" target="_blank" rel="noopener">出典</a>' % esc(_src)
                        if _src.startswith("http") else
                        '<span class="nosrc">出典：%s</span>'
                        % esc(_src or "まだ取れていない"))
            rows.append(
                '<li class="c"><div class="hd"><span class="ax">%s</span>'
                '%s<b>%s</b><span class="ar">%s</span></div>'
                '<p class="why">%s</p><p class="fact">%s</p>'
                '<p class="meta">%s'
                '<span class="v">動画：%s</span></p></li>' % (
                    esc(c.get("axis")),
                    ('<span class="asia">%s</span>' % asia) if asia else "",
                    esc(c.get("name")), esc(c.get("area") or ""),
                    esc(c.get("why")), esc(c.get("fact") or ""),
                    _srchtml, esc(c.get("video") or "未確認")))
        rej = "".join('<li><b>%s</b>：%s <a href="%s" target="_blank" rel="noopener">出典</a></li>'
                      % (esc(r.get("name")), esc(r.get("why")), esc(r.get("src")))
                      for r in (d.get("rejected") or []))
        nyc = "".join("<li>%s</li>" % esc(x) for x in (d.get("notYetChecked") or []))
        blocks.append(
            '<section class="entry"><h2>入口：%s<span class="song">%s</span></h2>'
            '<p class="ewhy">%s</p><p class="eid">%s</p>'
            '<ol class="list">%s</ol>'
            '%s%s</section>' % (
                esc(ent.get("artist")),
                ('「%s」' % esc(ent.get("song"))) if ent.get("song") else "",
                esc(ent.get("why") or ""), esc(ent.get("identity") or ""),
                "".join(rows),
                ('<details class="rej"><summary>外したもの（%d）</summary><ul>%s</ul></details>'
                 % (len(d.get("rejected") or []), rej)) if rej else "",
                ('<details class="nyc"><summary>まだ取れていないもの（%d）</summary><ul>%s</ul></details>'
                 % (len(d.get("notYetChecked") or []), nyc)) if nyc else ""))

    run = {}
    rp = os.path.join(SRC, "_run.json")
    if os.path.exists(rp):
        run = json.load(io.open(rp, encoding="utf-8"))
    runs = run.get("runs", 0)
    red = (runs > 0 and total == 0)

    html = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>仕入れ候補（棚にはまだ入れていない）</title>
<style>
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f6f4ef;color:#1c1a17;
 font:16px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
header{background:#1c1a17;color:#f6f4ef;padding:22px 18px}
header h1{margin:0;font-size:20px;letter-spacing:.04em}
header p{margin:6px 0 0;font-size:13px;opacity:.78}
.badge{display:inline-block;margin-top:10px;padding:4px 10px;border-radius:999px;
 background:#c8a44a;color:#1c1a17;font-size:12px;font-weight:700}
.nums{display:flex;gap:10px;flex-wrap:wrap;padding:14px 18px;background:#fff;
 border-bottom:1px solid #e3ded2}
.num{flex:1 1 130px;border:1px solid #e3ded2;border-radius:10px;padding:10px 12px;background:#fdfcf9}
.num b{display:block;font-size:22px;line-height:1.2}
.num span{font-size:11px;opacity:.65}
.red{border-color:#b4332b;background:#fdf1f0}
.red b{color:#b4332b}
main{padding:18px;max-width:900px;margin:0 auto}
.nosrc{color:#a33;font-size:.82rem}
.entry{margin:0 0 30px}
.entry h2{font-size:17px;margin:0 0 4px;padding-bottom:8px;border-bottom:2px solid #1c1a17}
.song{font-weight:400;opacity:.7}
.ewhy{margin:8px 0 2px;font-size:13px}
.eid{margin:0 0 14px;font-size:12px;opacity:.68}
.list{list-style:none;margin:0;padding:0;counter-reset:c}
.c{counter-increment:c;background:#fff;border:1px solid #e3ded2;border-radius:12px;
 padding:13px 14px 11px;margin:0 0 9px}
.c .hd{display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}
.c .hd::before{content:counter(c);font-size:11px;opacity:.45;min-width:16px}
.c b{font-size:15px}
.ax{font-size:10px;background:#efeadd;border-radius:4px;padding:2px 6px;opacity:.8}
.asia{font-size:10px;background:#1c1a17;color:#f6f4ef;border-radius:4px;padding:2px 6px}
.ar{font-size:11px;opacity:.6}
.why{margin:7px 0 0;font-size:14px}
.fact{margin:5px 0 0;font-size:12px;opacity:.72}
.meta{margin:7px 0 0;font-size:11px;display:flex;gap:12px;align-items:center}
.meta a{color:#7a5c12}
.v{opacity:.6}
details{margin:12px 0 0;font-size:13px}
summary{cursor:pointer;opacity:.75}
details ul{margin:8px 0 0;padding-left:18px}
details li{margin:0 0 6px;font-size:12px;opacity:.8}
footer{padding:18px;font-size:11px;opacity:.6;text-align:center}
@media(max-width:400px){main{padding:12px}.c{padding:11px 11px 9px}}
</style></head><body>
<header><h1>仕入れ候補</h1>
<p>1本入れたら、その周りを勝手に掘って溜めた場所。</p>
<span class="badge">★まだ棚には入れていません</span></header>
<div class="nums">
<div class="num"><b>%d</b><span>候補の数</span></div>
<div class="num"><b>%d</b><span>うちアジア</span></div>
<div class="num%s"><b>%d</b><span>走った回数</span></div>
<div class="num"><b>%d</b><span>動画が未確認</span></div>
</div>
<main>%s</main>
<footer>%s に組み直し ／ 元データ status/shiire_kouho/ ／ 0円の道だけ（MusicBrainz・Last.fmの公開ページ・Wikipedia）</footer>
</body></html>""" % (total, asia_total, " red" if red else "", runs, novideo,
                     "".join(blocks), time.strftime("%Y-%m-%d %H:%M"))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(html)
    print("書いた: %s ／ 候補%d件（うちアジア%d件）／ 動画未確認%d件"
          % (OUT, total, asia_total, novideo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
