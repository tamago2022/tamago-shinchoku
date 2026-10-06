#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""鬼監督の口。やり残しを自分で見つけて、自分から1本だけ言い出す。

━━ なぜ作ったか（2026-09-22・たまごさん）━━

  「俺が言わなくても仕事が進むようにしてほしい。意図を汲み取って、
   『これできてないからここ進めよう』だとか、そこも半自動化したい。
   もちろん勝手な余計なことはやるな、というのはあるんだけど、
   『勝手にこれを進めましょうか』とか『やっておきました』でもいい。
   だけど、それはちゃんと役に立つことね。自分のビジョンに向かってつながること。
   余計なことはやらなくていいし、無駄なクレジット消費もしなくていい。」

鬼監督（tools/oni_gate.py）は「出すな」と言える。だが自分からは何も言わない。
これはその口。**目と口で1対。**

━━ 3つだけ守る ━━

  1. **1本しか言わない。**
     過去いちばん大きい失敗は「枝を4本同時に伸ばして本線が1ミリも進まなかった」。
     見つけたものが20本あっても、口に出すのは一番効く1本だけ。
     残りは黙って控えに積む（積むのはタダ。着火だけがお金と時間を食う）。

  2. **物差しは2つだけ。**
     ・お金につながるか
     ・ビジョン（棚・ごきげん補給所）に近づくか
     どちらにも当たらないものは**枝**。枝は積むだけで着火しない。
     「やった方がよさそう」は理由にならない。それで4本死んでいる。

  3. **AIを1回も呼ばない。**
     全部ただの文字の照合と日付の引き算。クレジットは1円もかからない。
     毎日呼んでも、呼ばない日と費用が同じ。だから毎日呼べる。

━━ やる／言う／触らない の振り分け ━━

  やっておく  … いまは何もしない（v1では自動着火はしない）。
                口が当たっているかをたまごさんが見て、当たってから手を付ける。
  言う        … 一番効く1本。「これ進めましょうか」まで書く
  触らない    … 枝。控えに積むだけ。口に出さない

使い方:
  python3 tools/oni_kuchi.py            # 1日1回に間引いて、言うことがあれば言う
  python3 tools/oni_kuchi.py --now      # 間引きを無視していま見る
  python3 tools/oni_kuchi.py --all      # 順位を全部見る（調べもの用）

終了コード: 0=いつも0（心臓に相乗りするので、工場を止めない）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(REPO, "status")
QUEUE = os.path.join(STATUS, "queue.json")
OUT = os.path.join(STATUS, "oni_kuchi.md")
STAMP = os.path.join(STATUS, ".oni_kuchi_last")
JST = datetime.timezone(datetime.timedelta(hours=9))

# ---------------------------------------------------------------------------
# 物差し。たまごさんが言った2つだけ。ここに3つ目を足さないこと。
# ---------------------------------------------------------------------------
OKANE = re.compile(
    r"売|課金|価格|値段|販売|購入|決済|収益|有料|Gumroad|スタンプ|"
    r"スポンサー|広告|サブスク|note|投げ銭")
HONSEN = re.compile(
    r"棚|仕入|曲|カバー|アーティスト|ごきげん|補給所|名カバー|案内所|"
    r"ページ|公開|サムネ|コピー|導線|検索|トップ")
EDA = re.compile(
    r"掃除|片づけ|片付け|整理|棚卸|移行|名前を変|リネーム|ログを|"
    r"ディスク|容量|バックアップ|リファクタ")

# 止まったまま何日で「もう自分から言う」か
STUCK_DAYS = 2


def _load_items():
    try:
        with open(QUEUE, encoding="utf-8") as f:
            q = json.load(f)
    except Exception as e:
        print("受付台帳が読めませんでした: %s" % e)
        return []
    return q.get("items") or []


def _days_since(s):
    if not s:
        return None
    try:
        d = datetime.datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=JST)
        return (datetime.datetime.now(JST) - d).days
    except Exception:
        return None


def score(it):
    """点が高いほど「いま言うべき」。理由も一緒に返す（点だけ出しても直せない）。"""
    text = "%s %s" % (it.get("title") or "", it.get("why") or "")
    st = (it.get("status") or "").lower()
    pts, why = 0, []

    if OKANE.search(text):
        pts += 50
        why.append("お金に直接つながる")
    if HONSEN.search(text):
        pts += 30
        why.append("棚（本線）の話")
    if EDA.search(text) and not OKANE.search(text):
        pts -= 40
        why.append("枝（掃除・整理の類）")

    # 止まっている度。始めたのに終わっていないものは、新しく始めるより先。
    if st == "stuck":
        pts += 25
        why.append("いちど着手して止まったまま")
    elif st == "awaiting_check":
        pts += 15
        why.append("たまごさんの確認待ちで置きっぱなし")
    elif st == "hold":
        pts -= 30
        why.append("たまごさんが自分で止めたもの")
    elif st in ("done", "merged"):
        pts -= 999

    d = _days_since(it.get("startedAt"))
    if d is not None and st in ("stuck", "running", "awaiting_check"):
        if d >= STUCK_DAYS:
            pts += min(d, 20)
            why.append("%d日動いていない" % d)

    try:
        pr = int(it.get("priority") or 3)
        pts += (3 - pr) * 8
    except Exception:
        pass

    return pts, why


def rank(items):
    rows = []
    for it in items:
        st = (it.get("status") or "").lower()
        if st in ("done", "merged"):
            continue
        p, w = score(it)
        rows.append((p, w, it))
    rows.sort(key=lambda r: -r[0])
    return rows


def _throttled():
    """1日1回に間引く。同じ話を1日に何度も言うのは水くみ。"""
    today = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    try:
        with open(STAMP, encoding="utf-8") as f:
            if f.read().strip() == today:
                return True
    except Exception:
        pass
    return False


def _stamp():
    try:
        with open(STAMP, "w", encoding="utf-8") as f:
            f.write(datetime.datetime.now(JST).strftime("%Y-%m-%d"))
    except Exception:
        pass


def say(rows, write=True):
    if not rows:
        return "言うことはありません。"
    top_p, top_w, top = rows[0]
    if top_p <= 0:
        return ("言うことはありません（残っているのは枝ばかりで、"
                "いま着火する値打ちのあるものがありません）。")

    eda = [r for r in rows if r[0] < 0]
    tsugi = [r for r in rows[1:6] if r[0] > 0]

    now = datetime.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# 鬼監督から、1本だけ")
    lines.append("")
    lines.append("%s" % now)
    lines.append("")
    lines.append("## これ、進めましょうか")
    lines.append("")
    lines.append("**%s番 ― %s**" % (top.get("n") or "?", top.get("title") or ""))
    lines.append("")
    if top.get("why"):
        lines.append("> %s" % top["why"])
        lines.append("")
    lines.append("なぜこれかというと：%s。" % "、".join(top_w))
    lines.append("")
    lines.append("「やって」と言ってもらえれば進めます。違うなら違うと言ってください。")
    lines.append("")
    if tsugi:
        lines.append("## その次（いまは手を付けません）")
        lines.append("")
        for p, w, it in tsugi:
            lines.append("- %s番 %s ― %s" % (
                it.get("n") or "?", it.get("title") or "", "、".join(w)))
        lines.append("")
    lines.append("## 触らないもの")
    lines.append("")
    lines.append("枝（掃除・整理の類）が%d件たまっています。"
                 "お金にもビジョンにも近づかないので、控えに積むだけにして着火しません。"
                 % len(eda))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("見ているもの：受付台帳の%d件。物差しは「お金につながるか」"
                 "「棚に近づくか」の2つだけ。AIは1回も呼んでいません（0円）。" % len(rows))
    body = "\n".join(lines) + "\n"
    if write:
        try:
            os.makedirs(STATUS, exist_ok=True)
            with open(OUT, "w", encoding="utf-8") as f:
                f.write(body)
        except Exception:
            pass
    return body


def main():
    ap = argparse.ArgumentParser(description="鬼監督の口 — やり残しを自分で見つけて1本だけ言う")
    ap.add_argument("--now", action="store_true", help="1日1回の間引きを無視する")
    ap.add_argument("--all", action="store_true", help="順位を全部見る")
    a = ap.parse_args()

    items = _load_items()
    rows = rank(items)

    if a.all:
        for p, w, it in rows[:40]:
            print("%5d  %-14s %s ― %s" % (
                p, (it.get("status") or "無"),
                (it.get("n") or "?"), (it.get("title") or "")[:40]))
        print("\n合計 %d件" % len(rows))
        return 0

    if not a.now and _throttled():
        return 0

    print(say(rows))
    _stamp()
    return 0


if __name__ == "__main__":
    sys.exit(main())
