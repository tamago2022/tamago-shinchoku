#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【出どころ】その1本は「本人が選んだ」のか「機械が選んだ」のか。

たまごさんの言葉（2026-09-27）:
  「各行に『本人が選んだ／機械が選んだ』の札。機械が選んだものは赤。」

実測（2026-09-27）:
  絢香「三日月」／Neil Young「Harvest Moon」… 9/27 08:12 に 1166_ireru が自動投入
  Green Day …                                 9/26 23:45 に 1165_ireru が自動投入
  → いずれも **本人（たまごさん）が選んだ記録は無い**。だから赤。

どこを見るか:
  status/buffer_queue/dashita.jsonl … 入れた係の名前（where）が1行ずつ入っている台帳
  status/buffer_queue/honnin.jsonl  … ★たまごさんが選んだものを置く台帳（下の「入れ方」）

本人が選んだことにする入れ方（どちらでもよい）:
  1) honnin.jsonl に1行足す
       {"song_key":"ayaka/mikazuki","at":"2026-09-27 12:00","dare":"たまごさん"}
       {"post_id":"abc123"} でも効く
  2) 入れる係の where を HONNIN に入っている名前にする（例 "owner_te_ire"）

★分からないものを「本人」にはしない。記録が無いものは 機械 と書く。
"""
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "buffer_queue", "dashita.jsonl")
HONNIN = os.path.join(REPO, "status", "buffer_queue", "honnin.jsonl")

# 「本人が選んだ」と言える係の名前だけ。ここに無いものは全部 機械。
HONNIN_WHERE = {"owner_te_ire", "tamago_te_ire", "honnin", "owner"}


def _rows(p):
    out = []
    try:
        for ln in io.open(p, encoding="utf-8"):
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    except Exception:
        pass
    return out


def _song_key(text):
    try:
        import buffer_sekisho
        return buffer_sekisho.song_key(text or "")
    except Exception:
        return ""


def hyou():
    """台帳を1回読んで引き表にする。{by_post:{}, by_song:{}, honnin_post:set, honnin_song:set}"""
    by_post, by_song = {}, {}
    for r in _rows(DAICHO):
        w = r.get("where") or ""
        at = r.get("at") or ""
        if r.get("post_id"):
            by_post[r["post_id"]] = (w, at)
        if r.get("song_key"):
            by_song.setdefault(r["song_key"], (w, at))
    hp, hs = set(), set()
    for r in _rows(HONNIN):
        if r.get("post_id"):
            hp.add(r["post_id"])
        if r.get("song_key"):
            hs.add(r["song_key"])
    return {"by_post": by_post, "by_song": by_song,
            "honnin_post": hp, "honnin_song": hs}


def shiraberu(post_id, text, h=None):
    """1本ぶんの出どころ。{"dare","aka","where","at","song_key"}"""
    h = h or hyou()
    sk = _song_key(text)
    w, at = h["by_post"].get(post_id) or h["by_song"].get(sk) or ("", "")
    if post_id in h["honnin_post"] or (sk and sk in h["honnin_song"]) \
            or (w in HONNIN_WHERE):
        return {"dare": "本人が選んだ", "aka": False, "where": w or "honnin.jsonl",
                "at": at, "song_key": sk}
    if w:
        return {"dare": "機械が選んだ", "aka": True, "where": w, "at": at,
                "song_key": sk}
    return {"dare": "機械が選んだ", "aka": True,
            "where": "入れた係の記録なし（本人由来の記録も無い）", "at": "",
            "song_key": sk}


def fuda(d):
    """画面に出す1行。"""
    ato = []
    if d.get("where"):
        ato.append(d["where"])
    if d.get("at"):
        ato.append(d["at"])
    return "%s%s" % (d["dare"], ("（%s）" % " ・ ".join(ato)) if ato else "")


if __name__ == "__main__":
    h = hyou()
    print("台帳 %d 本（post_id つき）／本人の札 %d 件"
          % (len(h["by_post"]), len(h["honnin_post"]) + len(h["honnin_song"])))
    for k, (w, at) in list(h["by_song"].items())[:40]:
        print("  %-38s %s %s" % (k, w, at))
