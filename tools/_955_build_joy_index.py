#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音楽以外の「ごきげんの種」を索引にする。

正本（concierge-concept-02-08.md §3）いわく、いちばん大事なのは
**「音楽しかない」と誤認させないこと。**
だから案内人が、食・動物・旅・笑い・踊り・ことばも同じ4枚の中に混ぜられるようにする。

元データ（別セッションが本番リポジトリから持ってきた写し）:
  worlds.ts      … 7つの世界（music/food/cute/laugh/travel/dance/joy）の棚と札
  foodCards.ts   … 食の部屋の札
  extraCards.ts  … 汎用カード

出力: share/check/assets/953-songs/joy.json
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "status" / "952_seihon" / "data"
OUT = REPO / "share" / "check" / "assets" / "953-songs" / "joy.json"

WORLDS = ["music", "food", "cute", "laugh", "travel", "dance", "joy"]
# 画面での見せ方（正本 §4 カテゴリごとの視覚言語）
KIND = {
    "music":  {"ja": "音楽",   "mark": "レコード"},
    "food":   {"ja": "食",     "mark": "皿"},
    "cute":   {"ja": "動物",   "mark": "肉球"},
    "laugh":  {"ja": "笑い",   "mark": "幕"},
    "travel": {"ja": "旅",     "mark": "切符"},
    "dance":  {"ja": "踊り",   "mark": "靴"},
    "joy":    {"ja": "ことば", "mark": "紙片"},
}


def scan_obj(s: str, i: int) -> int:
    depth, n, j = 0, len(s), i
    while j < n:
        c = s[j]
        if c in "\"'`":
            q = c
            j += 1
            while j < n:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == q:
                    break
                j += 1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return -1


def sfield(body, key):
    m = re.search(r'\b%s:\s*"((?:[^"\\]|\\.)*)"' % key, body)
    return re.sub(r"\\(.)", r"\1", m.group(1)) if m else ""


def read_worlds(text):
    """worlds.ts の札を、どの世界のものかを付けて取り出す。"""
    marks = []
    for w in WORLDS:
        for m in re.finditer(r"\n  %s:\s*\{" % w, text):
            marks.append((m.start(), w))
    marks.sort()
    if not marks:
        return []

    def world_at(pos):
        cur = marks[0][1]
        for p, w in marks:
            if p <= pos:
                cur = w
            else:
                break
        return cur

    out, j = [], 0
    for m in re.finditer(r'\{\s*id:\s*"', text):
        if m.start() < j:
            continue
        e = scan_obj(text, m.start())
        if e < 0:
            continue
        body = text[m.start():e + 1]
        j = e + 1
        title = sfield(body, "title")
        to = sfield(body, "to")
        if not title or not to:
            continue
        out.append({
            "k": world_at(m.start()),
            "t": title,
            "w": sfield(body, "whisper")[:90],
            "e": sfield(body, "emoji"),
            "u": to,
            "i": sfield(body, "thumb"),
        })
    return out


def read_cards(text, prefix, kind):
    """foodCards.ts / extraCards.ts のような slug ベースの札。"""
    out, j = [], 0
    for m in re.finditer(r'\{\s*slug:\s*"', text):
        if m.start() < j:
            continue
        e = scan_obj(text, m.start())
        if e < 0:
            continue
        body = text[m.start():e + 1]
        j = e + 1
        title = sfield(body, "title")
        slug = sfield(body, "slug")
        if not title or not slug:
            continue
        yt = sfield(body, "youtubeId")
        thumb = sfield(body, "thumb") or (
            f"https://img.youtube.com/vi/{yt}/hqdefault.jpg" if yt else "")
        out.append({
            "k": kind, "t": title,
            "w": (sfield(body, "copy") or sfield(body, "note"))[:90],
            "e": sfield(body, "emoji"),
            "u": prefix + slug, "i": thumb,
        })
    return out


def main():
    if not SRC.exists():
        print("元データがまだ来ていない:", SRC)
        return 1
    rows = []
    f = SRC / "worlds.ts"
    if f.exists():
        rows += read_worlds(f.read_text(encoding="utf-8", errors="replace"))
    for name, prefix, kind in [
        ("foodCards.ts", "/room/food/", "food"),
        # extraCards.ts は種類が混ざっていて（音楽の動画も入っている）、
        # 機械的に「ことば」と貼ると嘘になる。分類が取れるまで入れない。
        # 行き先とkindは、各ファイル自身のdocstringと本番ページで裏を取った値。
        #   /room/dance/d-soraki        … 200。パンくず「案内所トップ > 踊り」
        #   /room/summer/anri-windy-summer … 200。パンくず「案内所トップ > 音楽 > 夏の棚」
        # 以前は両方とも /room/card/ を貼っていて、本番に存在しない行き先だった（リンク切れ）。
        # summerCards は「夏に聴きたい曲」なので travel ではなく music。
        # 「旅に出たい」と言われて松田聖子が出る事故は、ここが原因だった。
        ("danceCards.ts", "/room/dance/", "dance"),
        ("summerCards.ts", "/room/summer/", "music"),
    ]:
        f = SRC / name
        if f.exists():
            rows += read_cards(f.read_text(encoding="utf-8", errors="replace"), prefix, kind)

    # 同じ行き先は1枚にする。絵が無い札は画面が寂しいので落とす。
    seen, keep = set(), []
    for r in rows:
        if not r["i"] or r["u"] in seen:
            continue
        seen.add(r["u"])
        keep.append(r)

    # 音楽は既に曲の索引がある。ここは「音楽以外」を厚くするための棚。
    n_by = {}
    for r in keep:
        n_by[r["k"]] = n_by.get(r["k"], 0) + 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"base": "https://joy-relief-station.lovable.app",
                               "kind": KIND, "cards": keep},
                              ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print(f"{len(keep)}枚 → joy.json {OUT.stat().st_size/1024:.0f}KB")
    for k in WORLDS:
        print(f"  {KIND[k]['ja']}: {n_by.get(k,0)}枚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
