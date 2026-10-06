#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1162番【1枚】ラシコルの審査がいまどうなっているか（2026-09-26）

出すもの（全部実測。推測は書かない）
  ・いまの状態（審査中／公開された）
  ・審査リクエストからの経過日数
  ・最後に見に行った時刻
  ・LINE公式が言っている審査期間と、個別問い合わせが出せるようになる日

出力: 1162-rashikoru.html
戻し方: rm -f 1162-rashikoru.html tools/1162_page.py
"""
import io
import json
import os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(REPO, "1162-rashikoru.html")
JST = timezone(timedelta(hours=9))

TOIAWASE = ("https://contact-cc.line.me/detailId/11844?continue_without_login=true")


def yomu(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def rireki(n=12):
    out = []
    try:
        for line in io.open(os.path.join(ST, "1162_shinsa.jsonl"), encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        pass
    return out[-n:][::-1]


def main():
    now = datetime.now(JST)
    d = yomu(os.path.join(ST, "1162_shinsa.json"), {}) or {}

    state = d.get("state", "まだ一度も見に行っていない")
    koukai = d.get("koukai")
    keika = d.get("keikaNissu")
    mita = d.get("t", "—")
    if mita and mita != "—":
        try:
            mita = datetime.strptime(mita, "%Y-%m-%dT%H:%M:%S%z").astimezone(JST).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass

    iro = "ok" if koukai else ("ng" if koukai is False else "")
    nokori = "—"
    try:
        kanou = datetime.strptime(d.get("toiawaseKanoubi", ""), "%Y-%m-%d").replace(tzinfo=JST)
        nokori = "あと%d日（%s）" % ((kanou.date() - now.date()).days, d["toiawaseKanoubi"])
    except Exception:
        pass

    def box(m, a, h="", c=""):
        return ('<div class="b"><div class="m">%s</div><div class="a %s">%s</div>'
                '<div class="h">%s</div></div>' % (m, c, a, h))

    boxes = "\n".join([
        box("いまの状態", state, "LINE STOREの商品ページを実際に見に行った結果", iro),
        box("審査リクエストからの経過", ("%d日" % keika) if keika is not None else "—",
            "リクエスト日 %s" % d.get("shinseiDate", "—")),
        box("最後に見に行った時刻", mita, "3時間おきに自動で見に行っています"),
        box("個別問い合わせが出せるようになる日", nokori,
            "LINEの問い合わせフォームは「リクエストから1か月以上」でないと受け付けない"),
    ])

    rows = "".join(
        '<tr><td>%s</td><td>%s</td></tr>' % (
            (r.get("t", "")[:16].replace("T", " ")), r.get("state", ""))
        for r in rireki())

    html = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1162 ラシコルの審査</title>
<style>
body{background:#12100e;color:#efe9df;font-family:-apple-system,"Hiragino Sans",sans-serif;
margin:0;padding:24px;line-height:1.7}
h1{font-size:19px;margin:0 0 4px;letter-spacing:.04em}
.d{color:#8d857a;font-size:12px;margin-bottom:20px}
.g{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.b{background:#1c1916;border:1px solid #2e2924;border-radius:10px;padding:16px}
.m{font-size:12px;color:#9a9086;letter-spacing:.04em}
.a{font-size:22px;margin:6px 0 2px;font-weight:600}
.h{font-size:11px;color:#7d746a}
.ok{color:#7fc98a}.ng{color:#e8c46a}
h2{font-size:14px;margin:26px 0 8px;color:#c9bfb2;font-weight:600}
p{font-size:13px;color:#a79d92;margin:6px 0}
a{color:#8fb7d9}
table{border-collapse:collapse;font-size:12px;margin-top:6px}
td{border-bottom:1px solid #2a2520;padding:4px 14px 4px 0;color:#a79d92}
code{background:#241f1b;padding:1px 5px;border-radius:4px;font-size:12px}
</style>
<h1>ラシコルの審査（%(name)s ／ ID %(id)s）</h1>
<div class="d">%(now)s 時点・1162番</div>
<div class="g">
%(boxes)s
</div>

<h2>LINEが公式に言っていること（2026-09-26 実測）</h2>
<p>LINEの問い合わせフォームは、サービス=LINE Creators Market／カテゴリ=審査期間・リジェクト／
詳細=審査期間を教えてほしい を選ぶと、こう書かれた注意が出る：
<strong>「こちらからお問い合わせされても、審査状況の調査や審査期間の個別案内を行うことはできません。
審査完了まで1ヶ月ほどお時間がかかります。内容により1ヶ月以上かかる可能性もあり、
審査完了の順番が前後することがあります。」</strong></p>
<p>さらにフォーム自体が「リクエストから1か月以上経過していますか？」で分岐し、
「経過していない」を選ぶと以降の入力欄が閉じて送信できない。
つまり<strong>1か月を過ぎるまでは、そもそも個別の問い合わせを受け付けていない</strong>。</p>
<p>問い合わせ窓口（1か月経過後に使う）：<a href="%(toi)s">%(toi)s</a></p>

<h2>見に行った記録</h2>
<table>%(rows)s</table>

<h2>仕組み</h2>
<p>ログインが要るマイページは機械から見に行けないので、外から見える
LINE STOREの商品ページ（<a href="%(store)s">%(store)s</a>）を3時間おきに叩いている。
「アイテムが見つかりません」の間は審査中、商品名が出たら公開。
道具は <code>tools/1162_mihari.py</code> ／ <code>tools/1162_page.py</code>、
止めるときは <code>status/1162.stop</code> を置く。</p>
</html>""" % {
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "name": d.get("name", "Rashikoru the Mysterious Forest Beast"),
        "id": d.get("stickerId", "47502978"),
        "boxes": boxes,
        "rows": rows or "<tr><td>まだ記録なし</td><td></td></tr>",
        "toi": TOIAWASE,
        "store": d.get("storeUrl", "https://store.line.me/stickershop/product/47502978/ja"),
    }

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print(OUT)


if __name__ == "__main__":
    main()
