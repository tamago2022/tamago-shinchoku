#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/kenpou_tsuiki.py ── 第16条【憲法更新】を仕組みにする（34514号）。

たまごさんの言葉（2026-08-05・FOUNDER_INTENT 16条）:
  「『これを憲法にして』等の指示は、その場限りで終わらせず該当文書に追記候補を作る。」

★この条文自体が、言われてから1ヶ月以上『その場のセッションで直すだけ』になっていた
  （直した瞬間は反映されるが、仕組みが無いので次に同じ発言があっても毎回また
  人が気づくまで埋もれる＝条文が自分自身には適用されていなかった）。

やること:
  会話の中で「これを憲法にして」「ルールにして」のような一文が出たら、
  その場のセッションの編集だけで終わらせず、**追記候補を1件、台帳に残す**。
  台帳の形は tools/daicho.py（言われたら1行残す・2回目は回数+1・3回目以上は最優先）
  をそのまま使う。新しい保存方式は作らない。

  実際にどのファイルへ・どの言い回しで入れるかの最終判断はここでは行わない
  （自動で憲法ファイルを書き換えると、言葉の受け取り違いがそのまま恒久ルール化
  する事故が起きるため。台帳に残す＝「埋もれさせない」が目的で、
  「人の確認なしに本文を書き換える」は目的ではない）。

正本: status/kenpou_tsuiki.json
画面: share/kenpou_tsuiki.html（--page で作る）
呼び口: tools/stop_kanmon/prompt_gate.mjs（UserPromptSubmitで毎回自動検出）

使い方:
  python3 tools/kenpou_tsuiki.py --kenshutsu "<会話の生テキスト>"
  python3 tools/kenpou_tsuiki.py --ichiran
  python3 tools/kenpou_tsuiki.py --page
  python3 tools/kenpou_tsuiki.py --shiken
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from daicho import onaji  # ★既存の「同じ依頼かどうか」判定をそのまま使う（新しい類似度は作らない）

LEDGER = os.path.join(REPO, "status", "kenpou_tsuiki.json")
PAGE = os.path.join(REPO, "share", "kenpou_tsuiki.html")
JST = datetime.timezone(datetime.timedelta(hours=9))

# ---------------------------------------------------------------------------
# 検出条件：「これを憲法にして」等
# ---------------------------------------------------------------------------
TRIGGER = re.compile(
    r"(憲法|恒久(の)?ルール|ルール)に(して|しよう|してくれ|してください|しておいて|しちゃって|しといて)"
)

# 該当文書の推定（当たらなければ「未分類」＝人が判断する）
DOC_HINTS = [
    (re.compile(r"ブラウザ|タブ|Chrome|Brave|タブID|tabId"), "tools/prompt_rules/always-21-browser-routing.md", "ブラウザ振り分け"),
    (re.compile(r"報告|URL無し|完了条件|9割削"), "子セッション先頭文（session preamble）", "報告ルール"),
    (re.compile(r"確認|承認|課金|お金"), "子セッション先頭文（session preamble）", "確認・金銭"),
    (re.compile(r"オリジナル|発明|自作"), "tools/1184_kanmon.py 周辺（0.5節）", "オリジナル禁止"),
]


def ima():
    return datetime.datetime.now(JST)


def yomu():
    if not os.path.exists(LEDGER):
        return {"updatedAt": "", "rows": []}
    try:
        return json.load(io.open(LEDGER, encoding="utf-8"))
    except Exception:
        return {"updatedAt": "", "rows": []}


def kaku(d):
    d["updatedAt"] = ima().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    tmp = LEDGER + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, LEDGER)


def _bunkatsu(text):
    return [s.strip() for s in re.split(r"[\r\n]+|。", text or "") if s.strip()]


def kouho_bun(text):
    """トリガーを含む文＋直前の文（文脈が無い追記候補を作らない）"""
    bun = _bunkatsu(text)
    for i, s in enumerate(bun):
        if TRIGGER.search(s):
            maegaki = bun[i - 1] if i > 0 else ""
            kouho = (maegaki + "。" + s) if maegaki else s
            return kouho[:200]
    return text.strip()[:200]


def suisoku_bunsho(text):
    for pat, doc, label in DOC_HINTS:
        if pat.search(text or ""):
            return doc, label
    return "未分類（人が判断）", "未分類"


def kenshutsu(text, test=False):
    if not TRIGGER.search(text or ""):
        return None

    kouho = kouho_bun(text)
    doc, label = suisoku_bunsho(text)
    d = yomu()
    t = ima()

    for r in d["rows"]:
        if onaji(r["kouho"], kouho):
            r["kaisu"] = int(r.get("kaisu") or 1) + 1
            r["saigo"] = t.strftime("%Y-%m-%d %H:%M")
            kaku(d)
            print(json.dumps({"どうした": "追記候補の回数を+1しました", "id": r["id"],
                              "回数": r["kaisu"]}, ensure_ascii=False))
            return r

    rid = "kenpou-%d" % int(t.timestamp())
    r = {
        "id": rid,
        "kouho": kouho,
        "suisoku_bunsho": doc,
        "label": label,
        "kaisu": 1,
        "hatsu": t.strftime("%Y-%m-%d %H:%M"),
        "saigo": t.strftime("%Y-%m-%d %H:%M"),
        "jotai": "追記候補（未反映・人の確認待ち）",
        "test": bool(test),
    }
    d["rows"].insert(0, r)
    kaku(d)
    print(json.dumps({"どうした": "追記候補を1件作りました", "id": rid,
                      "推定文書": doc}, ensure_ascii=False))
    return r


def ichiran():
    d = yomu()
    rows = [r for r in d["rows"] if not r.get("test")]
    if not rows:
        print("追記候補は0件です。")
        return
    for r in rows:
        print("[%s] %dx %s → %s" % (r["id"], r["kaisu"], r["kouho"][:40], r["suisoku_bunsho"]))


def page():
    d = yomu()
    rows = [r for r in d["rows"] if not r.get("test")]
    trs = "".join(
        "<tr><td>%s</td><td>%s</td><td class=\"num\">%d</td><td>%s</td><td>%s</td></tr>"
        % (r["hatsu"], _esc(r["kouho"]), r["kaisu"], _esc(r["suisoku_bunsho"]), _esc(r["jotai"]))
        for r in rows
    )
    html = PAGE_TMPL.replace("__N__", str(len(rows))).replace("__ROWS__", trs or
        "<tr><td colspan=5>まだ追記候補はありません（『〜を憲法にして』の発言がまだ無い）</td></tr>")
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with io.open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print("書きました: %s" % PAGE)


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PAGE_TMPL = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>第16条｜憲法更新の追記候補（34514号）</title>
<style>
:root{--paper:#f4f1ea;--ink:#16130f;--sub:#6b6259;--rule:#d8d2c6;--ok:#2f6b3f}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font-family:"Hiragino Sans","Noto Sans JP",system-ui,sans-serif;font-size:15px;line-height:1.65}
.wrap{max-width:960px;margin:0 auto;padding:26px 16px 80px}
header{border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:16px}
h1{font-size:20px;margin:0 0 4px}.lead{color:var(--sub);font-size:12.5px;margin:0}
.kotae{border:3px solid var(--ink);padding:14px 16px;margin:0 0 20px;background:#fff}
.kotae .big{font-size:24px;font-weight:800}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:10.5px;color:var(--sub);padding:6px 8px 6px 0;border-bottom:1px solid var(--rule)}
td{padding:9px 8px 9px 0;border-bottom:1px solid var(--rule);vertical-align:top}
.num{font-weight:800;text-align:center}
footer{margin-top:30px;color:var(--sub);font-size:11.5px}
</style></head><body><div class="wrap">
<header>
<h1>第16条｜「憲法にして」の追記候補</h1>
<p class="lead">34514号／会話中に「これを憲法にして」等が出たら自動で1件残す（その場のセッションで終わらせない）</p>
</header>
<div class="kotae"><div class="big">いまの追記候補：__N__ 件</div>
<p>人（たまごさん）かAIがここを見て、推定文書へ実際に追記するかを判断する。同じ候補が2回目に出たら新しい行を作らず回数を+1する。</p></div>
<table><thead><tr><th>最初</th><th>候補の文</th><th>回数</th><th>推定文書</th><th>状態</th></tr></thead>
<tbody>__ROWS__</tbody></table>
<footer>正本: status/kenpou_tsuiki.json ／ 検出口: tools/stop_kanmon/prompt_gate.mjs</footer>
</div></body></html>
"""


def shiken():
    """逆テスト：検出・回数+1・無関係な文で検出しない、の3つを確かめる。"""
    before = len(yomu()["rows"])
    r1 = kenshutsu("明日の作業方針についての雑談です。これを憲法にしてください。タブは必ず閉じること。", test=True)
    assert r1 is not None and r1["kaisu"] == 1, "①検出できていない"
    r2 = kenshutsu("明日の作業方針についての雑談です。これを憲法にしてください。タブは必ず閉じること。", test=True)
    assert r2["id"] == r1["id"] and r2["kaisu"] == 2, "②2回目で回数+1されていない"
    r3 = kenshutsu("今日のランチは何にしようか迷っています。", test=True)
    assert r3 is None, "③無関係な文で誤検出している"
    after = len(yomu()["rows"])
    assert after == before + 1, "④台帳の行数が想定どおり増えていない"
    print("KENPOU_SHIKEN_RESULT: PASS（検出%d件→行数+1・回数+1・無関係文は検出せず）" % after)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kenshutsu")
    ap.add_argument("--ichiran", action="store_true")
    ap.add_argument("--page", action="store_true")
    ap.add_argument("--shiken", action="store_true")
    a = ap.parse_args()

    if a.shiken:
        sys.exit(shiken())
    if a.kenshutsu is not None:
        r = kenshutsu(a.kenshutsu)
        sys.exit(0 if r else 1)
    if a.ichiran:
        ichiran()
        return
    if a.page:
        page()
        return
    ap.print_help()


if __name__ == "__main__":
    main()
