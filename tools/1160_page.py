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
    h = ["<!doctype html><html lang=ja><meta charset=utf-8>",
         '<meta name=viewport content="width=device-width,initial-scale=1">',
         "<title>調べもの棚｜ループエンジニアリングと無人運用</title>",
         "<style>%s</style>" % CSS, "<body><div class=wrap>",
         "<header><h1>人を挟まずに回す仕組み<br>世界の実装と、失敗の記録</h1>",
         "<p class=lead>Genspark（Deep Research）が調べて書いたもの。出典URLつき。</p>",
         "<p class=meta>更新 %s ／ 取れた %d本・走っている %d本・順番待ち %d本</p></header>"
         % (now, j.get("取れた", 0), j.get("走っている", 0), j.get("順番待ち", 0))]

    if arts:
        h.append("<div class=toc><h2>目次</h2><ol>")
        for r, _, _, _ in arts:
            h.append('<li><a href="#%s">%s</a></li>' % (r["id"], html.escape(r.get("title", r["id"]))))
        h.append("</ol></div>")

    for r, body, urls, n in arts:
        h.append('<article id="%s"><div class=head><h2>%s</h2>' % (r["id"], html.escape(r.get("title", r["id"]))))
        h.append('<p class=sub>Genspark Deep Research ／ 投げた %s ／ 出典URL %d本 ／ %s字'
                 '%s</p></div>' % (html.escape(str(r.get("submitted_at", ""))), urls, format(n, ","),
                                   "（突き返し %d回）" % r.get("sashimodoshi", 0) if r.get("sashimodoshi") else ""))
        h.append(body)
        h.append("</article>")

    machi = [r for r in rows if r.get("state") in ("走っている", "順番待ち")]
    if machi:
        h.append("<div class=machi><strong>いま調べさせているもの</strong><br>")
        for r in machi:
            h.append("%s <span class=badge>%s</span><br>" %
                     (html.escape(r.get("title", r["id"])), html.escape(r.get("state", ""))))
        h.append("答えが取れた順にこのページへ積まれます。</div>")

    h.append("<footer>調べたのは Genspark（Deep Research）。"
             "1本ずつ自動で流し、出典URLが少ない・失敗例が無い答えは突き返して書き直させています。<br>"
             "残クレジット %s ／ このページは自動更新（tools/1160_shirabe.py・tools/1160_page.py）</footer>"
             % html.escape(str(j.get("zan", "?"))))
    h.append("</div></body></html>")

    with io.open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(h))
    print("書いた %s（%d本・%dバイト）" % (OUT, len(arts), os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
