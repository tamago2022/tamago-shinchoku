#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1092番【曲ページに飛べないカードを直す】

実測（2026-09-24）:
  棚に貼ってあるURL 754件のうち **45件が曲ページにならず、アーティストページに落ちていた。**
  判定は canonical を見て行った（`&song=` が消えていたら落ちている）。

直し方は2通りだけ。★1行も消さない。
  ① 同じ動画IDの曲が、そのアーティストの棚に既にある
     → カードの行き先（worlds.ts の to:）を、その正しいスラッグに**書き替える**。
  ② 棚にその曲が無いが、カードは動画IDと題名を持っている
     → その曲を**そのアーティストの棚に足す**（id＝いま貼られているスラッグ・題名＝カードの題名）。
       ＝いま存在しないURLが、そのまま生きるようになる。他人の行は1文字も触らない。
  ③ そもそもアーティストが棚にいない → ★保留。一覧に残す。勝手に人を作らない
     （関所 sekisho-artist-song：名前が似ているだけで別人の棚に入れる事故を止めるため）。

使い方（Macの上）:
    python3 tools/kareha_naosu.py --an     # 案を出すだけ（1文字も書き替えない）
    python3 tools/kareha_naosu.py --yaru   # 実際に書き替える（git は触らない）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
OUTDIR = os.path.join(REPO, "status", "1092_url_zure")
SRC_CANDIDATES = ["/tmp/jrs-pub/src/lib", "/Users/mac/Desktop/joy-relief-station/src/lib",
                  os.path.join(REPO, "status", "_1039", "lib")]

CARD = re.compile(r'\{(?:[^{}]|\{[^{}]*\})*?to:\s*"(/cover-guide\?artist=[^"]+)"(?:[^{}]|\{[^{}]*\})*?\}', re.S)
VID = re.compile(r'(?:youtube\.com/vi/|youtu\.be/|/vi/)([A-Za-z0-9_\-]{11})')
VID2 = re.compile(r'youtubeId:\s*"([A-Za-z0-9_\-]{11})"')
TITLE = re.compile(r'title:\s*"((?:[^"\\]|\\.)*)"')


def srcdir():
    for d in SRC_CANDIDATES:
        if os.path.isfile(os.path.join(d, "coverGuide.ts")):
            return d
    raise SystemExit("coverGuide.ts が見つかりません")


def load():
    import tsunagatte_nai as T
    d = srcdir()
    cg = open(os.path.join(d, "coverGuide.ts"), encoding="utf-8").read()
    arts = T.parse_artists(cg)
    return d, cg, arts


def cards(text):
    """to: のURLごとに、カードが持っている動画IDと題名を拾う。"""
    out = {}
    for m in CARD.finditer(text):
        blk, to = m.group(0), m.group(1)
        v = VID.search(blk) or VID2.search(blk)
        t = TITLE.search(blk)
        rec = out.setdefault(to, {"vids": set(), "titles": set()})
        if v:
            rec["vids"].add(v.group(1))
        if t:
            rec["titles"].add(t.group(1))
    return out


def clean_title(t, artist_name):
    """カードの題名から、アーティスト名の飾りだけ落とす。中身は変えない。"""
    a = re.escape(artist_name)
    t = re.sub(r"^\s*%s\s*[—\-–:：]\s*" % a, "", t).strip()
    t = re.sub(r"\s*[／/]\s*%s\s*$" % a, "", t).strip()
    m = re.match(r"^\s*%s\s*[「『](.+?)[」』]\s*(.*)$" % a, t)
    if m:
        t = (m.group(1) + (" " + m.group(2) if m.group(2) else "")).strip()
    return t or artist_name


def plan():
    d, cg, arts = load()
    byid = {a["id"]: a for a in arts}
    yt = {}
    for a in arts:
        for s in a["songs"]:
            if s.get("youtubeId"):
                yt.setdefault(a["id"], {}).setdefault(s["youtubeId"], s["id"])
    wpath = os.path.join(d, "worlds.ts")
    w = open(wpath, encoding="utf-8").read()
    cmap = cards(w)
    kekka = os.path.join(OUTDIR, "links_kekka.jsonl")
    zure = [json.loads(l) for l in open(kekka, encoding="utf-8")]
    zure = [r for r in zure if r.get("hantei") == "zure"]
    kakikae, tasu, horyuu = [], [], []
    for r in zure:
        a, s = r["artist"], r["song"]
        to = f"/cover-guide?artist={a}&song={s}"
        c = cmap.get(to, {"vids": set(), "titles": set()})
        vids, titles = sorted(c["vids"]), sorted(c["titles"])
        if a not in byid:
            horyuu.append({**r, "riyuu": "アーティストが棚にいない", "vids": vids})
            continue
        hit = next((yt.get(a, {}).get(v) for v in vids if yt.get(a, {}).get(v)), None)
        if hit:
            kakikae.append({"artist": a, "old": s, "new": hit, "to": to})
        elif vids and titles:
            tasu.append({"artist": a, "song": s, "youtubeId": vids[0],
                         "title": clean_title(titles[0], byid[a]["name"])})
        else:
            horyuu.append({**r, "riyuu": "動画IDか題名がカードに無い", "vids": vids})
    return d, wpath, w, cg, byid, kakikae, tasu, horyuu


def cmd(yaru: bool):
    d, wpath, w, cg, byid, kakikae, tasu, horyuu = plan()
    os.makedirs(OUTDIR, exist_ok=True)
    json.dump({"書き替え": kakikae, "棚に足す": tasu, "保留": horyuu},
              open(os.path.join(OUTDIR, "naoshi_an.json"), "w"), ensure_ascii=False, indent=1)
    print(f"元: {d}")
    print(f"① カードの行き先を正しいスラッグへ書き替え : {len(kakikae)}件")
    print(f"② 棚にその曲を足す（id＝今のURLのまま）     : {len(tasu)}件")
    print(f"③ 保留（勝手に直さない）                    : {len(horyuu)}件")
    if not yaru:
        print("→ 案のみ。1文字も書き替えていません。 status/1092_url_zure/naoshi_an.json")
        return
    # ① worlds.ts の to: を書き替える
    n1 = 0
    for k in kakikae:
        old = f'"/cover-guide?artist={k["artist"]}&song={k["old"]}"'
        new = f'"/cover-guide?artist={k["artist"]}&song={k["new"]}"'
        if old in w:
            w = w.replace(old, new)
            n1 += 1
    if n1:
        open(wpath, "w", encoding="utf-8").write(w)
    # ② coverGuide.ts のそのアーティストの songs: [ の直後に1行足す
    n2 = 0
    for t in tasu:
        m = re.search(r'\{\s*id:\s*"%s",\s*name:\s*"(?:[^"\\]|\\.)*"[^\n]*?songs:\s*\[' % re.escape(t["artist"]), cg)
        if not m:
            horyuu.append({**t, "riyuu": "棚の中にその人の songs: [ が見つからない"})
            continue
        title = t["title"].replace('"', '\\"')
        row = ('\n    { id: "%s", title: "%s", note: "", youtubeId: "%s" },'
               % (t["song"], title, t["youtubeId"]))
        cg = cg[:m.end()] + row + cg[m.end():]
        n2 += 1
    if n2:
        open(os.path.join(d, "coverGuide.ts"), "w", encoding="utf-8").write(cg)
    # 確かめ：足したものが本当に棚に居るか、もう1回読み直して数える
    import tsunagatte_nai as T
    arts2 = T.parse_artists(open(os.path.join(d, "coverGuide.ts"), encoding="utf-8").read())
    shelf2 = {a["id"]: set(s["id"] for s in a["songs"]) for a in arts2}
    nokori = [t for t in tasu if t["song"] not in shelf2.get(t["artist"], set())]
    print(f"書き替えた: {n1}件 / 棚に足した: {n2}件 / 足したのに入っていない: {len(nokori)}件")
    print(f"読み直し: アーティスト{len(arts2)}・曲{sum(len(a['songs']) for a in arts2)}")
    json.dump({"書き替えた": n1, "足した": n2, "保留": horyuu, "入らなかった": nokori},
              open(os.path.join(OUTDIR, "naoshi_kekka.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--an", action="store_true")
    ap.add_argument("--yaru", action="store_true")
    a = ap.parse_args()
    cmd(a.yaru)
