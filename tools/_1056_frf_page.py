#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1056番【FRF'26の棚を本番に出す】門0を通った組から、見て分かる1枚を組む。

- 材料：status/shiire_shoko/*.json（1055番が門0を通したもの）
- 出すのは **本人確定 かつ 公式動画がある組だけ**。
  （空サムネイル・空箱を出さないため。tamago-magazine-layout の決まり）
- サムネイルは公式動画のYouTube静止画。生死は status/_1056_thumb.json で確かめたものだけ載せる。

  python3 tools/_1056_frf_page.py --list      … 動画IDの一覧（生死確認用）
  python3 tools/_1056_frf_page.py --build OUT … HTMLを書く
"""
import json
import os
import re
import sys
import glob
import html

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHOKO = os.path.join(REPO, "status", "shiire_shoko")
THUMB = os.path.join(REPO, "status", "_1056_thumb.json")


def vid(url):
    if not url:
        return ""
    m = re.search(r"(?:youtu\.be/|/embed/|[?&]v=)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else ""


def load():
    out = []
    for f in sorted(glob.glob(os.path.join(SHOKO, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f, encoding="utf-8"))
        if d.get("hantei") != "本人確定":
            continue
        k = d.get("kokishiki") or {}
        v = vid(k.get("kokaiDouga"))
        if not v:
            continue
        d["_vid"] = v
        out.append(d)
    return out


def caption(memo):
    """公式ページから取った事実だけ残す。★から後ろは内部の注意書きなので落とす。"""
    if not memo:
        return ""
    s = memo.split("★")[0].strip()
    s = s.replace("裏を取った（公式ページ本文）：", "").strip()
    return s[:70]


def build(dest):
    alive = {}
    if os.path.exists(THUMB):
        alive = json.load(open(THUMB, encoding="utf-8"))
    def ok(v, kind):
        if not alive:
            return True
        return (alive.get(v) or {}).get(kind) == 200

    rows = [d for d in load() if ok(d["_vid"], "hq")]
    rows.sort(key=lambda d: d["name"].lower())
    # 扉の大きな画は、大判(maxres)が生きているものから選ぶ（ぼやけた画を全面に敷かない）
    hero = ""
    for d in rows:
        if ok(d["_vid"], "max"):
            hero = d["_vid"]
            break
    if not hero and rows:
        hero = rows[0]["_vid"]
    heroimg = "maxresdefault" if (not alive or ok(hero, "max")) else "hqdefault"
    cards = []
    for d in rows:
        k = d["kokishiki"]
        v = d["_vid"]
        links = ['<a class="l" href="https://www.youtube.com/watch?v=%s" target="_blank" rel="noopener">公式動画</a>' % v]
        if k.get("youtube"):
            links.append('<a class="l" href="%s" target="_blank" rel="noopener">公式チャンネル</a>' % html.escape(k["youtube"]))
        if k.get("site"):
            links.append('<a class="l" href="%s" target="_blank" rel="noopener">公式サイト</a>' % html.escape(k["site"]))
        shoko = (d.get("shoko") or [{}])[0].get("url", "")
        cap = caption(d.get("memo"))
        cards.append("""<article class="c">
  <a class="th" href="https://www.youtube.com/watch?v={v}" target="_blank" rel="noopener">
    <img loading="lazy" src="https://i.ytimg.com/vi/{v}/hqdefault.jpg" alt="{n} の公式動画">
  </a>
  <p class="k">{kuni}</p>
  <h3>{n}</h3>
  <p class="cap">{cap}</p>
  <p class="ls">{links}</p>
  <p class="src"><a href="{shoko}" target="_blank" rel="noopener">出どころ：FRF’26 公式アーティストページ</a></p>
</article>""".format(v=v, n=html.escape(d["name"]),
                     kuni=html.escape(d.get("honnin", {}).get("kuni") or ""),
                     cap=html.escape(cap), links=" ".join(links),
                     shoko=html.escape(shoko)))

    doc = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FUJI ROCK &rsquo;26 ― 本人だと確かめた@@N@@組｜ごきげん補給所</title>
<meta name="description" content="同姓同名の別人を弾いて、公式ページで本人だと確かめた@@N@@組。全部、公式の動画つき。">
<style>
:root{--bg:#0c0b09;--fg:#f2ede4;--dim:#8f877a;--ac:#d94f2b;--line:#2a2724}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font-family:"Hiragino Mincho ProN","Yu Mincho",serif;line-height:1.75}
.wrap{max-width:1180px;margin:0 auto;padding:0 28px}
.hero{position:relative;min-height:74vh;display:flex;align-items:flex-end;
 background:#000 center/cover no-repeat;}
.hero::after{content:"";position:absolute;inset:0;
 background:linear-gradient(180deg,rgba(12,11,9,.35) 0%,rgba(12,11,9,.92) 78%,var(--bg) 100%)}
.hero .in{position:relative;z-index:2;padding:0 28px 64px;max-width:1180px;margin:0 auto;width:100%}
.ch{font-family:Georgia,serif;letter-spacing:.42em;font-size:12px;color:var(--ac);margin:0 0 20px}
h1{font-weight:400;font-size:clamp(34px,6.2vw,74px);line-height:1.18;margin:0 0 22px;letter-spacing:.02em}
h1 em{font-style:normal;color:var(--ac)}
.lead{font-size:clamp(15px,1.7vw,19px);color:#ddd5c8;max-width:40em;margin:0}
.rule{height:1px;background:var(--line);margin:0}
.quote{font-size:clamp(20px,3vw,34px);line-height:1.6;color:var(--fg);
 border-left:3px solid var(--ac);padding:6px 0 6px 26px;margin:84px 0;max-width:24em;font-weight:400}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:56px 34px;padding:72px 0 96px}
.c{margin:0}
.th{display:block;aspect-ratio:16/9;overflow:hidden;background:#17150f;border:1px solid var(--line)}
.th img{width:100%;height:100%;object-fit:cover;display:block;filter:saturate(.92)}
.th:hover img{filter:none;transform:scale(1.03);transition:.4s}
.k{font-family:Georgia,serif;font-size:11px;letter-spacing:.3em;color:var(--ac);margin:16px 0 6px}
.c h3{font-size:21px;font-weight:400;margin:0 0 8px;line-height:1.35}
.cap{font-size:13.5px;color:var(--dim);margin:0 0 12px;min-height:1.2em}
.ls{margin:0 0 6px;font-size:12.5px;font-family:system-ui,sans-serif}
.l{color:var(--fg);text-decoration:none;border-bottom:1px solid var(--ac);margin-right:14px}
.l:hover{color:var(--ac)}
.src{margin:0;font-size:11px;font-family:system-ui,sans-serif}
.src a{color:#6d665c;text-decoration:none}
.src a:hover{color:var(--dim)}
footer{border-top:1px solid var(--line);padding:40px 0 80px;color:var(--dim);font-size:13px}
footer a{color:var(--fg)}
@media(max-width:600px){.grid{gap:44px 20px;padding:48px 0 72px}.wrap{padding:0 18px}.hero .in{padding:0 18px 44px}}
</style>
</head>
<body>
<header class="hero" style="background-image:url(https://i.ytimg.com/vi/@@HERO@@/@@HQ@@.jpg)">
  <div class="in">
    <p class="ch">01 / FUJI ROCK &rsquo;26</p>
    <h1>同じ名前の、<em>別人</em>を弾いた。<br>残った@@N@@組。</h1>
    <p class="lead">機械に名前を打ち込むと、たいてい有名なほうが1位に出る。IOと打てばブラジルのアンビエント奏者が、USと打てばNirvanaが出た。全部、来年ここに立つ本人ではない。公式のアーティストページを1組ずつ開いて、国とメンバーと公式リンクを突き合わせた。下にいるのは、その全員。</p>
  </div>
</header>
<div class="wrap">
  <p class="quote">名前が合っただけでは、本人ではない。</p>
  <div class="rule"></div>
  <div class="grid">
@@CARDS@@
  </div>
  <footer>
    サムネイルと動画は各アーティストの公式チャンネルのもの。国・メンバー・公式リンクの出どころは
    <a href="https://www.fujirockfestival.com/artist/index" target="_blank" rel="noopener">FUJI ROCK FESTIVAL &rsquo;26 公式アーティストページ</a>（2026-09-24 に確認）。<br>
    公式の動画が見つからなかった組と、同名が多すぎて本人を決めきれなかった組は、ここには出していない。
  </footer>
</div>
</body>
</html>
"""
    doc = (doc.replace("@@N@@", str(len(rows)))
              .replace("@@HERO@@", hero)
              .replace("@@HQ@@", heroimg)
              .replace("@@CARDS@@", "\n".join(cards)))
    with open(dest, "w", encoding="utf-8") as f:
        f.write(doc)
    return len(rows)


if __name__ == "__main__":
    if "--list" in sys.argv:
        for d in load():
            print(d["_vid"])
    elif "--build" in sys.argv:
        dest = sys.argv[sys.argv.index("--build") + 1]
        print("書きました %d組 → %s" % (build(dest), dest))
    else:
        print(__doc__)
