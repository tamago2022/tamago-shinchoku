#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部AIの台帳（投げっぱなしをゼロにする道具）

━━ なぜ作ったか（2026-09-25・たまごさん原文）━━
  「ジェンスパークどうした？あいつ、あいつどうなん？ページ作ったの？ちゃんと。
    言いっぱなしで逃がさないと。」
  「投げて返ってきたのかどうかなども、全部記録しておいて。」

━━ 何をする道具か ━━
  ① 外部AI（Genspark / Devin / Jules / ChatGPT(Codex) / Grok / Lovable …）に
     何かを投げたら1行ずつ足す。
  ② 期限を過ぎて返ってきていないものを★赤で出す。
  ③ 「投げた数 > 0 なのに返ってきた数 = 0」を毎回数字で出す。
     （feedback_running_but_blind_is_the_worst_failure）

━━ 台帳の1行（status/gaibu_ai/daicho.jsonl）━━
  id        … 通し番号の文字列
  at        … 投げた日時（JST, ISO）
  ai        … 誰に（genspark / devin / jules / codex / grok / lovable …）
  what      … 何を頼んだか（1行）
  kigen     … 期限（JST, ISO）
  kaeri     … 返ってきたか: "yes" / "no" / "partial"
  kaeri_at  … 返ってきた日時（無ければ null）
  url       … 成果物のURL（無ければ null）
  kane      … かかった額（文字列。実測なら "実測 0credit" のように書く）
  memo      … 補足

━━ 使い方 ━━
  python3 tools/gaibu_ai.py --nage --ai genspark --what "..." --kigen 2026-09-25T21:00 --kane "実測0credit"
  python3 tools/gaibu_ai.py --kaeri <id> --url <URL> [--kane "..."]
  python3 tools/gaibu_ai.py               # 集計（赤を出す）
  python3 tools/gaibu_ai.py --html        # 進捗表から開けるHTMLを書き出す
"""
from __future__ import annotations

import argparse
import json
import os
import html as _html
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DIR = os.path.join(REPO, "status", "gaibu_ai")
DAICHO = os.path.join(DIR, "daicho.jsonl")
OUT_HTML = os.path.join(REPO, "1136-gaibu-ai-daicho.html")


def _now():
    return datetime.now(JST).isoformat(timespec="seconds")


def load():
    rows = []
    if not os.path.exists(DAICHO):
        return rows
    with open(DAICHO, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def save_all(rows):
    os.makedirs(DIR, exist_ok=True)
    tmp = DAICHO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, DAICHO)


def nage(ai, what, kigen, kane="未測定", memo=""):
    rows = load()
    nid = str(max([int(r.get("id", 0)) for r in rows] or [0]) + 1)
    r = {"id": nid, "at": _now(), "ai": ai, "what": what, "kigen": kigen,
         "kaeri": "no", "kaeri_at": None, "url": None, "kane": kane, "memo": memo}
    rows.append(r)
    save_all(rows)
    print(json.dumps(r, ensure_ascii=False))
    return r


def kaeri(nid, url=None, kane=None, state="yes", memo=None):
    rows = load()
    hit = False
    for r in rows:
        if str(r.get("id")) == str(nid):
            r["kaeri"] = state
            r["kaeri_at"] = _now()
            if url:
                r["url"] = url
            if kane:
                r["kane"] = kane
            if memo:
                r["memo"] = memo
            hit = True
    save_all(rows)
    print("ok" if hit else "見つからない: " + str(nid))


def shukei(rows=None):
    rows = rows if rows is not None else load()
    now = datetime.now(JST)
    nageta = len(rows)
    kaetta = len([r for r in rows if r.get("kaeri") in ("yes", "partial")])
    mada = [r for r in rows if r.get("kaeri") == "no"]
    okure = []
    for r in mada:
        k = r.get("kigen")
        try:
            if k and datetime.fromisoformat(k).replace(tzinfo=JST) < now:
                okure.append(r)
        except Exception:
            pass
    per = {}
    for r in rows:
        a = r.get("ai", "?")
        d = per.setdefault(a, {"nageta": 0, "kaetta": 0})
        d["nageta"] += 1
        if r.get("kaeri") in ("yes", "partial"):
            d["kaetta"] += 1
    return {"nageta": nageta, "kaetta": kaetta, "mikaeri": len(mada),
            "kigen_gire": len(okure), "per": per, "okure": okure, "rows": rows}


def report():
    s = shukei()
    print(f"投げた数 {s['nageta']} / 返ってきた数 {s['kaetta']} / 未返却 {s['mikaeri']} / 期限切れ {s['kigen_gire']}")
    for a, d in sorted(s["per"].items()):
        mark = "★赤" if d["nageta"] > 0 and d["kaetta"] == 0 else "  "
        print(f"{mark} {a}: 投げた {d['nageta']} / 返ってきた {d['kaetta']}")
    if s["nageta"] > 0 and s["kaetta"] == 0:
        print("★★赤：投げた数 > 0 なのに返ってきた数 = 0")
    for r in s["okure"]:
        print(f"★期限切れ id={r['id']} {r['ai']} 期限{r['kigen']} 「{r['what'][:40]}」")
    return s


def write_html():
    s = shukei()
    rows = sorted(s["rows"], key=lambda r: r.get("at", ""), reverse=True)
    aka = s["nageta"] > 0 and s["kaetta"] == 0
    tr = []
    for r in rows:
        st = r.get("kaeri")
        if st == "yes":
            cls, lab = "ok", "返ってきた"
        elif st == "partial":
            cls, lab = "part", "途中まで"
        else:
            cls, lab = "ng", "まだ返ってきていない"
        url = r.get("url")
        a = f'<a href="{_html.escape(url)}" target="_blank" rel="noopener">開く</a>' if url else "—"
        tr.append(
            f"<tr><td>{_html.escape(str(r.get('id','')))}</td>"
            f"<td>{_html.escape(str(r.get('at','')))[:16].replace('T',' ')}</td>"
            f"<td>{_html.escape(str(r.get('ai','')))}</td>"
            f"<td>{_html.escape(str(r.get('what','')))}</td>"
            f"<td>{_html.escape(str(r.get('kigen') or '—'))[:16].replace('T',' ')}</td>"
            f"<td class='{cls}'>{lab}</td><td>{a}</td>"
            f"<td>{_html.escape(str(r.get('kane','')))}</td></tr>")
    doc = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>外部AIの台帳｜投げっぱなしをゼロにする</title>
<style>
:root{{color-scheme:light;--ink:#191714;--bg:#f6f4ef;--sub:#7a7268;--line:#e0dad0;--red:#b3402f;--ok:#2e7d52;--amb:#a97c20}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Hiragino Sans","Yu Gothic",sans-serif;line-height:1.8}}
.w{{max-width:1000px;margin:0 auto;padding:28px 16px 80px}}
h1{{font-family:"Hiragino Mincho ProN",serif;font-size:clamp(21px,5.5vw,31px);margin:6px 0 4px}}
.kick{{font-family:Georgia,serif;font-size:10px;letter-spacing:.3em;color:var(--red)}}
.lead{{font-size:14px;color:#3a352e;margin:0 0 18px}}
.big{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 26px}}
.big div{{background:#fff;border:1px solid var(--line);padding:12px 16px;min-width:120px;flex:1}}
.big b{{display:block;font-size:26px;font-family:Georgia,serif;line-height:1.2}}
.big span{{font-size:11.5px;color:var(--sub)}}
.alarm{{background:#fbecea;border:1px solid var(--red);color:var(--red);padding:12px 16px;font-size:13.5px;margin:0 0 22px;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:13px;background:#fff;border:1px solid var(--line)}}
th,td{{border-bottom:1px solid var(--line);padding:9px 8px;text-align:left;vertical-align:top}}
th{{background:#faf8f4;font-size:11px;color:var(--sub);font-weight:400;white-space:nowrap}}
.ok{{color:var(--ok);font-weight:700}} .ng{{color:var(--red);font-weight:700}} .part{{color:var(--amb);font-weight:700}}
.wrap{{overflow-x:auto}}
.note{{font-size:12px;color:var(--sub);margin-top:16px}}
</style></head><body><div class="w">
<div class="kick">GAIBU AI / LEDGER</div>
<h1>外部AIの台帳</h1>
<p class="lead">外へ投げた仕事を1件1行で置く。返ってこないものが赤になる。投げっぱなしをここで潰す。</p>
{'<div class="alarm">★赤：投げた数 &gt; 0 なのに返ってきた数 = 0</div>' if aka else ''}
<div class="big">
<div><b>{s['nageta']}</b><span>投げた</span></div>
<div><b>{s['kaetta']}</b><span>返ってきた</span></div>
<div><b>{s['mikaeri']}</b><span>まだ返ってきていない</span></div>
<div><b>{s['kigen_gire']}</b><span>期限切れ</span></div>
</div>
<div class="wrap"><table>
<tr><th>#</th><th>投げた</th><th>誰に</th><th>何を</th><th>期限</th><th>返り</th><th>成果</th><th>かかった額</th></tr>
{''.join(tr) if tr else '<tr><td colspan="8">まだ1件もない</td></tr>'}
</table></div>
<p class="note">元データ：status/gaibu_ai/daicho.jsonl ／ 書き出し：tools/gaibu_ai.py --html ／ 更新 {_now()[:16].replace('T',' ')}</p>
</div></body></html>"""
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(doc)
    print(OUT_HTML)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--nage", action="store_true")
    p.add_argument("--ai")
    p.add_argument("--what")
    p.add_argument("--kigen")
    p.add_argument("--kane", default="未測定")
    p.add_argument("--memo", default="")
    p.add_argument("--kaeri")
    p.add_argument("--url")
    p.add_argument("--state", default="yes")
    p.add_argument("--html", action="store_true")
    a = p.parse_args()
    if a.nage:
        nage(a.ai, a.what, a.kigen, a.kane, a.memo)
    elif a.kaeri:
        kaeri(a.kaeri, a.url, a.kane if a.kane != "未測定" else None, a.state,
              a.memo or None)
    elif a.html:
        write_html()
    else:
        report()


if __name__ == "__main__":
    main()
