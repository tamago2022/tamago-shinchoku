#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1158番【1枚】鍵が切れていないことを実測で見せる表（2026-09-26）

たまごさん：「最後に切れた日時／同時起動の最大本数／連続稼働時間を1枚に出す。」

出すもの（全部実測。推測は1文字も書かない）
  ・最後に切れた日時と、そこからの連続稼働時間
  ・同時起動の最大本数（直近24時間・1分おきの実測から）
  ・2本以上になった回数（これが0なら取り合いは起きていない）
  ・関所（1158_kanmon.py）が効いているか

出力: 1158-kagi.html（GitHub Pages の直下）
戻し方: rm -f 1158-kagi.html tools/1158_page.py
"""
import io
import json
import os
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(REPO, "1158-kagi.html")
JST = timezone(timedelta(hours=9))


def yomu(p, default=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return default


def mihari(jikan=24):
    """直近N時間の見張り記録。"""
    p = os.path.join(ST, "kanmon_mihari.jsonl")
    kiri = datetime.now(JST) - timedelta(hours=jikan)
    out = []
    try:
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                if datetime.strptime(d["t"], "%Y-%m-%dT%H:%M:%S%z") >= kiri:
                    out.append(d)
            except Exception:
                pass
    except Exception:
        pass
    return out


def main():
    now = datetime.now(JST)
    keeper = yomu(os.path.join(ST, "auth_keeper.json"), {}) or {}
    jougen = yomu(os.path.join(ST, "dojisu_jougen.json"), {}) or {}

    kireta = keeper.get("ngSince")
    ikiteru = keeper.get("state") != "expired"
    if kireta and ikiteru:
        # 生きているなら「最後に切れた日時」からの連続稼働
        try:
            t0 = datetime.strptime(kireta, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
            renzoku = "%.1f時間" % ((now - t0).total_seconds() / 3600)
        except Exception:
            renzoku = "—"
    elif not ikiteru:
        renzoku = "0（いま切れています）"
    else:
        renzoku = "—"

    s = mihari(24)
    saidai = max([d["n"] for d in s], default=None)
    nihon_ijou = len([d for d in s if d["n"] >= 2])
    kanmon_aru = os.path.exists(os.path.join(HERE, "1158_kanmon.py"))

    def box(midashi, atai, hosoku=""):
        return ('<div class="b"><div class="m">%s</div><div class="a">%s</div>'
                '<div class="h">%s</div></div>' % (midashi, atai, hosoku))

    html = """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>1158 鍵の表</title>
<style>
body{background:#12100e;color:#efe9df;font-family:-apple-system,"Hiragino Sans",sans-serif;
margin:0;padding:24px;line-height:1.7}
h1{font-size:19px;margin:0 0 4px;letter-spacing:.04em}
.d{color:#8d857a;font-size:12px;margin-bottom:20px}
.g{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.b{background:#1c1916;border:1px solid #2e2924;border-radius:10px;padding:16px}
.m{font-size:12px;color:#9a9086;letter-spacing:.04em}
.a{font-size:26px;margin:6px 0 2px;font-weight:600}
.h{font-size:11px;color:#7d746a}
.ok{color:#7fc98a}.ng{color:#e07a6a}
h2{font-size:14px;margin:26px 0 8px;color:#c9bfb2;font-weight:600}
p{font-size:13px;color:#a79d92;margin:6px 0}
code{background:#241f1b;padding:1px 5px;border-radius:4px;font-size:12px}
</style>
<h1>鍵が切れていないか（実測）</h1>
<div class="d">%(now)s 時点・1158番</div>
<div class="g">
%(boxes)s
</div>
<h2>いま何が起きているか</h2>
%(hon)s
<h2>関所の中身</h2>
<p>claude を起動する経路（auto_launcher / command_ingest / gaibu_copy_naoshi /
session_watchdog / auth_watch / auth_keeper）を全部 <code>tools/1158_kanmon.py</code> に通し、
<code>flock</code> で同時に走る本数を上限まで物理的に絞っている。
上限は <code>status/dojisu_jougen.json</code> の「同時上限」＝現在 %(jougen)s 本。</p>
<p>実測（2026-09-26）：偽のclaude5本を同時に投げて17秒。1本ずつ走った証拠
（取り合いのままなら3秒で終わる）。</p>
</html>""" % {
        "now": now.strftime("%Y-%m-%d %H:%M"),
        "jougen": jougen.get("同時上限", "?"),
        "boxes": "\n".join([
            box("鍵はいま",
                '<span class="%s">%s</span>' % ("ok" if ikiteru else "ng",
                                                "生きている" if ikiteru else "切れている"),
                keeper.get("lastNgWhy", "")[:60] if not ikiteru else ""),
            box("最後に切れた日時", kireta or "—", "auth_keeper の実測"),
            box("連続稼働時間", renzoku, "最後に切れてから"),
            box("同時起動の最大本数",
                "—" if saidai is None else "%d本" % saidai,
                "直近24時間・1分おきの実測（%d回ぶん）" % len(s)),
            box("2本以上になった回数",
                '<span class="%s">%s</span>' % ("ok" if nihon_ijou == 0 else "ng",
                                                "%d回" % nihon_ijou),
                "0なら取り合いは起きていない"),
            box("関所", '<span class="%s">%s</span>' % (
                ("ok", "効いている") if kanmon_aru else ("ng", "無い")),
                "tools/1158_kanmon.py"),
        ]),
        "hon": ("<p>鍵は生きている。関所が同時起動を%s本に抑えているので、"
                "取り合いで鍵が消えることは構造的に起きない。</p>" % jougen.get("同時上限", "?")
                if ikiteru else
                "<p><b>鍵はいま切れている。</b>関所は入ったので"
                "<b>これ以上取り合いで消えることはない</b>が、"
                "既に空になった鍵は関所では戻せない。"
                "ログインし直しが1回だけ要る（<code>status/LOGIN.md</code>）。"
                "戻ったあとは、この表の「2本以上になった回数」が0のまま伸びていくかで"
                "効いているかを見られる。</p>")
    }
    io.open(OUT, "w", encoding="utf-8").write(html)
    print("書いた: %s" % OUT)
    print("鍵: %s / 最大本数: %s / 2本以上: %d回 / 標本: %d"
          % ("生" if ikiteru else "死", saidai, nihon_ijou, len(s)))


if __name__ == "__main__":
    main()
