#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-11 入荷（たまごさんのリスト約85曲のうち、在庫に無かった分）を coverGuide.ts に入れる。

たまごさんの言葉：「下のリストの曲を、サイトの在庫に無いものだけ全部入荷する（重複は入れない）。
  名カバーの棚には入れない。ほかの棚にも入れない（曲ページを作るだけ）。」

- 入れる中身は status/nyuka_1011/nyuka.json（判定・証拠つき）。この道具は何度走らせても同じ結果（冪等）。
  同じ動画IDが既にファイルにあれば入れない＝重複ゼロを機械で守る。
- 既存アーティストの曲は、そのアーティストの songs の末尾へ。新しいアーティストは nyuka1011Batch にまとめる。
- 棚（worlds/shelves）には一切触らない。ownerAdded: true（店主の指示で入れた曲の印）を付ける。
- 関所 sekisho-artist-song：米倉利徳の棚にあった久保田利伸「Missing」（久保田本人の公式動画）は、消さずに久保田の棚へ移す。
  控えは status/nyuka_1011/nyuka.json の moved に残す。

  python3 tools/nyuka_1011_ireru.py <coverGuide.ts>          # 書き換える
  python3 tools/nyuka_1011_ireru.py <coverGuide.ts> --dry-run
  python3 tools/nyuka_1011_ireru.py --self-test
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA = os.path.join(REPO, "status", "nyuka_1011", "nyuka.json")


def js(s):
    return json.dumps(s, ensure_ascii=False)


def song_line(s):
    return '    { id: %s, title: %s, note: "", youtubeId: %s, ownerAdded: true }' % (js(s["song_id"]), js(s["title"]), js(s["youtubeId"]))


def match_bracket(text, i):
    """text[i] が '[' か '{'。文字列とコメントを飛ばして対応する閉じ括弧の位置を返す。"""
    pairs = {"[": "]", "{": "}"}
    stack = []
    j = i
    n = len(text)
    while j < n:
        c = text[j]
        if c in "\"'`":
            q = c
            j += 1
            while j < n and text[j] != q:
                if text[j] == "\\":
                    j += 1
                j += 1
        elif c == "/" and text[j + 1:j + 2] == "/":
            j = text.index("\n", j)
            continue
        elif c == "/" and text[j + 1:j + 2] == "*":
            j = text.index("*/", j) + 1
        elif c in pairs:
            stack.append(pairs[c])
        elif c in "]}":
            if not stack or stack.pop() != c:
                raise ValueError("括弧が合わない at %d" % j)
            if not stack:
                return j
        j += 1
    raise ValueError("閉じ括弧が無い")


def songs_close(text, aid):
    m = re.search(r'^  \{ id: "%s",' % re.escape(aid), text, re.M)
    if not m:
        m = re.search(r'^  \{\n\s+id: "%s",' % re.escape(aid), text, re.M)
    if not m:
        raise KeyError(aid)
    k = text.index("songs: [", m.start())
    b = k + len("songs: ")
    return match_bracket(text, b)


def insert_into(text, aid, lines):
    close = songs_close(text, aid)
    before = text[:close].rstrip()
    sep = "," if before.endswith("}") else ""
    return before + sep + "\n" + ",\n".join(lines) + "\n  " + text[close:]


def apply(text, data):
    log = []
    have = set(re.findall(r'youtubeId: "([A-Za-z0-9_-]{11})"', text))
    # 1) 移す（消さずに移す）
    for mv in data.get("moved", []):
        pat = re.compile(r'^\s*\{ id: %s,[^\n]*youtubeId: "%s"[^\n]*\},?\n' % (re.escape(js(mv["from_song_id"])), mv["youtubeId"]), re.M)
        if pat.search(text):
            text = pat.sub("", text, count=1)
            text = insert_into(text, mv["to_artist_id"], [song_line({"song_id": mv["to_song_id"], "title": mv["title"], "youtubeId": mv["youtubeId"]})])
            log.append("移した %s → %s/%s" % (mv["from_artist_id"], mv["to_artist_id"], mv["to_song_id"]))
    have = set(re.findall(r'youtubeId: "([A-Za-z0-9_-]{11})"', text))
    # 2) 既存アーティストへ
    by = {}
    for s in data["new_songs"]:
        if s["youtubeId"] in have:
            log.append("既にある（入れない） %s" % s["youtubeId"])
            continue
        if not s.get("new_artist"):
            by.setdefault(s["artist_id"], []).append(song_line(s))
    for aid, lines in by.items():
        text = insert_into(text, aid, lines)
        log.append("%s に %d 曲" % (aid, len(lines)))
    # 3) 新しいアーティスト
    if "const nyuka1011Batch" not in text:
        arts = {}
        for s in data["new_songs"]:
            if s.get("new_artist") and s["youtubeId"] not in have:
                a = arts.setdefault(s["artist_id"], {"s": s, "lines": []})
                a["lines"].append(song_line(s))
        if arts:
            blk = ["", "// 2026-10-11 入荷（たまごさんのリスト・在庫に無かった分。棚には入れない＝曲ページとアーティストページだけ）",
                   "// 動画の証拠（チャンネル名・ID）は tamago-shinchoku/status/nyuka_1011/nyuka.json。tools/nyuka_1011_ireru.py が入れた。",
                   "const nyuka1011Batch: CoverGuideArtist[] = ["]
            for aid, a in arts.items():
                s = a["s"]
                blk.append('  { id: %s, name: %s, aliases: %s, eras: %s, songs: [' % (js(aid), js(s["artist"]), js(s.get("aliases") or []), js(s.get("eras") or [])))
                blk.append(",\n".join(a["lines"]))
                blk.append("  ]},")
            blk.append("];")
            blk.append("artists.push(...nyuka1011Batch);")
            anchor = "artists.push(...omarBatch);"
            i = text.index(anchor) + len(anchor)
            text = text[:i] + "\n" + "\n".join(blk) + text[i:]
            log.append("新しいアーティスト %d 組" % len(arts))
    return text, log


def self_test():
    t = ('export const artists = [\n  { id: "a", name: "A", aliases: [], songs: [\n    { id: "x", title: "x]", note: "", youtubeId: "AAAAAAAAAAA" },\n  ]},\n'
         '  { id: "y", name: "Y", aliases: [], songs: [\n    { id: "m", title: "M", note: "", youtubeId: "MMMMMMMMMMM" }\n  ]},\n];\nartists.push(...omarBatch);\n')
    d = {"moved": [{"from_artist_id": "y", "from_song_id": "m", "to_artist_id": "a", "to_song_id": "m2", "title": "M", "youtubeId": "MMMMMMMMMMM"}],
         "new_songs": [{"artist_id": "a", "song_id": "z", "title": "Z", "youtubeId": "ZZZZZZZZZZZ"},
                       {"artist_id": "a", "song_id": "dup", "title": "D", "youtubeId": "AAAAAAAAAAA"},
                       {"artist_id": "n", "artist": "N", "new_artist": True, "song_id": "q", "title": "Q", "youtubeId": "QQQQQQQQQQQ"}]}
    out, log = apply(t, d)
    out2, _ = apply(out, d)
    ok = (out.count("ZZZZZZZZZZZ") == 1 and out.count("MMMMMMMMMMM") == 1 and out.count("QQQQQQQQQQQ") == 1
          and out.count("AAAAAAAAAAA") == 1 and out2 == out and 'id: "m2"' in out)
    print("self-test", "OK" if ok else "NG", log)
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--self-test":
        sys.exit(self_test())
    p = a[0]
    text = io.open(p, encoding="utf-8").read()
    data = json.load(io.open(DATA, encoding="utf-8"))
    out, log = apply(text, data)
    print("\n".join(log))
    if "--dry-run" not in a and out != text:
        io.open(p, "w", encoding="utf-8").write(out)
        print("書き換えた", p)
