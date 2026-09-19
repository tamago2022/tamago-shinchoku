#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""957番 — 案内人の「ごきげんの種」検証データを、実在する棚のカードから作る。

正本(status/952_seihon/concierge-concept-02-08.md)の合格条件:
  「音楽だけのサイト」に見えないこと／音楽以外のカテゴリも最低1回は見える検証データ。

架空のカードは1枚も作らない。joy-relief-station の origin/main に実在する
foodCards / danceCards / summerCards / extraCards をそのまま種にする。
（持ち帰りは tools/_952_data_fetch.py。工場Mac経由・読むだけ）

★カテゴリはタグの「完全一致」だけで決める。
  題名やコピーの部分一致で決めると、山下達郎「クリスマス・イブ」が動物に、
  「盆踊り」がことばに化けた（2026-09-19 実測）。分からないものは出どころで決める。
"""
import io
import json
import os
import re
from collections import Counter

D = "status/952_seihon/data/"
OUT = "share/check/assets/957-concierge/seeds.json"
BASE = "https://joy-relief-station.lovable.app"

ROOM = {"foodCards.ts": "food", "danceCards.ts": "dance",
        "summerCards.ts": "summer", "extraCards.ts": "card"}

TAG2CAT = {
    "動物": "animal", "猫": "animal", "牛": "animal", "象": "animal",
    "牧場": "animal", "まる": "animal", "ゆるキャラ": "animal",
    "笑い": "laugh", "コント": "laugh", "アニメコント": "laugh",
    "ナンセンス": "laugh",
    "カレー": "food", "インドカレー": "food", "料理": "food", "食": "food",
    "食文化": "food", "飯テロ": "food", "肉": "food", "チャーハン": "food",
    "デザート": "food", "デカ盛り": "food", "町中華": "food", "厨房": "food",
    "レストラン": "food", "エンタメグルメ": "food", "スパイス": "food", "Alinea": "food",
    "旅": "travel", "旅立ち": "travel", "絶景": "travel", "香港映画": "travel",
    "豆知識": "word", "生活の知恵": "word", "ライフハック": "word",
    "昔ばなし": "word", "ストーリー": "word",
    "ダンス": "video", "名もなきダンサー": "video", "踊る阿呆": "video",
    "勝手に体が動く棚": "video", "名パフォーマンス": "video", "路上": "video",
    "密着": "video", "映画": "video", "伝説の動画": "video",
}
CAT_ORDER = ["animal", "laugh", "food", "travel", "word", "video"]


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
                    "yt": g("youtubeId"),
                    "tags": re.findall(r'"([^"]+)"', tg.group(1)) if tg else []})
    return [o for o in out if o["title"] and o["yt"]]


def category(src, o):
    hit = {TAG2CAT[t] for t in o["tags"] if t in TAG2CAT}
    for c in CAT_ORDER:
        if c in hit:
            return c
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
            seeds.append({
                "id": room + "/" + o["slug"],
                "cat": category(f, o),
                "title": o["title"],
                "copy": (o["copy"] or "")[:90],
                "yt": o["yt"],
                "url": "%s/room/%s/%s" % (BASE, room, o["slug"]),
                "tags": o["tags"][:6],
            })
    seen, uniq = set(), []
    for s in seeds:
        if s["yt"] in seen:
            continue
        seen.add(s["yt"])
        uniq.append(s)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps({"base": BASE, "n": len(uniq), "cards": uniq},
                   ensure_ascii=False, separators=(",", ":")))
    print("書きました %s / %d枚" % (OUT, len(uniq)))
    print(Counter(s["cat"] for s in uniq).most_common())


if __name__ == "__main__":
    main()
