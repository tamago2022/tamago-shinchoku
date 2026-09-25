#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1145番【推移】間違いの総数を毎日1行ずつ記録して、減っているかを1枚で見せる。

たまごさん:「間違いが日ごとにどんどん少なくなってくればいいんだよ。」

読む:
  status/1140/kensa.json        全曲の型ごとの間違い（データを読んだぶん）
  status/1145/oembed.jsonl      動画1本ずつの実測（あるぶんだけ数える。推定しない）
  status/1145/page.jsonl        ページを実物で見た結果（あるぶんだけ）
書く:
  status/1145/suii.json         1日1行の推移
  1145-heru.html                折れ線1枚（減っていなければ赤）
"""
from __future__ import annotations
import io, json, os, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "status")
OUT = os.path.join(S, "1145")
SUII = os.path.join(OUT, "suii.json")
PAGE_HTML = os.path.join(ROOT, "1145-heru.html")



KYOUTSUU = "og-four-doors"


def score(p, songs_by_url, oe, dead):
    """ページ1件の赤を、保存した中身から付け直す（取り直さない）。
    ★生きているものを赤にしない。分からないものは赤にしない。"""
    aka = []
    if p.get("err") == "UnicodeEncodeError":
        return ["※古い取り方の失敗（数えない）"]
    if p.get("code") != 200:
        return ["200が返らない"]
    img = p.get("ogImage", "")
    if not img:
        aka.append("OG画像が無い")
    elif KYOUTSUU in img:
        aka.append("OG画像が共通画像（四つの扉）")
    elif p.get("ogImageCode") not in (None, 200):
        aka.append("OG画像が出ない")
    if not p.get("ogTitle"):
        aka.append("titleが空")
    if not p.get("ogDesc"):
        aka.append("コピーが空")
    elif not p.get("copyCore"):
        aka.append("コピーが空（曲名だけ）")
    r = songs_by_url.get(p["url"])
    if r is not None:
        raw = r.get("videos", {}).get("raw", []) or []
        if not raw:
            aka.append("動画が1本も無い")
        else:
            m = [v for v in raw if v in oe]
            if m and len([v for v in m if v in dead]) == len(raw):
                aka.append("動画が全部再生できない（実測）")
    return aka


def jsonl(p):
    if not os.path.exists(p):
        return []
    r = []
    for line in io.open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                r.append(json.loads(line))
            except Exception:
                pass
    return r


def tally():
    kensa = json.load(io.open(os.path.join(S, "1140", "kensa.json"), encoding="utf-8"))
    rows = kensa["rows"]
    ids = [x.strip() for x in io.open(os.path.join(S, "1140", "all_video_ids.txt"),
                                     encoding="utf-8") if x.strip()]
    oe = {r["id"]: r for r in jsonl(os.path.join(OUT, "oembed.jsonl")) if r.get("id")}
    dead = {k for k, v in oe.items() if v.get("v") not in ("alive", "unknown")}

    hidden = set()
    hp = os.path.join(S, "1140", "kakusu.txt")
    if os.path.exists(hp):
        for line in io.open(hp, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                hidden.add(line.split("\t")[0].strip())

    kata = {}
    for r in rows:
        for f in r["faults"]:
            kata[f] = kata.get(f, 0) + 1

    # 実測でわかったこと（推定しない）
    sub = {"完全": 0, "一部": 0, "未実測あり": 0}
    for r in rows:
        raw = r.get("videos", {}).get("raw", []) or []
        if not raw:
            continue
        m = [v for v in raw if v in oe]
        if len(m) < len(raw):
            sub["未実測あり"] += 1
        if not m:
            continue
        ng = [v for v in m if v in dead]
        if ng and len(ng) == len(raw):
            sub["完全"] += 1
        elif ng:
            sub["一部"] += 1

    pg_raw = jsonl(os.path.join(OUT, "page.jsonl"))
    pg = {}
    for p in pg_raw:                      # 同じURLは新しいほうを採る
        u = p.get("url")
        if u and (u not in pg or p.get("t", 0) >= pg[u].get("t", 0)):
            pg[u] = p
    by_url = {r["url"]: r for r in rows}
    for p in pg.values():
        p["赤"] = score(p, by_url, oe, dead)
    pg = [p for p in pg.values() if "※古い取り方の失敗（数えない）" not in p["赤"]]
    pg_aka = [p for p in pg if p.get("赤")]
    md5 = {}
    for p in pg:
        h = p.get("ogImageMd5")
        if h:
            md5.setdefault(h, []).append(p["url"])
    kyoutsuu = {h: len(v) for h, v in md5.items() if len(v) > 1}

    kata2 = dict(kata)
    kata2["saiseiDekinai(実測)"] = sub["完全"]
    machigai = sum(1 for r in rows if r["faults"])
    omote = sum(1 for r in rows if r["faults"] and r["key"] not in hidden)

    return {
        "日": time.strftime("%Y-%m-%d"),
        "時刻": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "全曲数": len(rows),
        "間違いがあった曲数": machigai,
        "表に出ている曲の間違い": omote,
        "隠してある曲": len(hidden),
        "型ごと": kata2,
        "動画IDの実数": len(ids),
        "実測した動画": len([v for v in ids if v in oe]),
        "未実測の動画": len([v for v in ids if v not in oe]),
        "実測で生きている": sum(1 for v in oe.values() if v.get("v") == "alive"),
        "実測で再生できない": len(dead),
        "実測で不明": sum(1 for v in oe.values() if v.get("v") == "unknown"),
        "実測の内訳": {k: sum(1 for x in oe.values() if x.get("v") == k)
                      for k in sorted({x.get("v") for x in oe.values()})},
        "動画が全部だめな曲(実測)": sub["完全"],
        "動画が一部だめな曲(実測)": sub["一部"],
        "ページを実物で見た": len(pg),
        "ページが赤だった": len(pg_aka),
        "ページの赤の内訳": _count([a for p in pg for a in p.get("赤", [])]),
        "OG画像が他と同じだったmd5の組数": len(kyoutsuu),
        "OG画像が他と同じ件数": sum(kyoutsuu.values()),
    }


def _count(xs):
    d = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


def main():
    os.makedirs(OUT, exist_ok=True)
    t = tally()
    hist = []
    if os.path.exists(SUII):
        try:
            hist = json.load(io.open(SUII, encoding="utf-8")).get("推移", [])
        except Exception:
            hist = []
    hist = [h for h in hist if h.get("日") != t["日"]] + [t]
    hist.sort(key=lambda h: h["日"])
    json.dump({"_これは何": "間違いの総数の毎日の推移。減っていなければ赤。",
               "最新": t, "推移": hist},
              io.open(SUII, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    io.open(PAGE_HTML, "w", encoding="utf-8").write(render(hist, t))
    print(json.dumps({k: v for k, v in t.items() if k != "型ごと"}, ensure_ascii=False))
    return 0


def render(hist, t):
    pts = [(h["日"], h["間違いがあった曲数"]) for h in hist]
    W, H, P = 900, 320, 56
    if len(pts) == 1:
        pts = pts + pts
    mx = max(v for _, v in pts) or 1
    mn = min(v for _, v in pts)
    lo = max(0, mn - (mx - mn) * 0.3 - 1)
    span = (mx - lo) or 1
    n = len(pts) - 1 or 1
    xy = [(P + i * (W - 2 * P) / n, H - P - (v - lo) / span * (H - 2 * P))
          for i, (_, v) in enumerate(pts)]
    poly = " ".join("%.1f,%.1f" % p for p in xy)
    heru = len(hist) >= 2 and hist[-1]["間違いがあった曲数"] < hist[-2]["間違いがあった曲数"]
    col = "#2f7d4f" if heru else "#b3261e"
    msg = ("昨日 %s件 → 今日 %s件（%s件 減った）" % (
        f"{hist[-2]['間違いがあった曲数']:,}", f"{hist[-1]['間違いがあった曲数']:,}",
        f"{hist[-2]['間違いがあった曲数']-hist[-1]['間違いがあった曲数']:,}")
        if len(hist) >= 2 and heru else
        ("昨日 %s件 → 今日 %s件。★減っていない" % (
            f"{hist[-2]['間違いがあった曲数']:,}", f"{hist[-1]['間違いがあった曲数']:,}")
         if len(hist) >= 2 else "今日が1日目。明日から増減が出る"))
    dots = "".join('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s"/>' % (x, y, col)
                   for x, y in xy)
    labs = "".join('<text x="%.1f" y="%d" text-anchor="middle" font-size="11" fill="#7a6a55">%s</text>'
                   % (xy[i][0], H - P + 20, pts[i][0][5:]) for i in range(len(pts)))
    vals = "".join('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" fill="%s">%s</text>'
                   % (x, y - 12, col, f"{pts[i][1]:,}") for i, (x, y) in enumerate(xy))
    kata = "".join("<tr><td>%s</td><td style='text-align:right'>%s</td></tr>"
                   % (k, f"{v:,}") for k, v in sorted(t["型ごと"].items(),
                                                      key=lambda kv: -kv[1]))
    naiyaku = "".join("<tr><td>%s</td><td style='text-align:right'>%s</td></tr>"
                      % (k, f"{v:,}") for k, v in t["実測の内訳"].items())
    aka = "".join("<tr><td>%s</td><td style='text-align:right'>%s</td></tr>"
                  % (k, f"{v:,}") for k, v in t["ページの赤の内訳"].items()) or \
        "<tr><td>赤なし</td><td style='text-align:right'>0</td></tr>"
    return """<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1145番 間違いは減っているか</title>
<style>
:root{--ink:#2b2317;--paper:#faf5ec;--line:#e3d9c6}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Hiragino Mincho ProN",serif;padding:28px 18px 60px}
.w{max-width:940px;margin:0 auto}
h1{font-size:26px;letter-spacing:.06em;margin:0 0 4px}
.sub{color:#7a6a55;font-size:13px;margin-bottom:22px}
.card{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px;margin:0 0 18px}
.msg{font-size:19px;font-weight:700;color:%s;margin:0 0 6px}
table{width:100%%;border-collapse:collapse;font-size:14px;
font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif}
td{padding:6px 8px;border-bottom:1px solid #f0eade}
h2{font-size:15px;letter-spacing:.08em;color:#7a6a55;margin:0 0 10px;
font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif}
.g{display:grid;grid-template-columns:1fr 1fr;gap:18px}
@media(max-width:700px){.g{grid-template-columns:1fr}}
.n{font-size:34px;font-weight:700}
.k{color:#7a6a55;font-size:12px;
font-family:-apple-system,"Hiragino Kaku Gothic ProN",sans-serif}
</style></head><body><div class="w">
<h1>間違いは減っているか</h1>
<div class="sub">1145番・実物で棚卸し。データを読むだけでなく、動画を1本ずつ叩き、ページを実際に取って見た結果。
最終更新 %s</div>

<div class="card"><p class="msg">%s</p>
<div class="k">うち、いま表に出ている曲の間違い <b>%s</b> 件（隠してある %s 曲は除いた）</div>
<svg viewBox="0 0 %d %d" width="100%%"><rect x="0" y="0" width="%d" height="%d" fill="none"/>
<polyline points="%s" fill="none" stroke="%s" stroke-width="2.5"/>%s%s%s</svg></div>

<div class="g">
<div class="card"><h2>動画を1本ずつ叩いた（oEmbed・0円）</h2>
<div class="n">%s <span class="k">/ %s 本</span></div>
<div class="k">未実測 %s 本 ★推定では数えない</div>
<table>%s</table>
<table><tr><td>動画が全部だめな曲（実測）</td><td style="text-align:right">%s</td></tr>
<tr><td>一部だめな曲（実測）</td><td style="text-align:right">%s</td></tr></table></div>

<div class="card"><h2>ページを実物で取って見た</h2>
<div class="n">%s <span class="k">件</span></div>
<div class="k">うち赤 %s 件 ／ OG画像が他と同じ %s 件</div>
<table>%s</table></div>
</div>

<div class="card"><h2>間違いの型ごと（全%s曲）</h2><table>%s</table></div>
<div class="sub">※ここに出る数字は、叩いた・取った分だけ。未実測は「未実測」と書く。</div>
</div></body></html>""" % (
        col, t["時刻"], msg,
        f'{t.get("表に出ている曲の間違い",0):,}', f'{t.get("隠してある曲",0):,}',
        W, H, W, H, poly, col, dots, labs, vals,
        f'{t["実測した動画"]:,}', f'{t["動画IDの実数"]:,}', f'{t["未実測の動画"]:,}',
        naiyaku, f'{t["動画が全部だめな曲(実測)"]:,}', f'{t["動画が一部だめな曲(実測)"]:,}',
        f'{t["ページを実物で見た"]:,}', f'{t["ページが赤だった"]:,}',
        f'{t["OG画像が他と同じ件数"]:,}', aka, f'{t["全曲数"]:,}', kata)


if __name__ == "__main__":
    raise SystemExit(main())
