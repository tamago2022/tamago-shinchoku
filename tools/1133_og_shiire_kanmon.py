#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1133番【門0b・仕入れの門】OGカードが作れない曲は棚に入れない。

たまごさん（2026-09-25）:
  「仕入れの段階から、そこもしっかりクリアできるように、仕組みで全部直してね。」
  「OG画像が生成できない曲は棚に入らない。弾いた数を毎回ログに出す。
    弾き0が続いたら門が効いていない＝赤。」

■ ここで見るもの（外に出ない。0円。数秒）
  ① 曲名がある（空・"?"・"unknown"・"（仮）" のような仮置きは無い）
  ② アーティスト名がある
  ③ その2つで**実際にカードを焼いてみて**、1200x630で出てくる
  ④ 焼いたカードが 1133_og_karappo の空っぽ判定に落ちない（＝顔がある）
  1つでも欠けたら棚に入れない。理由を1行で返す。

■ 弾いた数のログ
  status/1133_og_kanmon.jsonl  … 1件1行（通した／弾いた・理由）
  python3 tools/1133_og_shiire_kanmon.py --tally   … 直近の通過/弾きの数を出す
  ★何日も弾き0が続いたら、門を通っていない（呼ばれていない）疑い＝赤。
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LOG = os.path.join(REPO, "status", "1133_og_kanmon.jsonl")
KARIOKI = re.compile(r"^\s*(\?+|-+|未定|不明|仮|（仮）|\(仮\)|unknown|untitled|no title)\s*$", re.I)


def _load(name):
    p = os.path.join(HERE, name)
    spec = importlib.util.spec_from_file_location(name[:-3], p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _nokoru(s):
    s = (s or "").strip()
    return "" if (not s or KARIOKI.match(s)) else s


def tsukureruka(title, artist, year="", lang="ja"):
    """カードが作れるか。作れるなら ("", png bytes)、作れないなら (理由, None)。"""
    t, a = _nokoru(title), _nokoru(artist)
    if not t:
        return "曲名が無い（カードの顔が作れない）", None
    if not a:
        return "アーティスト名が無い（カードの顔が作れない）", None
    try:
        card = _load("1133_og_card.py")
    except Exception as e:
        return ("カードの型が読めない（%s）。工場に Pillow が要ります："
                "python3 -m pip install --user pillow" % repr(e)[:60]), None
    try:
        im = card.card(t, a, year, lang)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        raw = buf.getvalue()
    except Exception as e:
        return "カードが焼けない（%s）" % repr(e)[:80], None
    try:
        r = _load("1133_og_karappo.py").judge_bytes(raw)
    except Exception as e:
        return "焼いたカードを検品できない（%s）" % repr(e)[:80], None
    if r.get("karappo"):
        return "焼いたカードが空っぽ判定に落ちた（%s）" % "／".join(r.get("riyuu") or []), None
    return "", raw


def gate(item, lang="ja"):
    """入荷票を1件見る。通れば ""、通らなければ理由。ログは必ず1行残す。"""
    riyuu, raw = tsukureruka(item.get("title"), item.get("artist"),
                             item.get("year") or "", lang)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
           "id": item.get("id"), "artist": item.get("artist"),
           "title": item.get("title"), "tsuuka": not riyuu, "riyuu": riyuu,
           "bytes": len(raw) if raw else 0}
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return riyuu


def tally(days=7):
    if not os.path.exists(LOG):
        return {"通した": 0, "弾いた": 0, "riyuu": {}, "note": "ログがまだありません"}
    kiru = time.time() - days * 86400
    ok = ng = 0
    why = {}
    for line in io.open(LOG, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        try:
            t = time.mktime(time.strptime(r["at"][:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            t = kiru + 1
        if t < kiru:
            continue
        if r.get("tsuuka"):
            ok += 1
        else:
            ng += 1
            k = (r.get("riyuu") or "")[:30]
            why[k] = why.get(k, 0) + 1
    return {"日数": days, "通した": ok, "弾いた": ng, "理由": why,
            "赤": (ok + ng) == 0}


if __name__ == "__main__":
    if "--tally" in sys.argv:
        print(json.dumps(tally(), ensure_ascii=False, indent=1))
    elif "--selftest" in sys.argv:
        cases = [
            ({"title": "夏の終りのハーモニー", "artist": "井上陽水・安全地帯", "year": 1986}, True),
            ({"title": "", "artist": "井上陽水"}, False),
            ({"title": "?", "artist": "井上陽水"}, False),
            ({"title": "September", "artist": ""}, False),
            ({"title": "September", "artist": "Earth, Wind & Fire", "year": 1978}, True),
        ]
        bad = 0
        for item, want in cases:
            r = gate(dict(item))
            got = not r
            print(("○" if got == want else "✕"), item.get("title") or "(空)", "→", r or "通す")
            bad += 0 if got == want else 1
        print("自己テスト:", "全部通りました" if not bad else "%d件おかしい" % bad)
        sys.exit(1 if bad else 0)
    else:
        print(__doc__)
