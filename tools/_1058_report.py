#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1058番【Gensparkが調べた証拠の紙】

たまごさん（2026-09-24）：
  「Gensparkと繋がってるっていうのを、俺はまだ体感してない。
    Gensparkのレポート、『あいつが調べましたよ』っていうのを証明して。」

載せるのは4つだけ：
  ① Gensparkが返してきた**生の答え**（こちらで書き直さない）
  ② 調べた日時と、減ったクレジット（＝あいつが動いた証拠）
  ③ 返ってきたURLを tools/yomu.py で叩いた結果（200かどうか）
  ④ 中身：棚にあるのにカバーと繋がっていない組が何件か

★要約だけにしない。★確かめていないことを書かない。
"""
import html
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "gsk_daicho.jsonl")
TSUNAGI = os.path.join(REPO, "status", "gsk", "tsunagatte_nai.json")
OUT = os.path.join(REPO, "share", "check", "1058-genspark-shoko.html")
CHECK_N = 10   # 叩いて200を確かめるURLの本数（★叩きすぎない）


def rows():
    out = []
    if not os.path.exists(DAICHO):
        return out
    with open(DAICHO, encoding="utf-8") as f:
        for line in f:
            try:
                g = json.loads(line)
            except Exception:
                continue
            if g.get("bangou") == 7:
                out.append(g)
    return out


def kotae_urls(rel):
    p = os.path.join(REPO, rel or "")
    if not rel or not os.path.exists(p):
        return [], ""
    raw = open(p, encoding="utf-8").read()
    try:
        d = json.loads(raw)
        res = d.get("data", {}).get("organic_results", []) or []
    except Exception:
        res = []
    return [{"title": r.get("title", ""), "link": r.get("link", ""), "snippet": r.get("snippet", "")}
            for r in res[:5]], raw


def tataku(url):
    """tools/yomu.py で叩く。★読めたかどうかだけ。中身は載せない。"""
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "yomu.py"), url],
                           capture_output=True, text=True, timeout=90)
        try:
            d = json.loads(r.stdout)
        except Exception:
            return {"ok": r.returncode == 0, "code": None, "why": (r.stderr or "")[:120]}
        code = d.get("code") or d.get("httpCode") or d.get("status")
        return {"ok": bool(d.get("ok")) or code == 200, "code": code,
                "why": (d.get("error") or d.get("why") or "")[:120],
                "yomite": d.get("読み手") or d.get("reader") or ""}
    except Exception as e:
        return {"ok": False, "code": None, "why": "%s" % type(e).__name__}


def main():
    gs = rows()
    tn = {}
    if os.path.exists(TSUNAGI):
        tn = json.load(open(TSUNAGI, encoding="utf-8"))

    tataita = 0
    blocks = []
    for g in gs:
        urls, raw = kotae_urls(g.get("答え"))
        checks = []
        for u in urls[:2]:
            if not u["link"]:
                continue
            if tataita < CHECK_N:
                c = tataku(u["link"])
                tataita += 1
            else:
                c = {"ok": None, "code": None, "why": "今回は叩いていません"}
            checks.append((u, c))
        blocks.append({"g": g, "urls": urls, "raw": raw, "checks": checks})

    zen = gs[0].get("残クレジット") if gs else None
    ato = gs[-1].get("残クレジット") if gs else None
    tsukatta = round(sum(float(g.get("使ったクレジット") or 0) for g in gs), 3)

    def esc(x):
        return html.escape(str(x))

    body = []
    for b in blocks:
        g = b["g"]
        ul = "".join(
            "<li><a href=\"%s\" target=_blank rel=noopener>%s</a><br><span class=t>%s</span>%s</li>" % (
                esc(u["link"]), esc(u["title"][:110] or u["link"]), esc(u["snippet"][:160]),
                ("<span class=%s>%s</span>" % (
                    "ok" if c.get("ok") else "ng",
                    ("yomu.py 200 ✓" if c.get("ok") else "yomu.py %s ✗ %s" % (c.get("code"), c.get("why")))))
                if c else "")
            for u, c in b["checks"])
        nokori = "".join("<li><a href=\"%s\" target=_blank rel=noopener>%s</a></li>" % (esc(u["link"]), esc(u["title"][:110]))
                         for u in b["urls"][len(b["checks"]):])
        body.append("""<details class=card><summary><b>%s</b>
<span class=meta>%s ／ 使ったクレジット %s ／ 残 %s</span></summary>
<div class=q>投げた問い：<code>%s</code></div>
<ul class=links>%s%s</ul>
<div class=t>▼ Gensparkが返してきた生の答え（こちらで一切書き直していません）</div>
<pre>%s</pre></details>""" % (
            esc(g.get("対象") or g.get("toi")), esc(g.get("at")),
            esc(g.get("使ったクレジット")), esc(g.get("残クレジット")),
            esc(g.get("toi")), ul, nokori, esc((b["raw"] or "")[:6000])))

    page = """<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Gensparkが調べた証拠｜1058</title>
<style>
body{font:15px/1.75 -apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;margin:0;padding:18px 16px 60px;background:#faf8f4;color:#221}
h1{font-size:19px;margin:0 0 2px}
.sub{color:#776;font-size:12px;margin:0 0 14px}
.box{background:#fff;border:1px solid #e8e2d6;border-radius:12px;padding:14px;margin:0 0 14px}
.big{font-size:28px;font-weight:700;letter-spacing:-.02em}
.big small{font-size:12px;font-weight:400;color:#887}
.card{background:#fff;border:1px solid #e8e2d6;border-radius:12px;padding:12px 14px;margin:0 0 10px}
summary{cursor:pointer;font-size:14px}
.meta{display:block;color:#887;font-size:11px;margin-top:3px}
.q{font-size:12px;color:#665;margin:10px 0}
code{background:#f3efe6;padding:1px 5px;border-radius:4px;font-size:11px;word-break:break-all}
ul.links{padding-left:18px;margin:8px 0;font-size:13px}
ul.links li{margin-bottom:8px}
.t{color:#887;font-size:11px}
.ok{display:inline-block;margin-left:6px;color:#27632a;font-size:11px;font-weight:600}
.ng{display:inline-block;margin-left:6px;color:#a33;font-size:11px;font-weight:600}
pre{background:#12100d;color:#d8d2c4;padding:10px;border-radius:8px;overflow:auto;font-size:10.5px;line-height:1.5;max-height:340px;white-space:pre-wrap;word-break:break-all}
a{color:#1a5fb4}
</style>
<h1>Gensparkが調べた証拠</h1>
<p class=sub>1058号／%s 時点。<b>生の答えをそのまま載せています。</b>こちらの要約ではありません。</p>

<div class=box>
  <div class=big>%s <small>→</small> %s <small>クレジット</small></div>
  <div class=t>★これが「あいつが動いた」証拠。この %s 件で <b>%s クレジット</b>減りました。
  残クレジットは <code>gsk me</code> の実測値（これ自体は0クレジット）。2026-10-04でプラン終了・繰り越しなし。</div>
</div>

<div class=box>
  <div class=big>%s <small>組</small></div>
  <div class=t>棚（アーティスト%s・曲%s）の中で、<b>同じ曲が2人以上いるのに互いに繋がっていない</b>組。
  ★候補であって断定ではありません。同じ曲名でも別の曲のことがあります。<b>採否はたまごさん。</b>本番にはまだ繋いでいません。
  1曲につき最大3件まで絞ってあります。<br>→ <a href="./1058-tsunagatte-nai.html">繋がっていない組の一覧を見る</a></div>
</div>

<div class=box>
  <div class=t>下の%s件が、今回Gensparkに投げたぶん。開くと<b>生の答え</b>が出ます。
  URLは <code>tools/yomu.py</code> で実際に叩いて、200かどうかを書いてあります。</div>
</div>
%s
""" % (
        html.escape(gs[-1].get("at") if gs else "-"),
        html.escape(str(zen)), html.escape(str(ato)), len(gs), html.escape(str(tsukatta)),
        html.escape(str(tn.get("繋がっていない組", "-"))),
        html.escape(str(tn.get("棚のアーティスト数", "-"))), html.escape(str(tn.get("棚の曲数", "-"))),
        len(gs), "".join(body))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(page)
    print(json.dumps({"件数": len(gs), "前": zen, "後": ato, "使った": tsukatta,
                      "叩いたURL": tataita, "紙": os.path.relpath(OUT, REPO)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
