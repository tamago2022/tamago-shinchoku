#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1149番【1枚の表】やりっぱなし4帳簿・型・門の死活・同時本数を1枚にする。

  python3 tools/1149_page.py     … 1149-yarippanashi.html を作り直す
戻し方（1行）: git checkout -- 1149-yarippanashi.html
"""
from __future__ import annotations
import html, json, os
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
JST = timezone(timedelta(hours=9))
E = lambda s: html.escape(str(s if s is not None else ""))


def jload(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return d


def jsonl(p):
    out = []
    if os.path.exists(p):
        for l in open(p, encoding="utf-8", errors="replace"):
            l = l.strip()
            if l:
                try:
                    out.append(json.loads(l))
                except Exception:
                    pass
    return out


def tbl(head, rows):
    if not rows:
        return '<p class="ok">0件。ここは今きれいです。</p>'
    h = "".join(f"<th>{E(c)}</th>" for c in head)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


def main():
    g = jload(os.path.join(ST, "1149", "genzai.json"))
    if not g:
        raise SystemExit("先に python3 tools/1149_daicho.py を走らせてください")
    d = jload(os.path.join(ST, "dojisu_jougen.json"), {})
    fk = jsonl(os.path.join(ST, "1149", "fukkyuu.jsonl"))
    y, k, m, kara = g["yari"], g["kata"], g["mon"], g["kara"]
    suii = g.get("suii", {})

    cards = ""
    for name in ("始めたまま", "確かめてない", "返ってこない", "直してない"):
        v = y["kensuu"][name]
        s = suii.get(name, {})
        han = s.get("判定", "")
        cls = "aka" if ("赤" in han or v > 0) else "ok"
        cards += (f'<div class="card {cls}"><div class="n">{v}</div><div class="lbl">{E(name)}</div>'
                  f'<div class="sub">前回 {E(s.get("前"))} → {E(han)}</div></div>')

    kata_rows = [[E(r["kata"]), f'<b>{r["narashi"]}</b>回', f'{r["shurui"]}種',
                  "<br>".join(E(x["nani"]) + f'（{x["kaisu"]}回）' for x in r["rei"])]
                 for r in k["kata"]]
    mon_rows = [[E(x["mon"]), x["tsuuka"], f'<b>{x["hajiki"]}</b>', E(x["saigo"]),
                 f'<span class="{"aka" if x["han"].startswith("赤") else "ok"}">{E(x["han"])}</span>']
                for x in m["mon"]]

    h1 = [[E(x["n"]), E(x["title"]), f'{x["keika_h"]}時間', E(x["state"]), E(x["iro"])] for x in y["hajimeta_mama"][:30]]
    h2 = [[E(x["n"]), E(x["title"]), f'{x["keika_h"]}時間',
           "<br>".join(f'<a href="{E(u)}">{E(u[:60])}</a>' for u in x["urls"])] for x in y["tashikametenai"][:30]]
    h3 = [[E(x["aite"]), E(x["nani"] or x["thread"]), f'{x["keika_h"]}時間', E(x["iro"])] for x in y["kaettekonai"][:30]]
    h4 = [[E(x["n"]), E(x["title"]), f'{x["keika_h"]}時間', E(x["shiteki"])] for x in y["naoshitenai"][:30]]

    fk_ok = sum(1 for r in fk if r.get("event") == "done")
    fk_re = sum(1 for r in fk if r.get("event") == "retry")
    fk_au = sum(1 for r in fk if r.get("event") == "auth_stop")
    fk_sk = sum(1 for r in fk if r.get("event") == "skipped")

    aka_html = "".join(f'<li>{E(a)}</li>' for a in kara["aka"]) or "<li>なし</li>"

    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1149番：やりっぱなしゼロ（4帳簿・型・門）</title>
<style>
:root{{color-scheme:light}}
body{{font-family:-apple-system,"Hiragino Sans",sans-serif;margin:0;background:#faf8f4;color:#1b1b1b;line-height:1.7}}
.wrap{{max-width:1000px;margin:0 auto;padding:20px 16px 80px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17px;margin:34px 0 8px;border-left:5px solid #c9a227;padding-left:10px}}
.lead{{color:#555;font-size:13px;margin:0 0 20px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.card{{background:#fff;border:1px solid #e3ddd0;border-radius:12px;padding:14px;text-align:center}}
.card.aka{{border-color:#d33;background:#fff6f6}}
.card .n{{font-size:34px;font-weight:800}} .card .lbl{{font-size:13px;font-weight:700}}
.card .sub{{font-size:11px;color:#777;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff;margin-top:6px}}
th,td{{border:1px solid #e5e0d4;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f3efe4;font-size:12px}}
.aka{{color:#c00;font-weight:700}} .ok{{color:#2a7}}
.box{{background:#fff;border:1px solid #e3ddd0;border-radius:12px;padding:12px 14px;font-size:13px}}
code{{background:#f0ece0;padding:1px 5px;border-radius:4px;font-size:12px}}
a{{color:#15c}}
</style></head><body><div class="wrap">
<h1>1149番：やりっぱなしゼロ</h1>
<p class="lead">更新 {E(g['at'][:16])}（機械が数えた実測。手で書いた数字は1つもありません）<br>
作り直し方：<code>python3 tools/1149_daicho.py --naosu &amp;&amp; python3 tools/1149_page.py</code></p>

<h2>やりっぱなし4帳簿（毎日数える。減っていなければ赤）</h2>
<div class="cards">{cards}</div>

<h2>最上位の赤：動いているのに何も取れていない</h2>
<div class="box">直近24時間 … 巡回 {kara['shuukai']}周／走行 {kara['soukou']}／<b>取れた {kara['toreta']}</b>
<ul>{aka_html}</ul>
<p style="color:#666;font-size:12px;margin:6px 0 0">※「取れた」は台帳の<b>差分</b>で数えます。累計を足すと12万件になり、赤が永久に出ません（4日半見逃した原因がこれ）。</p></div>

<h2>①始めたのに終わっていない（3時間で黄・6時間で赤）</h2>
{tbl(["番","件名","経過","状態","色"], h1)}

<h2>②出したのに確かめていない（→ 叩く仕事を自動で積む）</h2>
{tbl(["番","件名","出してから","URL"], h2)}

<h2>③頼んだのに返ってきていない（24時間で期限切れ＝赤）</h2>
{tbl(["相手","内容","経過","色"], h3)}

<h2>④見つけたのに直していない（→ 繰り上げ候補を自動で出す）</h2>
{tbl(["番","件名","経過","指摘"], h4)}

<h2>今日壊れたものの型（件数ではなく型で数える）</h2>
<div class="box">鳴った回数 <b>{k['narashiN']}</b>回 ／ 種類 {k['shuruiN']} ／ <b>型は {k['kataN']}</b>。
いちばん多い型：<b>{E(k['ichiban'])}</b><br>
<span style="color:#666;font-size:12px">2,800回鳴っていても、直す先は{k['kataN']}か所しかない。1件ずつ直すと2,800回の作業になる。</span></div>
{tbl(["型","鳴った回数","種類","例"], kata_rows)}

<h2>門の死活（弾き0が続く門＝素通り＝赤）</h2>
{tbl(["門の台帳","通過","弾き","最後に動いた","判定"], mon_rows)}

<h2>落ちても続きから（自動復旧の実測）</h2>
<div class="box">やり直し {fk_re}回／完走 {fk_ok}回／<b>認証で即停止 {fk_au}回</b>／停止中スキップ {fk_sk}回<br>
使い方：<code>tools/1149_fukkyuu.sh &lt;名前&gt; -- &lt;コマンド&gt;</code>　解除：<code>tools/1149_fukkyuu.sh --susumu</code><br>
<span style="color:#666;font-size:12px">認証で落ちたときだけ、やり直さずに止めます。やり直すと同じ失敗を1,403回積むからです。</span></div>

<h2>同時本数（機械が決めた上限）</h2>
<div class="box">上限 <b>{E(d.get('jougen'))}本</b>（基準{E(d.get('kijun'))}本）／負荷 {E(round(d.get('loadPct',0)))}%・swap {E(round(d.get('swapGB',0),1))}GB・落ちた率 {E(round((d.get('ochiRitsu') or 0)*100))}%
<ul>{"".join(f"<li>{E(r)}</li>" for r in d.get("riyuu", []))}</ul></div>

</div></body></html>"""
    out = os.path.join(REPO, "1149-yarippanashi.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print("書いた:", out, len(doc), "bytes")


if __name__ == "__main__":
    main()
