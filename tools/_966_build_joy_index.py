#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""966番：7つの棚ぜんぶを案内人が引けるようにする。

■ なぜ作り直すか（2026-09-20 たまごさん実測）
  「動物は1枚も出してこない。料理は出せるんだけど、ダンスだとか動物がアクセスできないみたい。」

  原因は憶測ではなく実測で判った。**元データの写しが途中で切れていた。**
    本番 src/lib/worlds.ts      … 529,438バイト
    手元 status/952_seihon/data … 68,342バイト（＝13%しか無かった）
    本番 src/lib/extraCards.ts  … 191,568バイト／手元 67,475バイト
  worlds.ts の中で cute（動物）/ laugh（笑い）/ travel（旅）/ joy（ことば）の棚は
  ファイルの後半にある。だから切れた写しには**1枚も入っていなかった。**

  → tools/_966_build_region.py と同じ便（status/mac_jobs 経由・工場Mac側で git show）で
    全部を取り直した。置き場所は status/966_seihon/。

■ 出どころ
  どの札がどの世界のものかは、**worlds.ts 自身の world の入れ物**で決める。
  題名やコピーの部分一致で決めない（2026-09-19 実測：「クリスマス・イブ」が動物に、
  「盆踊り」がことばに化けた）。worlds.ts に載っていない extraCards は
  **タグの完全一致**だけで決める。どちらでも決まらないものは入れない。

出力: share/check/assets/953-songs/joy.json
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "status" / "966_seihon"
OUT = REPO / "share" / "check" / "assets" / "953-songs" / "joy.json"

WORLDS = ["music", "food", "cute", "laugh", "travel", "dance", "joy"]
KIND = {
    "music":  {"ja": "音楽",   "mark": "レコード"},
    "food":   {"ja": "食",     "mark": "皿"},
    "cute":   {"ja": "動物",   "mark": "肉球"},
    "laugh":  {"ja": "笑い",   "mark": "幕"},
    "travel": {"ja": "旅",     "mark": "切符"},
    "dance":  {"ja": "踊り",   "mark": "靴"},
    "joy":    {"ja": "ことば", "mark": "紙片"},
}

# extraCards のタグ → 棚。★ 完全一致だけ。部分一致で繋がない（憲法22）。
TAG2KIND = {
    "動物": "cute", "猫": "cute", "犬": "cute", "牛": "cute", "象": "cute",
    "牧場": "cute", "まる": "cute", "ゆるキャラ": "cute", "ペット": "cute",
    "笑い": "laugh", "コント": "laugh", "アニメコント": "laugh",
    "ナンセンス": "laugh", "お笑い": "laugh", "漫才": "laugh",
    "食": "food", "料理": "food", "カレー": "food", "インドカレー": "food",
    "食文化": "food", "飯テロ": "food", "肉": "food", "チャーハン": "food",
    "デザート": "food", "デカ盛り": "food", "町中華": "food", "厨房": "food",
    "レストラン": "food", "エンタメグルメ": "food", "スパイス": "food",
    "旅": "travel", "旅立ち": "travel", "絶景": "travel", "温泉": "travel",
    "宿": "travel", "銭湯": "travel", "サウナ": "travel",
    "ダンス": "dance", "名もなきダンサー": "dance", "踊る阿呆": "dance",
    "勝手に体が動く棚": "dance", "名パフォーマンス": "dance",
    "豆知識": "joy", "生活の知恵": "joy", "ライフハック": "joy",
    "昔ばなし": "joy", "ストーリー": "joy", "ことば": "joy",
}


def scan_obj(s, i):
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

    # ★ 入れ子を飛ばさない。棚（shelf）の中に札（card）が入っているので、
    #   「棚を1つ読んだら、その終わりまで飛ばす」書き方だと札を全部食べてしまう。
    #   2026-09-20 実測：これで「ことば」の棚が 1枚しか拾えていなかった（本当は8枚以上ある）。
    out = []
    for m in re.finditer(r'\{\s*id:\s*"', text):
        e = scan_obj(text, m.start())
        if e < 0:
            continue
        body = text[m.start():e + 1]
        if "cards:" in body or "shelves:" in body:
            continue          # これは入れ物。札ではない
        title = sfield(body, "title")
        to = sfield(body, "to")
        if not title or not to:
            continue
        out.append({"k": world_at(m.start()), "t": title,
                    "w": sfield(body, "whisper")[:90], "e": sfield(body, "emoji"),
                    "u": to, "i": sfield(body, "thumb")})
    return out


def read_cards(text, prefix, kind=None, tagmap=False):
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
        k = kind
        if tagmap:
            tg = re.search(r"tags:\s*\[(.*?)\]", body, re.S)
            tags = re.findall(r'"([^"]+)"', tg.group(1)) if tg else []
            hits = [TAG2KIND[t] for t in tags if t in TAG2KIND]
            if not hits:
                continue
            # 同じ札に複数のタグが付いていたら、いちばん多いものを採る
            k = max(set(hits), key=hits.count)
        yt = sfield(body, "youtubeId")
        thumb = sfield(body, "thumb") or (
            "https://img.youtube.com/vi/%s/hqdefault.jpg" % yt if yt else "")
        out.append({"k": k, "t": title,
                    "w": (sfield(body, "copy") or sfield(body, "note"))[:90],
                    "e": sfield(body, "emoji"), "u": prefix + slug, "i": thumb})
    return out


def main():
    f = SRC / "worlds.ts"
    if not f.exists():
        print("元データがまだ来ていない:", f)
        return 1
    rows = read_worlds(f.read_text(encoding="utf-8", errors="replace"))
    for name, prefix, kind, tagmap in [
        ("foodCards.ts", "/room/food/", "food", False),
        ("danceCards.ts", "/room/dance/", "dance", False),
        # summerCards は「夏に聴きたい曲」＝音楽。旅ではない
        ("summerCards.ts", "/room/summer/", "music", False),
        # extraCards は種類が混ざっているのでタグの完全一致だけで決める
        ("extraCards.ts", "/room/card/", None, True),
    ]:
        g = SRC / name
        if g.exists():
            rows += read_cards(g.read_text(encoding="utf-8", errors="replace"),
                               prefix, kind, tagmap)

    # ★ 同じ行き先でも棚が違えば別の1枚として残す。
    #   （「September」は音楽の棚にも喜びの棚にも踊りの棚にも置いてある。
    #     行き先だけで重複を消すと、後から来た棚が空になる）
    # ★ music は曲の索引（head.json・34,240曲）が別にあるので、ここには積まない。
    #   同じものを2回積むとスマホで読む量が3倍になる。
    seen, keep = set(), []
    for r in rows:
        k = (r["k"], r["u"])
        if not r["i"] or not r["k"] or r["k"] == "music" or k in seen:
            continue
        seen.add(k)
        keep.append(r)

    n_by = {}
    for r in keep:
        n_by[r["k"]] = n_by.get(r["k"], 0) + 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"base": "https://joy-relief-station.lovable.app",
                               "kind": KIND, "cards": keep},
                              ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    print("%d枚 → joy.json %.0fKB" % (len(keep), OUT.stat().st_size / 1024))
    for k in WORLDS:
        print("  %s: %d枚" % (KIND[k]["ja"], n_by.get(k, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
