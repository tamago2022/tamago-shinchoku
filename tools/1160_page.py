#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1160番【調べものの棚】Gensparkが書いた答えを1枚のページに積む。

  status/1160/kotae/*.md  →  status/public/1160-shirabe.html
  （status/public/ は tools/pages_publish.sh が gh-pages へそのまま載せる＝mainを触らない）

  本番URL: https://tamago2022.github.io/tamago-shinchoku/status/public/1160-shirabe.html
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DIR = os.path.join(REPO, "status", "1160")
KOTAE = os.path.join(DIR, "kotae")
OUT = os.path.join(REPO, "status", "public", "1160-shirabe.html")


def souji(t):
    """Gensparkの返しに混ざる「会話の書庫」を落として、読み物だけ残す。"""
    t = re.sub(r"<compressed-history>.*?</compressed-history>", "", t, flags=re.S)
    t = re.sub(r"<turn\b.*?</turn>", "", t, flags=re.S)
    t = re.sub(r"<system-reminder>.*?</system-reminder>", "", t, flags=re.S)
    t = re.sub(r"This is a read-only archive of prior conversation\..*", "", t, flags=re.S)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def md2html(t):
    out = []
    in_ul = False
    for line in t.split("\n"):
        s = line.rstrip()
        # 先にリンクと強調
        def inline(x):
            x = html.escape(x)
            x = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", x)
            x = re.sub(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)",
                       r'<a href="\2" target="_blank" rel="noopener">\1</a>', x)
            x = re.sub(r"(?<!\")(?<!=)(https?://[^\s<\)\]\"']+)",
                       r'<a href="\1" target="_blank" rel="noopener">\1</a>', x)
            return x
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            if in_ul:
                out.append("</ul>"); in_ul = False
            n = min(len(m.group(1)) + 1, 5)
            out.append("<h%d>%s</h%d>" % (n, inline(m.group(2)), n))
            continue
        m = re.match(r"^\s*[-*・]\s+(.*)$", s)
        if m:
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append("<li>%s</li>" % inline(m.group(1)))
            continue
        if in_ul:
            out.append("</ul>"); in_ul = False
        if not s.strip():
            continue
        if re.match(r"^\s*(-{3,}|_{3,})\s*$", s):
            out.append("<hr>")
            continue
        out.append("<p>%s</p>" % inline(s))
    if in_ul:
        out.append("</ul>")
    return "\n".join(out)


CSS = """
:root{--ink:#16130f;--sub:#6b6257;--line:#e3ddd3;--bg:#faf7f2;--accent:#b5451b}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif;
  line-height:1.85;-webkit-text-size-adjust:100%}
.wrap{max-width:760px;margin:0 auto;padding:22px 18px 90px}
header{border-bottom:3px solid var(--ink);padding-bottom:14px;margin-bottom:8px}
h1{font-size:25px;line-height:1.35;margin:0 0 6px;letter-spacing:.01em}
.lead{color:var(--sub);font-size:13px;margin:0}
.meta{font-size:12px;color:var(--sub);margin:10px 0 0}
.badge{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:999px;
  padding:2px 9px;margin:0 6px 6px 0;background:#fff;color:var(--sub)}
.toc{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin:18px 0 26px}
.toc h2{font-size:13px;margin:0 0 8px;color:var(--sub);letter-spacing:.08em}
.toc ol{margin:0;padding-left:1.2em;font-size:15px}
.toc a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
article{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 18px;margin:0 0 28px}
article>.head{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:14px}
article h2{font-size:21px;margin:0 0 6px;line-height:1.4}
article .sub{font-size:12px;color:var(--sub);margin:0}
h3{font-size:18px;margin:26px 0 8px;padding-left:10px;border-left:4px solid var(--accent)}
h4{font-size:16px;margin:20px 0 6px;color:#2c2620}
h5{font-size:14px;margin:16px 0 6px;color:var(--sub)}
p{margin:0 0 12px;font-size:16px;word-break:break-word;overflow-wrap:anywhere}
ul{margin:0 0 14px;padding-left:1.25em}
li{margin:0 0 6px;font-size:16px;word-break:break-word;overflow-wrap:anywhere}
a{color:var(--accent);word-break:break-all}
hr{border:0;border-top:1px solid var(--line);margin:22px 0}
.machi{background:#fff;border:1px dashed var(--line);border-radius:12px;padding:14px 16px;font-size:14px;color:var(--sub)}
footer{margin-top:30px;font-size:12px;color:var(--sub);border-top:1px solid var(--line);padding-top:14px}
@media(max-width:480px){.wrap{padding:16px 13px 70px}h1{font-size:22px}article{padding:16px 14px}p,li{font-size:15.5px}}
"""


def wrap(title, inner, modoru=True):
    h = ["<!doctype html><html lang=ja><meta charset=utf-8>",
         '<meta name=viewport content="width=device-width,initial-scale=1">',
         "<title>%s</title>" % html.escape(title),
         "<style>%s</style>" % CSS, "<body><div class=wrap>"]
    if modoru:
        h.append('<p class=meta><a href="1160-shirabe.html">← 調べもの棚の目次へ</a></p>')
    h.append(inner)
    h.append('<footer>調べたのは Genspark（Deep Research）。出典URLつき。'
             '1本ずつ自動で流し、出典が少ない・失敗例が無い・レポート本文でない答えは'
             '突き返して書き直させています。<br>tools/1160_shirabe.py ／ tools/1160_page.py</footer>')
    h.append("</div></body></html>")
    return "\n".join(h)


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    rows = []
    q = os.path.join(DIR, "queue.jsonl")
    if os.path.exists(q):
        for line in io.open(q, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    j = {}
    p = os.path.join(DIR, "joukyou.json")
    if os.path.exists(p):
        try:
            j = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            pass

    arts = []
    for r in rows:
        f = os.path.join(KOTAE, "%s.md" % r["id"])
        if not os.path.exists(f):
            continue
        raw = io.open(f, encoding="utf-8").read()
        # 先頭の見出し＋メタ行は自分で作るので落とす
        body = raw.split("\n---\n", 1)[-1]
        body = souji(body)
        if len(body) < 500:
            continue
        urls = len(set(re.findall(r"https?://[^\s\)\]\"'>]+", body)))
        arts.append((r, md2html(body), urls, len(body)))

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    outdir = os.path.dirname(OUT)

    # ── 1本ずつの読み物ページ（重いので分ける） ──
    for r, body, urls, n in arts:
        t = r.get("title", r["id"])
        inner = ('<header><h1>%s</h1>'
                 '<p class=lead>Genspark（Deep Research）が調べて書いたもの</p>'
                 '<p class=meta>出典URL %d本 ／ %s字 ／ 投げた %s%s<br>'
                 '<a href="%s" target="_blank" rel="noopener">Gensparkのタスク画面（本人しか開けません）</a></p></header>'
                 % (html.escape(t), urls, format(n, ","), html.escape(str(r.get("submitted_at", ""))),
                    "／ 突き返し %d回" % r.get("sashimodoshi", 0) if r.get("sashimodoshi") else "",
                    html.escape(str(r.get("task_url", "")))))
        inner += "<article>%s</article>" % body
        p = os.path.join(outdir, "1160-%s.html" % r["id"])
        with io.open(p, "w", encoding="utf-8") as f:
            f.write(wrap(t, inner))
        print("書いた %s（%dバイト）" % (p, os.path.getsize(p)))

    # ── 目次（これが本番URL1枚） ──
    h = ["<header><h1>人を挟まずに回す仕組み<br>世界の実装と、失敗の記録</h1>",
         "<p class=lead>Genspark（Deep Research）が調べて書いたもの。全文に出典URLつき。</p>",
         "<p class=meta>更新 %s ／ 取れた %d本・走っている %d本・順番待ち %d本 ／ 残クレジット %s（Deep Research は消費0で実測）</p></header>"
         % (now, j.get("取れた", 0), j.get("走っている", 0), j.get("順番待ち", 0), html.escape(str(j.get("zan", "?"))))]
    for r, body, urls, n in arts:
        midashi = re.findall(r"<h3>(.*?)</h3>", body)[:4]
        h.append('<article><div class=head><h2><a href="1160-%s.html" style="color:inherit;text-decoration:none">%s</a></h2>'
                 '<p class=sub>出典URL %d本 ／ %s字%s</p></div>'
                 % (r["id"], html.escape(r.get("title", r["id"])), urls, format(n, ","),
                    "／ 突き返し %d回" % r.get("sashimodoshi", 0) if r.get("sashimodoshi") else ""))
        if midashi:
            h.append("<p>" + " ／ ".join(re.sub(r"<[^>]+>", "", m)[:40] for m in midashi) + "</p>")
        h.append('<p><a href="1160-%s.html">→ 全文を読む</a></p></article>' % r["id"])

    machi = [r for r in rows if r.get("state") in ("走っている", "順番待ち")]
    if machi:
        h.append("<div class=machi><strong>いま調べさせているもの</strong><br>")
        for r in machi:
            h.append("%s <span class=badge>%s</span><br>" %
                     (html.escape(r.get("title", r["id"])), html.escape(r.get("state", ""))))
        h.append("取れた順にこの棚へ積まれます。</div>")

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write(wrap("調べもの棚｜人を挟まずに回す仕組み", "\n".join(h), modoru=False))
    print("書いた %s（%d本・%dバイト）" % (OUT, len(arts), os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
