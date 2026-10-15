#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""治っていないベスト20（★上から潰すための1枚）。

  ★作って終わりにしない。作った瞬間から1番を潰す。
  ★1つ潰すたびにページから消える（`tools/daicho.py --tsubushita <id> --url <URL>`）。
  ★潰した＝本番に出てURLで開ける、まで。pushだけでは消えない。

正本： status/daicho.json（回数・日数）／status/public/mitassei.json（総数・帰還率）
画面： share/best20.html
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import daicho as D  # noqa: E402

PAGE = os.path.join(REPO, "share", "best20.html")
MITASSEI = os.path.join(REPO, "status", "public", "mitassei.json")

CSS = """:root{color-scheme:light dark}
*{box-sizing:border-box}
body{margin:0;padding:12px 12px 40px;color:#1c1a17;background:#faf8f4;
font:15px/1.6 -apple-system,"Hiragino Sans",system-ui,sans-serif}
h1{font-size:18px;margin:0 0 2px}
.sub{font-size:12px;color:#7a736a;margin:0 0 10px}
.top{background:#fff;border:1px solid #e6e0d6;border-radius:12px;padding:10px 12px;margin-bottom:12px}
.top div{font-size:13px;margin:3px 0}
.top b{font-size:16px}
.aka{color:#c0392b}
ol{margin:0;padding:0 0 0 0;list-style:none;counter-reset:r}
li{counter-increment:r;background:#fff;border:1px solid #e6e0d6;border-left:4px solid #cfc7ba;
border-radius:10px;padding:9px 11px 9px 11px;margin-bottom:7px;display:flex;gap:9px;align-items:baseline}
li.a{border-left-color:#c0392b}
li.k{border-left-color:#d19a1d}
li::before{content:counter(r);flex:0 0 auto;font-weight:700;font-size:12px;background:#1c1a17;
color:#fff;border-radius:99px;padding:1px 8px;min-width:2em;text-align:center}
li.a::before{background:#c0392b}
.t{flex:1 1 auto;font-weight:600;font-size:14px}
.m{flex:0 0 auto;font-size:11px;color:#7a736a;text-align:right;line-height:1.35}
h2{font-size:14px;margin:18px 0 6px}
.bt{display:block;background:#fff;border:1px solid #e6e0d6;border-left:4px solid #0a58ca;
border-radius:10px;padding:10px 11px;margin-bottom:7px;font-size:14px;font-weight:600;
color:#1c1a17;text-decoration:none}
.ashi{margin-top:14px;font-size:11px;color:#8a8278;line-height:1.7}
a{color:#0a58ca;word-break:break-all}"""


def _m():
    try:
        return json.load(io.open(MITASSEI, encoding="utf-8"))
    except Exception:
        return {}


def page():
    d = D.yomu()
    rows = [r for r in d["rows"] if D.kikan_jotai(r) != D.KIKAN_KAETTA]
    # 回数の多い順 → 治っていない日数の多い順
    rows.sort(key=lambda r: (-(r.get("kaisu") or 1), -(r.get("naotteinai") or 0)))
    best = rows[:20]
    m = _m()
    k = m.get("kikan") or {}

    ko = []
    for r in best:
        kaisu = r.get("kaisu") or 1
        hi = r.get("naotteinai") or 0
        j = D.kikan_jotai(r)
        cls = "a" if (kaisu >= 3 or j == D.KIKAN_3) else ("k" if hi >= 7 else "")
        ko.append('<li class="%s"><span class=t>%s</span>'
                  '<span class=m>%s回・%s日<br>%s</span></li>'
                  % (cls, D._esc(r["irai"]), kaisu, hi, D._esc(j)))

    tama = (m.get("tamago_machi") or [])
    bt = "".join('<div class=bt>%s</div>' % D._esc(x["na"]) for x in tama[:8])

    atama = """<h1>治っていないベスト20</h1>
<p class=sub>上から潰す。潰した（本番で開ける）ものはこのページから消える。{asof} 現在</p>
<div class=top>
<div>未達成　<b>{zenbu}件</b>（概算）　こちらで終わる <b>{kochira}件</b>／たまごさん待ち <b>{tamago}件</b></div>
<div>帰還率　<b>{kr}％</b>　／　1回目で正しく帰ってきた率　<b>{ir}％</b></div>
<div class=aka>やり直し中で音沙汰なし　<b>{k3}件</b>（最優先）</div>
</div>""".format(
        asof=(m.get("asof") or "")[:16].replace("T", " "),
        zenbu=m.get("zenbu", "?"), kochira=m.get("kochira", "?"), tamago=m.get("tamago", "?"),
        kr=k.get("kikanritsu", "?"), ir=k.get("ippatsuritsu", "?"),
        k3=k.get("③yarinaoshi_onsata_nashi", "?"))

    html = ("<!doctype html><html lang=ja><head><meta charset=utf-8>"
            "<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            "<title>治っていないベスト20</title>\n<style>\n" + CSS + "\n</style></head><body>\n"
            + atama + "\n<ol>\n" + "\n".join(ko) + "\n</ol>\n"
            + (("<h2>たまごさんにしか押せないもの（%d件）</h2>\n" % len(tama)) + bt if tama else "")
            + '<div class=ashi>受付台帳 → <a href="daicho.html">daicho.html</a><br>'
              "回数＝この件に触れている仕事票＋引き継ぎメモの本数（機械で数えた）。"
              "URLが無いものは「潰した」にできない。</div>\n</body></html>")

    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with io.open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print(json.dumps({"書いた": PAGE, "並べた": len(best),
                      "URL": "https://tamago2022.github.io/tamago-shinchoku/share/best20.html"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(page())
