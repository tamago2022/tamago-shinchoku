#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1055番【外の返事をまとめる】同じ号への返事で仕事票を増やさない。

━━ なぜ要るか（2026-09-24 実測）━━

  たまごさん：「Jules/Devinの返事が溜まって処理されない」（台帳 jules・124回・7日）
  台帳が自分で書いていた次の一手：
    「返事を仕事票にせず、台帳の同じ行の『今どこまで』に上書きする」

  実測（status/queue.json・2026-09-24 06:4x）：
    発車待ち 197件 ／ そのうち GitHubの号に紐づくもの 69件
    中身は同じ号の重複： #446 が6件・#390 が5件・#447 が5件・#431 が4件 …
    ＝ **1つの号に返事が来るたびに、新しい仕事票が1枚増えていた。**
    工場が1本も動けない日は、これがそのまま山になる。

  だから「同じ号への返事は、先にある仕事票の中に足す」に変える。
  号ひとつにつき仕事票はひとつ。返事は本文の末尾に時系列で積む。

━━ 消さない ━━

  まとめた側の仕事票は**消さない**。status を hold にして holdNote に
  「どの番号にまとめたか」を書くだけ。hold は「終わった」には数えられない
  （tools/mitassei.py の OCHITA_JOTAI に入っている）ので、
  **未達成の数を嘘で減らさない。**発車待ちから外れるだけ。

━━ 使い方 ━━

  python3 tools/gaibu_henji_matome.py            # 今ある重複をまとめる
  python3 tools/gaibu_henji_matome.py --naka     # 何がまとまるかを見るだけ（書かない）

  github_watch.py からは fold() を呼ぶ（新しい返事が来たとき）。
"""
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

QUEUE = os.path.join(REPO, "status", "queue.json")
LOG = os.path.join(REPO, "status", "gaibu_henji_matome.log")

# 発車待ちとして残っているもの（ここに居るものだけ「まとめる」対象）
MATOME_TAISHO = ("waiting",)
KIRI = 1200          # 1通ぶんの本文をここで切る（票が肥らないように）
TSUMU_JOUGEN = 12    # 1枚の票に積む返事の数の上限（これを超えたら古い方から落とす）


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (time.strftime("%F %T"), msg))
    except Exception:
        pass


def gou_key(it):
    """仕事票がどのGitHubの号のものか。取れなければ None。"""
    if it.get("ghKey"):
        return it["ghKey"]
    blob = json.dumps(it, ensure_ascii=False)
    m = re.search(r"github\.com/([\w.-]+/[\w.-]+)/issues/(\d+)", blob)
    if m:
        return "gh:%s#%s" % (m.group(1), m.group(2))
    m = re.search(r"api\.github\.com/repos/([\w.-]+/[\w.-]+)/issues/(\d+)", blob)
    if m:
        return "gh:%s#%s" % (m.group(1), m.group(2))
    return None


def _tsumu(it, midashi, honbun, url):
    """仕事票の本文の末尾に、返事を1通ぶん足す。"""
    what = it.get("what") or ""
    shirushi = "\n\n━━ 同じ号への返事（新しい順に足していく） ━━"
    if shirushi not in what:
        what += shirushi
    hito = "\n\n● %s\n%s\n%s" % (midashi, url or "", (honbun or "").strip()[:KIRI])
    what += hito
    # 積みすぎたら古い返事から落とす（見出しより前の本文は絶対に触らない）
    atama, _, shippo = what.partition(shirushi)
    tsubu = [t for t in shippo.split("\n\n● ") if t.strip()]
    if len(tsubu) > TSUMU_JOUGEN:
        tsubu = tsubu[-TSUMU_JOUGEN:]
        shippo = "\n\n● " + "\n\n● ".join(tsubu)
        what = atama + shirushi + shippo
    it["what"] = what
    it["henjiCount"] = int(it.get("henjiCount") or 0) + 1
    it["henjiLastAt"] = time.strftime("%F %T")
    return it


def fold(repo, num, midashi, honbun, url):
    """新しい返事を、同じ号の発車待ちの票に足す。

    足せたら その票の番号(int)、足す先が無ければ None を返す。
    ★None のときだけ、呼んだ側は新しい仕事票を積む。
    """
    import command_ingest as CI
    key = "gh:%s#%s" % (repo, num)
    try:
        with CI.queue_lock():
            q = CI._load_queue()
            saki = None
            for it in q.get("items") or []:
                if it.get("status") not in MATOME_TAISHO:
                    continue
                if gou_key(it) != key:
                    continue
                if saki is None or (it.get("n") or 0) > (saki.get("n") or 0):
                    saki = it
            if saki is None:
                return None
            saki["ghKey"] = key
            _tsumu(saki, midashi, honbun, url)
            CI._save_queue(q)
            log("%s の返事を %s番 に足した（新しい票は作らない）" % (key, saki.get("n")))
            return saki.get("n")
    except Exception as e:
        log("足せませんでした %s: %r" % (key, e))
        return None


def matome(kaku=True):
    """今ある発車待ちの重複を、号ごとに1枚へまとめる。"""
    import command_ingest as CI
    with CI.queue_lock():
        q = CI._load_queue()
        items = q.get("items") or []
        kumi = {}
        for it in items:
            if it.get("status") not in MATOME_TAISHO:
                continue
            k = gou_key(it)
            if not k:
                continue
            kumi.setdefault(k, []).append(it)

        kekka = []
        heratta = 0
        for k, ko in sorted(kumi.items()):
            if len(ko) < 2:
                continue
            ko.sort(key=lambda x: x.get("n") or 0)
            honke = ko[-1]                    # いちばん新しい票を本体にする
            honke["ghKey"] = k
            for it in ko[:-1]:
                _tsumu(honke,
                       "%s番「%s」からまとめました" % (it.get("n"), (it.get("title") or "")[:60]),
                       it.get("what") or "", "")
                if kaku:
                    it["status"] = "hold"
                    it["holdNote"] = ("%s の返事は %s番 にまとめました（1055番）。"
                                      "この票は消していません。本体が終われば一緒に終わります。"
                                      % (k, honke.get("n")))
                    it["mergedInto"] = honke.get("n")
                heratta += 1
            kekka.append({"号": k, "本体": honke.get("n"),
                          "まとめた": [x.get("n") for x in ko[:-1]]})
        if kaku and heratta:
            CI._save_queue(q)
        nokori = len([it for it in items if it.get("status") == "waiting"])
    out = {"号の数": len(kekka), "発車待ちから外した票": heratta,
           "いまの発車待ち": nokori, "中身": kekka}
    if kaku and heratta:
        log("まとめた：号%d件・票%d枚を発車待ちから外した" % (len(kekka), heratta))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(matome(kaku=("--naka" not in sys.argv)))
