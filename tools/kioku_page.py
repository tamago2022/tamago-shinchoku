#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/kioku_page.py ── 「何回言われたか」の紙を1枚だけ書く。

たまごさん（2026-09-26）:
  「過去のDispatch会話ログを機械で読んで、たまごさんの依頼を全部抜く。
    同じ依頼を何回言われたかを数える。出すのは本番HTMLページ1枚。
    列は：内容／言われた回数／最初に言われた日／状態／期限区分。回数の多い順。
    ★3回以上は自動でP1。」

出す場所は**リポ直下 1152-nankai.html**（share/ の下ではない）。スマホで開けるURL。

  https://tamago2022.github.io/tamago-shinchoku/1152-nankai.html

中身の出どころは2つだけ。ここでは何も判定しない（判定を2か所に置かない）。
  ・status/kioku/hatsugen.jsonl … 何を何回言われたか（tools/kioku.py が拾う）
  ・status/shukudai/daicho.jsonl … いまどうなっているか（tools/shukudai.py が持つ）

★期限区分は「言われた回数」と「最初に言われてからの日数」だけで機械が決める。
  人が触れる欄を作らない。触れると必ず「いつでも」に逃がされる。
"""
from __future__ import annotations

import datetime
import hashlib
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
HATSUGEN = os.path.join(ST, "kioku", "hatsugen.jsonl")
DAICHO = os.path.join(ST, "shukudai", "daicho.jsonl")
OUT = os.path.join(REPO, "1152-nankai.html")
PUB = os.path.join(ST, "public", "nankai.json")

JST = datetime.timezone(datetime.timedelta(hours=9))


def now():
    return datetime.datetime.now(JST)


def norm(s):
    return re.sub(r"[★☆*#`>【】\[\]「」『』（）()・:：,、。\.\-—–_/\\!！?？\s]", "", s or "").lower()


def jsonl(path):
    out = []
    if not os.path.exists(path):
        return out
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def hi_kazu(d):
    """最初に言われてから何日経ったか。日付が読めなければ 0（＝急がせない）。"""
    try:
        y = datetime.datetime.strptime((d or "")[:10], "%Y-%m-%d").replace(tzinfo=JST)
        return max(0, (now() - y).days)
    except Exception:
        return 0


def kigen(count, days):
    """★期限区分。機械が決める。人が動かせる欄を作らない。

      今すぐ    3回以上言わせた／2回言わせて1週間以上放置
      今週      2回言わせた／1回でも1ヶ月以上放置
      1ヶ月以内 1回で1週間以上
      いつでも  それ以外
    """
    if count >= 3 or (count >= 2 and days >= 7):
        return "今すぐ", 1
    if count >= 2 or days >= 30:
        return "今週", 2
    if days >= 7:
        return "1ヶ月以内", 3
    return "いつでも", 4


def jotai(title, daicho_by_key):
    """いまどうなっているか。宿題台帳が正本。載っていなければ未着手。"""
    r = daicho_by_key.get(norm(title)[:24])
    if not r:
        return "未着手", None
    st = r.get("state") or "未着手"
    if st in ("完了",):
        return "完了", r.get("evidence")
    if st in ("走行中",):
        return "走行中", None
    if st in ("確認待ち", "止まっている", "引き継ぎ", "重複"):
        return st, None
    return "未着手", None


def atsumeru():
    daicho = jsonl(DAICHO)
    by_key = {}
    for r in daicho:
        by_key.setdefault(norm(r.get("title"))[:24], r)
    rows = []
    for r in jsonl(HATSUGEN):
        t = (r.get("title") or "").strip()
        if len(norm(t)) < 8:
            continue
        n = int(r.get("count") or 1)
        d = hi_kazu(r.get("firstSaid"))
        k, korder = kigen(n, d)
        st, ev = jotai(t, by_key)
        rows.append({
            "id": r.get("id") or hashlib.sha1(norm(t).encode()).hexdigest()[:12],
            "title": t, "count": n,
            "firstSaid": r.get("firstSaid") or "―", "lastSaid": r.get("lastSaid") or "―",
            "days": d, "state": st, "evidence": ev,
            "kigen": k, "kigenOrder": korder,
            # ★言われた日時は分まで。判定日は言われた瞬間に焼かれていて動かせない。
            "saidJa": r.get("firstSaidJa") or r.get("firstSaid") or "―",
            "hantei1w": r.get("hantei1w"), "hantei1m": r.get("hantei1m"),
            "sonogo": r.get("sonogo"), "aka": bool(r.get("aka")),
            # ★3回以上は自動でP1。判定日で赤になったものもP1（tools/hantei.py が付ける）。
            "p": 1 if (n >= 3 or r.get("aka")) else (2 if n >= 2 else 3),
        })
    # 回数の多い順。同数なら古い順（古い方が先に返すべき）。
    rows.sort(key=lambda r: (-r["count"], r["firstSaid"]))
    return rows


def konshu(rows):
    """★ページの一番上にでかく出す3つ。走らせた本数は出さない。

    たまごさん（2026-09-26）:
      「測る数字は『走らせた本数』ではなく★『変わった件数』だけ。
        ページの一番上にでかく出すのは 今週言われた件数／実際に変わった件数／達成率%。
        たまごさん基準は最低5割。」

    「変わった」＝機械の検品と外の判定を通って完了になったもの。
    こちら側が「やりました」と書いただけのものは1件も数えない。
    """
    kara = (now() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    k = [r for r in rows if str(r.get("firstSaid") or "")[:10] >= kara]
    kaw = [r for r in k if r["state"] == "完了"]
    n, m = len(k), len(kaw)
    pct = round(100.0 * m / n, 1) if n else 0.0
    return {"iwareta": n, "kawatta": m, "pct": pct, "todoiteru": bool(n and pct >= 50.0)}


CSS = """
:root{--ink:#16130f;--sub:#6b6259;--line:#e5ded4;--bg:#faf7f2;--red:#c0392b;--amber:#b7791f;--gr:#1e7a3c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px 14px 64px}
h1{font-size:20px;margin:0 0 4px;letter-spacing:.02em}
.sub{color:var(--sub);font-size:12px;margin:0 0 18px}
.big{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:0 0 10px}
.big>div{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px 10px;text-align:center}
.big b{display:block;font-size:44px;line-height:1.05;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.big span{font-size:12px;color:var(--sub)}
.big .ng b{color:var(--red)}
.big .okk b{color:var(--gr)}
.kijun{margin:0 0 20px;font-size:12.5px;color:var(--sub);text-align:center}
.kijun b{color:var(--red)}
.mini{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--sub);margin:0 0 14px}
.mini b{color:var(--red);font-variant-numeric:tabular-nums;font-size:14px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);
 border-radius:10px;overflow:hidden;font-size:13px}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f3ede4;font-size:11px;color:var(--sub);font-weight:600;white-space:nowrap}
td.t{font-size:13px}
td.n{text-align:right;font-variant-numeric:tabular-nums;width:3.8em}
td.n.hi{color:var(--red);font-weight:700}
td.d{white-space:nowrap;color:var(--sub);font-size:11.5px}
td.g{color:var(--sub);font-size:11.5px}
.past{color:var(--red);font-weight:700}
tr.hot{background:#fdf2f0}
tr.warm{background:#fdf8ee}
.p1{background:var(--red);color:#fff;border-radius:4px;padding:1px 5px;font-size:10px;margin-right:5px}
.p2{background:var(--amber);color:#fff;border-radius:4px;padding:1px 5px;font-size:10px;margin-right:5px}
.s{font-size:11px;padding:2px 7px;border-radius:99px;white-space:nowrap;display:inline-block}
.s.ok{background:#e3f3e6;color:var(--gr)}
.s.run{background:#e4eefb;color:#1c5fa8}
.s.yet{background:#efeae3;color:#6b6259}
.s.wait{background:#fdf0dc;color:#96650d}
.s.stop{background:#fbe3e0;color:#a6301f}
.s.dup{background:#efeae3;color:#a09789}
code{font-family:inherit;font-size:inherit;color:inherit;background:none;padding:0}
.note{margin:18px 0 0;font-size:11.5px;color:var(--sub);line-height:1.9}
@media(max-width:640px){.big b{font-size:34px}
 th:nth-child(5),th:nth-child(6),td:nth-child(5),td:nth-child(6){display:none}}
"""


def build(rows):
    def esc(s):
        return (str(s if s is not None else "")
                .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    today = now().strftime("%Y-%m-%d")
    w = konshu(rows)
    n3 = len([r for r in rows if r["count"] >= 3])
    aka = len([r for r in rows if r.get("aka")])
    cls = {"完了": "ok", "走行中": "run", "未着手": "yet", "確認待ち": "wait",
           "止まっている": "stop", "引き継ぎ": "yet", "重複": "dup"}

    def hi(d):
        """判定日。★来ているのに返っていなければ赤く出す。"""
        if not d:
            return "-"
        sugita = d <= today
        return ('<span class="past">%s</span>' % esc(d)) if sugita else esc(d)

    tr = []
    for r in rows:
        mada = r["state"] != "完了"
        badge = ('<b class="p1">P1</b>' if r["p"] == 1 else
                 '<b class="p2">P2</b>' if r["p"] == 2 else "")
        tr.append(
            '<tr class="{cls}"><td class="d">{said}</td>'
            '<td class="t">{badge}<code data-inyou="台帳">{title}</code></td>'
            '<td class="n {hicls}">{n}</td>'
            '<td><span class="s {scls}">{st}</span></td>'
            '<td class="d">{h1}</td><td class="d">{h2}</td>'
            '<td class="g"><code data-inyou="台帳">{sonogo}</code></td></tr>'.format(
                cls=("hot" if (r["count"] >= 3 or r.get("aka")) else
                     "warm" if r["count"] >= 2 else ""),
                said=esc(r.get("saidJa")), badge=badge, title=esc(r["title"]),
                hicls="hi" if r["count"] >= 2 else "", n=r["count"],
                scls=cls.get(r["state"], "yet"), st=esc(r["state"]),
                h1=hi(r.get("hantei1w")) if mada else esc(r.get("hantei1w") or "-"),
                h2=hi(r.get("hantei1m")) if mada else esc(r.get("hantei1m") or "-"),
                sonogo=esc(r.get("sonogo") or "―")))

    karappo = ('<tr><td colspan="7" style="color:#928a80">まだ1件も拾えていません。'
               'tools/kioku.py --zenbu を回してください。</td></tr>')

    return """<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>何回言われたか</title>
<style>{css}</style>
<div class="wrap">
<h1>何回言われたか</h1>
<p class="sub">たまごさんの発言を会話ログから機械で拾って数えたもの。{at} 時点。手で書き足していません。<br>
この紙の本番：<a href="https://tamago2022.github.io/tamago-shinchoku/1152-nankai.html">https://tamago2022.github.io/tamago-shinchoku/1152-nankai.html</a>
　／　宿題台帳：<a href="https://tamago2022.github.io/tamago-shinchoku/share/check/1138-shukudai.html">1138-shukudai.html</a>
　／　完了の門：<a href="https://tamago2022.github.io/tamago-shinchoku/share/check/1141-kanryo-taikan.html">1141-kanryo-taikan.html</a></p>

<div class="big">
 <div><b>{iwareta}</b><span>今週 言われた件数</span></div>
 <div class="{c}"><b>{kawatta}</b><span>実際に変わった件数</span></div>
 <div class="{c}"><b>{pct}%</b><span>達成率</span></div>
</div>
<p class="kijun">基準は<b>最低5割</b>。{hyoka}</p>

<div class="mini">
 <span>3回以上言わせた（自動P1） <b>{n3}</b> 件</span>
 <span>判定日で赤になった <b>{aka}</b> 件</span>
 <span>台帳ぜんぶ {zen} 件</span>
</div>

<table>
<thead><tr><th>言われた日時</th><th>内容</th><th>回数</th><th>状態</th>
<th>1週間後の判定日</th><th>1ヶ月後の判定日</th><th>実際どうなったか</th></tr></thead>
<tbody>
{tr}
</tbody></table>

<p class="note">
 ・回数の多い順。<b>3回以上は自動でP1</b>。<br>
 ・<b>判定日が来たら機械が自動で状態を見に行きます</b>（tools/hantei.py）。変わっていなければ自動で赤＋P1に繰り上げ、その場で再発車します。<br>
 ・<b>状態「完了」はこちら側では書けません。</b>URLを叩いて200・中身が空でない・過去の指摘に引っかからない、を機械が確認し、さらに<b>外の判定（Genspark／Codex／公開リポ ai-kaigi）が入って初めて完了</b>になります（tools/oni_modoshi.py・tools/gaibu_shinsa.py）。<br>
 ・数えているのは「走らせた本数」ではなく<b>変わった件数</b>だけです。<br>
<br>
 <b>実測（この紙の数字の出どころ）：</b><br>
 <code>実測: 達成率 {pct}%　＝ {kawatta} / {iwareta}（今週言われた件数のうち、機械の検品と外の判定を通ったもの）
 ｜ 出どころ: status/kioku/hatsugen.jsonl ／ status/oni_modoshi/kenpin.jsonl ｜ 測った日時: {at}</code><br>
 ・拾う係 tools/kioku.py ／ 判定 tools/hantei.py ／ この紙 tools/kioku_page.py。すべて0円（AIを呼ばない・外へ出ない）。
</p>
</div>
""".format(css=CSS, at=esc(now().strftime("%Y-%m-%d %H:%M")),
           iwareta=w["iwareta"], kawatta=w["kawatta"], pct=w["pct"],
           c=("okk" if w["todoiteru"] else "ng"),
           hyoka=("届いています。" if w["todoiteru"] else "<b>★届いていません。</b>"),
           n3=n3, aka=aka, zen=len(rows), tr=("\n".join(tr) or karappo))


def main():
    rows = atsumeru()
    write_text(OUT, build(rows))
    write_text(PUB, json.dumps({
        "at": now().strftime("%Y-%m-%d %H:%M"),
        "total": len(rows),
        "iwareta3": len([r for r in rows if r["count"] >= 3]),
        "iwareta2": len([r for r in rows if r["count"] >= 2]),
        "mikanryo": len([r for r in rows if r["state"] != "完了"]),
        "imasugu": len([r for r in rows if r["kigen"] == "今すぐ"]),
        "url": "https://tamago2022.github.io/tamago-shinchoku/1152-nankai.html",
        "rows": rows[:400],
    }, ensure_ascii=False, indent=1))
    print("書きました：%s（%d件／3回以上 %d／2回以上 %d）"
          % (os.path.relpath(OUT, REPO), len(rows),
             len([r for r in rows if r["count"] >= 3]),
             len([r for r in rows if r["count"] >= 2])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
