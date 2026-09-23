# -*- coding: utf-8 -*-
"""1051番：関所が「保留」にした曲の youtubeId を取り出す（ファイルは触らない）。

gate_artist_song.py の保留一覧（--json で出たもの）と coverGuide.ts を突き合わせ、
  status/_1051/yt_ids.json   … 引く動画idの並び（YouTube APIに渡す）
  status/_1051/hold_map.json … 保留1件ごとに {artist, title, youtubeId, ...}
を書く。

なぜ曲名の行から直接拾わないか：
  1行に曲が2つ以上並ぶ行があるので、行ごとではなく**曲の{}ごと**に切って拾う。
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# 曲の{}ひとかたまり。id と title で始まるものだけ拾う。
SONG_OBJ = re.compile(
    r'\{\s*id:\s*"((?:[^"\\]|\\.)*)"\s*,\s*title:\s*"((?:[^"\\]|\\.)*)"(.*?)\}',
    re.S)
YT = re.compile(r'youtubeId:\s*"([\w-]{11})"')


def song_index(path):
    """(song_id, title) → [youtubeId...]  と、行番号つきの並び。"""
    text = open(path, encoding="utf-8").read()
    rows = []
    for m in SONG_OBJ.finditer(text):
        y = YT.search(m.group(3) or "")
        rows.append({
            "song_id": m.group(1),
            "title": m.group(2),
            "youtubeId": y.group(1) if y else "",
            "line": text.count("\n", 0, m.start()) + 1,
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", default="status/_1039/src_lib_coverGuide.ts")
    ap.add_argument("--sekisho", default="status/_1051/sekisho.json")
    ap.add_argument("--outdir", default="status/_1051")
    a = ap.parse_args()

    p = lambda x: x if os.path.isabs(x) else os.path.join(REPO, x)
    rows = song_index(p(a.ts))
    by_line = {}
    for r in rows:
        by_line.setdefault(r["line"], []).append(r)
    by_sid = {}
    for r in rows:
        by_sid.setdefault(r["song_id"], []).append(r)

    sek = json.load(open(p(a.sekisho), encoding="utf-8"))
    hold = sek.get("hold") or []

    out, miss = [], 0
    for h in hold:
        cand = [r for r in by_line.get(h["line"], [])
                if r["song_id"] == h["song_id"]]
        if not cand:
            cand = [r for r in by_sid.get(h["song_id"], [])
                    if r["title"] == h["title"]]
        if not cand:
            cand = by_sid.get(h["song_id"], [])
        vid = cand[0]["youtubeId"] if cand else ""
        if not vid:
            miss += 1
        out.append(dict(h, youtubeId=vid))

    os.makedirs(p(a.outdir), exist_ok=True)
    json.dump(out, open(os.path.join(p(a.outdir), "hold_map.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=1)
    ids = list(dict.fromkeys(r["youtubeId"] for r in out if r["youtubeId"]))
    json.dump(ids, open(os.path.join(p(a.outdir), "yt_ids.json"), "w",
                        encoding="utf-8"), ensure_ascii=False)
    print("保留 %d件 ／ 動画idが取れた %d件 ／ 取れない %d件 ／ 重複を除いた動画 %d本"
          % (len(out), len(out) - miss, miss, len(ids)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
