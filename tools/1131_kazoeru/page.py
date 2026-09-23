#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1131番【1枚のページ】status/1131_kowareteru.json → 1131-kowareteru.html
たまごさん：「上に『今いくつ壊れているか』の数字だけ。種類ごとの内訳はその下。
　　　　　　　1件ずつの一覧は畳む。たまごさんは一覧を読まない。数字が減っていくのが見えればいい。」
使い方: python3 tools/1131_kazoeru/page.py
"""
import html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(REPO, "status", "1131_kowareteru.json")
OUT = os.path.join(REPO, "1131-kowareteru.html")
LOG = os.path.join(REPO, "status", "1131_suii.jsonl")

d = json.load(open(SRC, encoding="utf-8"))
e = html.escape

suii = []
if os.path.exists(LOG):
    for line in open(LOG, encoding="utf-8"):
        line = line.strip()
        if line:
            try: suii.append(json.loads(line))
            except Exception: pass
suii = suii[-14:]

def spark(rows):
    if len(rows) < 2: return ""
    vals = [r["total"] for r in rows]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    w, h = 560, 70
    pts = " ".join("%.1f,%.1f" % (i*w/(len(vals)-1), h - (v-lo)/rng*(h-8) - 4) for i, v in enumerate(vals))
    return ('<svg viewBox="0 0 %d %d" class="spark"><polyline points="%s"/></svg>'
            '<div class="sparklab"><span>%s</span><span>%s</span></div>' % (w, h, pts, e(rows[0]["asof"][:10]), e(rows[-1]["asof"][:10])))

LAB = {"flow_nobasis":"この流れで、もう一本","flow_missing":"この流れで（行き先なし）","era_nogate":"同じ時代の曲",
       "era_gap":"同じ時代（年差）","linked_nosource":"出典なしで繋いである","cover_candidate":"裏取り待ち",
       "no_video":"動画なし","no_year":"年なし","no_note":"紹介文が空","note_cut":"途中で切れている",
       "note_spotify":"Spotify表記","same_name":"同名アーティスト"}

rows = []
for s in d["shurui"]:
    if s["n"] == 0:
        rows.append('<tr class="zero"><td>%s</td><td class="n">0</td><td></td></tr>' % e(s["label"])); continue
    pg = ("<span class='sub'>ページ %s枚</span>" % f'{s["pages"]:,}') if s.get("pages") else ""
    rows.append('<tr><td>%s%s</td><td class="n">%s</td><td class="t">%s</td></tr>'
                % (e(s["label"]), pg, f'{s["n"]:,}', e(s["tani"])))

def block(key, title, items, fmt):
    if not items: return ""
    li = "".join("<li>%s</li>" % fmt(x) for x in items)
    return "<details><summary>%s（先頭 %d件）</summary><ul>%s</ul></details>" % (e(title), len(items), li)

S = d.get("samples", {})
details = "".join([
    block("flow_nobasis", "この流れで — 根拠なし", S.get("flow_nobasis", []),
          lambda x: "<b>%s</b> → %s <span class='sub'>棚：%s</span>" % (e(x["pageTitle"]), e(x["pick"]), e(x.get("shelf") or ""))),
    block("flow_missing", "この流れで — 行き先が存在しない", S.get("flow_missing", []),
          lambda x: "<b>%s</b> → %s" % (e(x["page"]), e(x["pick"]))),
    block("era_nogate", "同じ時代 — 年チェック素通り", S.get("era_nogate", []),
          lambda x: "<b>%s</b> → %s" % (e(x["pageTitle"]), e(x["pick"]))),
    block("linked_nosource", "出典なしで繋いである（まず外す）", S.get("linked_nosource", []),
          lambda x: "<b>%s</b> <span class='sub'>%s</span>" % (e(x["pageTitle"]), e(x.get("kind") or ""))),
    block("cover_candidate", "裏取り待ち（※曲名一致は証拠ではない）", S.get("cover_candidate", []),
          lambda x: "<b>%s</b> ／ 同題の古い曲：%s" % (e(x["pageTitle"]), e(x["maybe"]))),
    block("same_name", "同名アーティスト", S.get("same_name", []),
          lambda x: "<b>%s</b> … %s" % (e(x["name"]), e(", ".join(x["ids"])))),
])

sa = d.get("sa")
sa_html = ""
if sa is not None:
    k = d["kinou"]["total"]
    cls = "down" if sa < 0 else ("up" if sa > 0 else "flat")
    sa_html = '<p class="sa %s">前回 %s → 今日 %s（%s%s）</p>' % (cls, f"{k:,}", f'{d["total"]:,}', "+" if sa >= 0 else "", f"{sa:,}")

TPL = """<!DOCTYPE html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>いま壊れている数 — ごきげん補給所</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:#0e0c13;color:#efe9e0;font-family:-apple-system,"Hiragino Sans",sans-serif;padding:28px 18px 80px;line-height:1.7}
.wrap{max-width:720px;margin:0 auto}
.kicker{font-size:11px;letter-spacing:.28em;color:#8d8598;margin-bottom:26px}
.big{font-size:clamp(68px,20vw,124px);font-weight:800;line-height:.92;letter-spacing:-.03em;
 background:linear-gradient(180deg,#fff,#c9a86a);-webkit-background-clip:text;background-clip:text;color:transparent}
.unit{font-size:15px;color:#a49bb2;margin-top:10px}
.sa{margin-top:14px;font-size:14px;color:#a49bb2}
.sa.down{color:#7fd6a2}.sa.up{color:#e58b8b}
.spark{width:100%;height:70px;margin:22px 0 4px;overflow:visible}
.spark polyline{fill:none;stroke:#c9a86a;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.sparklab{display:flex;justify-content:space-between;font-size:10px;color:#6f6880;margin-bottom:28px}
h2{font-size:11px;letter-spacing:.24em;color:#8d8598;margin:34px 0 12px;font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
td{padding:11px 4px;border-bottom:1px solid #241f2e;vertical-align:baseline}
td.n{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;white-space:nowrap}
td.t{width:2.4em;color:#8d8598;font-size:12px;padding-left:6px}
tr.zero{color:#5b5470}tr.zero td.n{color:#5b5470;font-weight:400}
.sub{display:block;font-size:11px;color:#8d8598}
details{margin:10px 0;border:1px solid #241f2e;border-radius:10px;overflow:hidden}
summary{cursor:pointer;padding:12px 14px;font-size:13px;color:#c9a86a;background:#151221}
details ul{list-style:none;padding:6px 14px 14px;font-size:12.5px;max-height:380px;overflow:auto}
details li{padding:7px 0;border-bottom:1px solid #1d1928;color:#bdb5c8}
details li b{color:#efe9e0;font-weight:600}
footer{margin-top:46px;font-size:11.5px;color:#6f6880;line-height:1.9}
</style></head><body><div class="wrap">
<p class="kicker">ごきげん補給所 — いま壊れている数</p>
<div class="big">{{total}}</div>
<p class="unit">件（{{kind}}種類）· {{asof}} 時点 · 曲 {{flowCards}}枚／「この流れで」{{flowPages}}ページを機械で全件照合</p>
{{sa}}
{{spark}}
<h2>種類ごとの内訳</h2>
<table>{{rows}}</table>
<h2>1件ずつ（畳んであります）</h2>
{{details}}
<footer>
数え方：本番の src/lib をそのまま束ねて、本番と同じ getShelfPicks() / getEraHitsFallback() を全曲に対して実際に呼び、画面に出るものを再現して数えています。推測は入っていません。<br>
「裏取り待ち」は繋ぐ候補ではありません。曲名が一致しただけでは証拠になりません。出典が取れたものだけ tools/1131_tsunagi_kanmon.py を通して繋ぎます。<br>
数え直し：bash tools/1131_kazoeru/hakaru.sh
</footer>
</div></body></html>"""

VARS = {
 "total": f'{d["total"]:,}', "kind": str(d["shuruiCount"]), "asof": e(d["asof"]),
 "flowCards": f'{d["scope"]["flowCards"]:,}', "flowPages": f'{d["scope"]["flowPages"]:,}',
 "sa": sa_html, "spark": spark(suii), "rows": "".join(rows), "details": details}
for k, v in VARS.items():
    TPL = TPL.replace("{{%s}}" % k, v)
open(OUT, "w", encoding="utf-8").write(TPL)
print(OUT)
