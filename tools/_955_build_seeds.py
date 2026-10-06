#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""955番 — 案内人の「ごきげんの種」検証データを、実在する棚のカードから作る。

正本(status/952_seihon/concierge-concept-02-08.md)の合格条件:
  「音楽だけのサイト」に見えないこと／音楽以外のカテゴリも最低1回は見える検証データ。

架空のカードは1枚も作らない。joy-relief-station の origin/main に実在する
foodCards / danceCards / summerCards / extraCards をそのまま種にする。
（持ち帰りは tools/_952_data_fetch.py。工場Mac経由・読むだけ）
"""
import io, json, os, re
from collections import Counter

D = "status/952_seihon/data/"
OUT = "share/check/assets/955-concierge/seeds.json"
BASE = "https://joy-relief-station.lovable.app"

ROOM = {"foodCards.ts": "food", "danceCards.ts": "dance",
        "summerCards.ts": "summer", "extraCards.ts": "card"}

# カテゴリの決め方（タグの実物から引く。無ければ出どころのファイルで決める）
RULES = [
    ("animal", ("動物", "猫", "ねこ", "犬", "いぬ", "рыб", "ペンギン", "うさぎ", "カピバラ",
                "リス", "パンダ", "肉球", "鳥")),
    ("laugh",  ("笑い", "コント", "漫才", "ギャグ", "ずっこけ", "ギャップ")),
    ("travel", ("旅", "海外", "夜景", "街", "京都", "伊勢", "山梨", "温泉", "銭湯", "サウナ",
                "ドライブ", "海", "故郷")),
    ("food",   ("カレー", "food", "食", "料理", "菓子", "パン", "スパイス", "食文化", "塩",
                "おやつ", "甘い")),
    ("video",  ("ダンス", "名パフォーマンス", "勝手に体が動く棚", "フラッシュモブ")),
    ("word",   ("ことば", "手紙", "本", "詩", "豆知識", "読みもの")),
]


def objs(path):
    s = io.open(D + path, encoding="utf-8", errors="replace").read()
    out = []
    for m in re.finditer(r'\{[^{}]*?slug:\s*"([^"]+)"[^{}]*?\}', s, re.S):
        blk = m.group(0)
        def g(k):
            mm = re.search(k + r':\s*"((?:[^"\\]|\\.)*)"', blk)
            return mm.group(1).replace('\\"', '"') if mm else None
        tg = re.search(r'tags:\s*\[(.*?)\]', blk, re.S)
        out.append({"slug": m.group(1), "title": g("title"), "copy": g("copy"),
                    "yt": g("youtubeId"), "emoji": g("emoji"),
                    "tags": re.findall(r'"([^"]+)"', tg.group(1)) if tg else []})
    return [o for o in out if o["title"] and o["yt"]]


def category(src, o):
    hay = " ".join(o["tags"]) + " " + (o["title"] or "") + " " + (o["copy"] or "")
    for cat, keys in RULES:
        if any(k in hay for k in keys):
            return cat
    if src == "foodCards.ts":
        return "food"
    if src == "danceCards.ts":
        return "video"
    return "music"


def main():
    seeds = []
    for f, room in ROOM.items():
        if not os.path.isfile(D + f):
            continue
        for o in objs(f):
            cat = "food" if f == "foodCards.ts" else category(f, o)
            seeds.append({
                "id": room + "/" + o["slug"],
                "cat": cat,
                "title": o["title"],
                "copy": (o["copy"] or "")[:90],
                "yt": o["yt"],
                "url": "%s/room/%s/%s" % (BASE, room, o["slug"]),
                "tags": o["tags"][:6],
            })
    # 同じ動画を二度出さない
    seen, uniq = set(), []
    for s in seeds:
        if s["yt"] in seen:
            continue
        seen.add(s["yt"]); uniq.append(s)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps({"base": BASE, "n": len(uniq), "cards": uniq},
                   ensure_ascii=False, separators=(",", ":")))
    print("書きました %s / %d枚" % (OUT, len(uniq)))
    print(Counter(s["cat"] for s in uniq).most_common())


if __name__ == "__main__":
    main()
