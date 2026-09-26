#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1165番：工場が本当に発車しているかを、数字3つだけで出す。

たまごさん（2026-09-27）:
  「クレジットがあるのに止まっている理由を教えてほしい。なんで止まってるの？」
  「使うペースが遅い。自発的に進められないの？」

進捗表に出すのはこの3つだけ。
  ① 直近24時間の発車本数
  ② 今走っている本数／上限（＋上限がその数になった理由）
  ③ 次に発車するタスク名

出力: /Users/mac/Desktop/tamago-shinchoku/1165-hassha.html
使い方: python3 tools/1165_page.py
"""
import io
import json
import os
import re
import time
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
OUT = os.path.join(REPO, "1165-hassha.html")
LOG = os.path.join(ST, "auto_launch.log")
HASSHA = re.compile(r"^(\d{4}-\d\d-\d\d) (\d\d:\d\d:\d\d) 🚀 自動発車 (\d+)番「(.*?)」")


def _load(p, d=None):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return d


MAC = (os.uname().sysname == "Darwin")


def _pid_alive(pid):
    # Macの上でなければ（Coworkのサンドボックス等）MacのPIDは見えない。
    # 見えないものを「死んでいる」と数えると走行0本と嘘をつくので、台帳の記録を信じる。
    if not MAC:
        return True
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def shuukei():
    now = datetime.datetime.now()
    kyou = now - datetime.timedelta(hours=24)
    hassha, saishin, jikanbetsu = [], None, {}
    try:
        for line in io.open(LOG, encoding="utf-8", errors="replace"):
            m = HASSHA.match(line)
            if not m:
                continue
            try:
                t = datetime.datetime.strptime(m.group(1) + " " + m.group(2),
                                               "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            saishin = (t, m.group(3), m.group(4), line.strip())
            if t >= kyou:
                hassha.append((t, m.group(3), m.group(4)))
                jikanbetsu[t.strftime("%m/%d %H時")] = jikanbetsu.get(
                    t.strftime("%m/%d %H時"), 0) + 1
    except Exception:
        pass

    q = _load(os.path.join(ST, "queue.json"), {}) or {}
    items = q.get("items") or []
    hashiru = [it for it in items
               if it.get("status") == "running" and it.get("pid")
               and _pid_alive(it.get("pid"))]
    machi = [it for it in items if (it.get("status") or "waiting") == "waiting"]
    machi.sort(key=lambda it: (int(it.get("p") or it.get("priority") or 9),
                              int(it.get("n") or 10 ** 9)))

    gate = _load(os.path.join(ST, "public", "hassha_gate.json"), {}) or {}
    cap = _load(os.path.join(ST, "launch_cap.json"), {}) or {}
    dj = _load(os.path.join(ST, "dojisu_jougen.json"), {}) or {}
    jitsu = dj.get("実測") or {}
    jougen = gate.get("maxParallel") or cap.get("cap") or 1

    return {
        "at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "hassha24": len(hassha),
        "jikanbetsu": jikanbetsu,
        "saishin": saishin,
        "hashiru": hashiru,
        "jougen": jougen,
        "tsugi": machi[:5],
        "machiKazu": len(machi),
        "konkyo": (gate.get("moto") or []) + (dj.get("根拠") or []),
        "hasshaOK": gate.get("hasshaOK"),
        "kagi": gate.get("why"),
        "jitsu": jitsu,
        "jitsuAt": dj.get("measuredAt"),
    }


CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0d0f12;color:#e8e6e1;
 font-family:"Hiragino Sans","Yu Gothic",system-ui,sans-serif;line-height:1.7}
.wrap{max-width:820px;margin:0 auto;padding:36px 20px 80px}
h1{font-size:22px;margin:0 0 4px;letter-spacing:.04em}
.at{color:#7d8590;font-size:13px;margin:0 0 28px}
.cards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.card{background:#15181d;border:1px solid #23272e;border-radius:14px;padding:18px 20px}
.lab{font-size:12px;color:#8b949e;letter-spacing:.08em;margin:0 0 6px}
.big{font-size:46px;font-weight:700;line-height:1.05;margin:0;
 font-variant-numeric:tabular-nums}
.big small{font-size:17px;font-weight:400;color:#8b949e;margin-left:4px}
.sub{font-size:13px;color:#9aa4ae;margin:8px 0 0}
.name{font-size:16px;font-weight:600;margin:6px 0 0}
h2{font-size:14px;color:#8b949e;letter-spacing:.08em;margin:36px 0 10px;
 border-top:1px solid #23272e;padding-top:18px}
ul{margin:0;padding-left:1.1em}
li{margin:0 0 6px;font-size:14px;color:#c9d1d9}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;color:#9aa4ae;
 background:#0a0c0f;border:1px solid #23272e;border-radius:10px;padding:12px 14px;
 overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.ok{color:#5ddba0}.ng{color:#ff7b72}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td{padding:6px 8px;border-bottom:1px solid #1d2126;vertical-align:top}
td:first-child{color:#7d8590;white-space:nowrap;width:1%}
.bar{display:inline-block;height:9px;background:#5ddba0;border-radius:5px;
 vertical-align:middle;margin-right:7px}
"""


def html(d):
    hashiru = d["hashiru"]
    tsugi = d["tsugi"]
    t1 = tsugi[0] if tsugi else None
    s = d["saishin"]
    j = d["jitsu"]
    rows = ""
    for k in sorted(d["jikanbetsu"], reverse=True)[:14]:
        v = d["jikanbetsu"][k]
        rows += ('<tr><td>%s</td><td><span class="bar" style="width:%dpx"></span>%d本</td></tr>'
                 % (k, min(360, v * 26), v))
    return """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>発車しているか｜1165</title><style>%s</style>
<div class="wrap">
<h1>工場は発車しているか</h1>
<p class="at">%s 時点で機械が数えた実測。人が書いた数字は1つも無い。</p>

<div class="cards">
  <div class="card"><p class="lab">① 直近24時間の発車</p>
    <p class="big">%d<small>本</small></p>
    <p class="sub">いちばん新しい発車：%s</p></div>
  <div class="card"><p class="lab">② 今走っている／上限</p>
    <p class="big">%d<small>／%d本</small></p>
    <p class="sub">発車の鍵：<span class="%s">%s</span></p></div>
  <div class="card"><p class="lab">③ 次に発車する</p>
    <p class="name">%s</p>
    <p class="sub">発車待ち %d件（この1本が空き枠に入る）</p></div>
</div>

<h2>上限がこの本数になった理由</h2>
<ul>%s</ul>

<h2>Macの実測（%s）</h2>
<div class="mono">空きメモリ %s GB ／ メモリ空き %s%% ／ 5分ロード比 %s ／ スワップ 残り%sGB・使用%sGB／全%sGB</div>

<h2>次に並んでいる5本</h2>
<table>%s</table>

<h2>時間ごとの発車本数</h2>
<table>%s</table>

<h2>いちばん新しい発車のログ1行（そのまま）</h2>
<div class="mono">%s</div>
</div></html>""" % (
        CSS, d["at"], d["hassha24"],
        (s[0].strftime("%m/%d %H:%M:%S") + "　" + s[1] + "番") if s else "記録なし",
        len(hashiru), d["jougen"],
        "ok" if d["hasshaOK"] else "ng", d["kagi"] or "不明",
        (t1.get("title") or "?")[:60] if t1 else "発車待ちが空",
        d["machiKazu"],
        "".join("<li>%s</li>" % r for r in d["konkyo"]) or "<li>記録なし</li>",
        d["jitsuAt"] or "?",
        j.get("memAvailGB"), j.get("memFreePct"),
        round(j["load5"] / j["cores"], 2) if (j.get("load5") and j.get("cores")) else "?",
        j.get("swapFreeGB"), j.get("swapUsedGB"), j.get("swapTotalGB"),
        "".join('<tr><td>%s番</td><td>%s</td></tr>'
                % (it.get("n"), (it.get("title") or "")[:70]) for it in tsugi) or
        "<tr><td>—</td><td>発車待ちが空</td></tr>",
        rows or "<tr><td>—</td><td>24時間で0本</td></tr>",
        (s[3] if s else "記録なし"),
    )


def main():
    d = shuukei()
    io.open(OUT, "w", encoding="utf-8").write(html(d))
    print("書いた: %s（直近24h %d本・走行%d本／上限%d本）"
          % (OUT, d["hassha24"], len(d["hashiru"]), d["jougen"]))


if __name__ == "__main__":
    main()
