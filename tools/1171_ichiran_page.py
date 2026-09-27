#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1171番【秋の箱・1枚の一覧】予約10本を、時刻／邦洋／本文／ページURL／動画の有無で出す。

たまごさんの言葉（2026-09-27・原文）:
  「今の予約10本の中身を全部出す（時刻／邦洋／本文／ページURL／動画の有無）。
    1枚のHTMLで見られるようにして進捗表に載せる。」
  「動画の無いもの、リンクの切れているものを赤で出す。」

★Bufferを1回も叩かない。読むのは手元の控えだけ（＝0叩き）。
    status/buffer_queue/.yoyaku.json          予約の控え
    status/oneshot/data/1171_kenpin_*.json    曲ページを実際に開いて数えた結果

赤にする条件（1つでも当たったら赤）:
  ・ページが開かない（HTTPが200でない）
  ・本人の動画が無い／小さい（横幅500px未満）
  ・関連が4本未満
  ・本文の最後の行がリンクになっていない
  ・枠と言語が合っていない（朝09:00＝邦楽／夜21:00＝洋楽）

出す: status/public/1171_ichiran.html
使い方: python3 tools/1171_ichiran_page.py
"""
import datetime
import html as H
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = datetime.timezone(datetime.timedelta(hours=9))
YOYAKU = os.path.join(REPO, "status", "buffer_queue", ".yoyaku.json")
KENPIN = [os.path.join(REPO, "status", "oneshot", "data", "1171_kenpin_a.json"),
          os.path.join(REPO, "status", "oneshot", "data", "1171_kenpin_b.json")]
WAKU = os.path.join(REPO, "status", "buffer_queue", ".waku.json")
OUT = os.path.join(REPO, "status", "public", "1171_ichiran.html")
MAIN_HABA = 500
KANREN_SAITEI = 4
e = H.escape


def jload(p, d):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


def nihongo_ga_aru(s):
    for c in s or "":
        o = ord(c)
        if (0x3040 <= o <= 0x30FF) or (0x4E00 <= o <= 0x9FFF) \
           or (0x3400 <= o <= 0x4DBF) or (0xFF66 <= o <= 0xFF9D):
            return True
    return False


def kotoba(text):
    for ln in (text or "").split("\n"):
        if "—" in ln or "–" in ln:
            return "ja" if nihongo_ga_aru(ln) else "en"
    return "ja" if nihongo_ga_aru(text or "") else "en"


def midashi(text):
    for ln in (text or "").split("\n"):
        if "—" in ln or "–" in ln:
            return ln.strip()
    return (text or "").split("\n")[0][:70]


def url_wo_hirou(text):
    m = re.findall(r'https?://\S+', text or "")
    return m[-1] if m else ""


def kenpin_yomu():
    """URL → 実測した数字。"""
    out = {}
    for p in KENPIN:
        d = jload(p, None)
        if d is None:
            continue
        rows = d.get("rows") if isinstance(d, dict) else d
        for r in rows or []:
            k = r.get("data") or {}
            v = k.get("videos") or []
            out[(r.get("url") or "").strip()] = {
                "http": r.get("status") or r.get("http"),
                "h1": k.get("h1") or "",
                "kanren": int(k.get("kanren_honsuu") or 0),
                "main_w": int((v[0].get("w") or 0)) if v else 0,
                "main": ("%sx%s" % (v[0].get("w"), v[0].get("h"))) if v else "",
                "videos": len(v),
            }
    return out


def shiraberu(p, kp):
    text = p.get("text") or ""
    due = p.get("due") or ""
    lang = kotoba(text)
    url = url_wo_hirou(text)
    k = kp.get(url)
    aka = []
    if k is None:
        aka.append("ページをまだ数えていない")
    else:
        if int(k.get("http") or 0) != 200:
            aka.append("ページが開かない（HTTP %s）" % k.get("http"))
        if k.get("main_w", 0) < MAIN_HABA:
            aka.append("本人の動画が無い"
                       if not k.get("videos") else
                       "本人の動画が小さい（%s）" % (k.get("main") or "?"))
        if k.get("kanren", 0) < KANREN_SAITEI:
            aka.append("関連が %d 本（最低 %d 本）" % (k.get("kanren", 0), KANREN_SAITEI))
        if not k.get("h1"):
            aka.append("見出しが出ていない＝未完成")
    if not url:
        aka.append("本文にリンクが無い")
    else:
        lines = [x for x in text.split("\n") if x.strip()]
        if not lines or "http" not in lines[-1]:
            aka.append("リンクが本文のいちばん最後に無い")
    hhmm = due[-5:] if len(due) >= 5 else ""
    if hhmm == "09:00" and lang != "ja":
        aka.append("朝の枠なのに洋楽")
    elif hhmm == "21:00" and lang != "en":
        aka.append("夜の枠なのに邦楽")
    elif hhmm and hhmm not in ("09:00", "21:00"):
        aka.append("枠の時刻が 09:00／21:00 でない（%s）" % hhmm)
    return {"due": due, "lang": lang, "text": text, "url": url,
            "midashi": midashi(text), "kenpin": k, "aka": aka}


def main():
    y = jload(YOYAKU, {})
    ps = y.get("yoyaku") or []
    kp = kenpin_yomu()
    rows = [shiraberu(p, kp) for p in ps]
    rows.sort(key=lambda r: r["due"])
    ng = sum(1 for r in rows if r["aka"])
    w = jload(WAKU, {})

    li = []
    for i, r in enumerate(rows, 1):
        k = r["kenpin"] or {}
        douga = ('<b class="ok">動画 %s</b>' % e(k.get("main") or "")
                 if k.get("main_w", 0) >= MAIN_HABA else
                 '<b class="ng">動画なし</b>' if k else '<b class="q">未測定</b>')
        kanren = ('<b class="%s">関連 %d</b>'
                  % ("ok" if k.get("kanren", 0) >= KANREN_SAITEI else "ng",
                     k.get("kanren", 0))) if k else ''
        riyuu = ('<p class="aka">▲ %s</p>' % e("／".join(r["aka"]))) if r["aka"] else ''
        li.append(
            '<li class="%s"><div class="hd"><span class="no">%02d</span>'
            '<span class="due">%s</span><span class="lang %s">%s</span>'
            '%s%s</div><p class="mi">%s</p>%s'
            '<pre>%s</pre>'
            '<p class="u">%s</p></li>'
            % ("bad" if r["aka"] else "good", i, e(r["due"]),
               r["lang"], "邦楽" if r["lang"] == "ja" else "洋楽",
               douga, kanren, e(r["midashi"]), riyuu, e(r["text"]),
               ('<a href="%s">%s</a>' % (e(r["url"]), e(r["url"]))
                if r["url"] else '<span class="ng">リンクなし</span>')))

    doc = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>秋の箱・予約の中身</title><style>
body{margin:0;padding:18px 14px 70px;background:#14120f;color:#efe9de;
 font:15px/1.7 -apple-system,"Hiragino Sans",sans-serif;max-width:760px;margin-inline:auto}
h1{font-size:19px;margin:0 0 2px}
.at{color:#8e857a;font-size:12.5px;margin:0 0 6px}
.sum{border:1px solid #3a342c;border-radius:8px;padding:10px 12px;margin:0 0 18px;font-size:13.5px}
.sum b.ng{color:#ff7a5c}
ol{list-style:none;margin:0;padding:0}
li{border:1px solid #2e2a24;border-left:4px solid #3f7d4f;border-radius:8px;
 padding:10px 12px;margin:0 0 12px;background:#1b1813}
li.bad{border-left-color:#d8452c;background:#221613}
.hd{display:flex;flex-wrap:wrap;gap:6px 9px;align-items:center;font-size:12.5px}
.no{color:#8e857a;font-variant-numeric:tabular-nums}
.due{font-variant-numeric:tabular-nums;color:#e8dcc4;font-weight:600}
.lang{border:1px solid #4a4238;border-radius:99px;padding:0 8px}
.lang.ja{color:#ffd9a0}.lang.en{color:#a8d8ff}
b.ok{color:#7fc18d;font-weight:600}
b.ng{color:#ff7a5c;font-weight:600}
b.q{color:#9a9287;font-weight:600}
.mi{margin:7px 0 0;font-size:15.5px}
.aka{margin:5px 0 0;color:#ff7a5c;font-size:13px}
pre{white-space:pre-wrap;word-break:break-word;margin:8px 0 0;padding:8px 10px;
 background:#100e0c;border-radius:6px;color:#c9c1b4;font:12.5px/1.6 ui-monospace,monospace}
.u{margin:7px 0 0;font-size:12px;word-break:break-all}
a{color:#7fb0e0}
</style></head><body>
<h1>秋の箱・予約の中身</h1>
<p class="at">%(at)s 時点。★Bufferは1回も叩いていません。手元の控えを読んで描いた1枚です。</p>
<div class="sum">予約 %(n)d 本／そのうち <b class="ng">直すところがあるもの %(ng)d 本</b><br>
決まり：朝 09:00 ＝ 邦楽／夜 21:00 ＝ 洋楽。関連は最低4本。本人の動画は必須。<br>
Bufferの枠：%(waku)s</div>
<ol>%(body)s</ol></body></html>""" % {
        "at": e(datetime.datetime.now(JST).strftime("%F %H:%M")),
        "n": len(rows), "ng": ng, "body": "".join(li) or "<li>控えが空です</li>",
        "waku": e("使い切り。%s に戻る（remaining=%s）"
                  % (w.get("modoru") or "?", w.get("remaining"))
                  if w.get("modoru") else "不明")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(doc)
    print("書いた: %s（%d 本／赤 %d 本）" % (OUT, len(rows), ng))
    for r in rows:
        if r["aka"]:
            print("  ▲ %s %s ／ %s" % (r["due"], r["midashi"], "／".join(r["aka"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
