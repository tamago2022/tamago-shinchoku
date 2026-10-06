# -*- coding: utf-8 -*-
"""関所Aで落ちた「別人の曲」を、アーティストページ本体から外す。

消さない。外すだけ。外した中身は 移送控え(.moved.json) に丸ごと残す。
本人のページが既にある曲（矢野顕子の Rydeen など）は、そちらに同じ曲があるので
本体から抜くだけで「移した」ことになる。無い場合は控えを見て関連枠へ入れる。

使い方:
  python3 tools/sekisho/gate_artist_song.py <coverGuide.ts> --json /tmp/sekisho.json
  python3 tools/sekisho/remove_foreign_songs.py <coverGuide.ts> /tmp/sekisho.json
  python3 tools/sekisho/remove_foreign_songs.py <coverGuide.ts> /tmp/sekisho.json --apply
"""
import json
import re
import sys


def song_span(line: str, song_id: str):
    """行の中から、その曲のオブジェクト literal `{ ... }` の範囲を返す。"""
    key = 'id: "%s"' % song_id
    pos = line.find(key)
    if pos < 0:
        return None
    start = line.rfind("{", 0, pos)
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(line)):
        if line[i] == "{":
            depth += 1
        elif line[i] == "}":
            depth -= 1
            if depth == 0:
                return (start, i + 1)
    return None


def main():
    path, report = sys.argv[1], sys.argv[2]
    apply = "--apply" in sys.argv
    data = json.load(open(report, encoding="utf-8"))
    targets = data["blocked"]                      # 関所A（確定の別人）だけ外す
    if "--include-hold" in sys.argv:
        targets = targets + data["hold"]

    lines = open(path, encoding="utf-8").read().split("\n")
    moved, missed = [], []
    # 同じ行に複数曲があるので、行ごとに後ろから消す
    by_line = {}
    for t in targets:
        by_line.setdefault(t["line"], []).append(t)

    for ln, items in by_line.items():
        line = lines[ln - 1]
        spans = []
        for t in items:
            sp = song_span(line, t["song_id"])
            if sp is None:
                missed.append(t)
                continue
            spans.append((sp, t))
        for (s, e), t in sorted(spans, key=lambda x: -x[0][0]):
            t = dict(t)
            t["removed_literal"] = line[s:e]
            moved.append(t)
            tail = line[e:]
            cut = len(tail) - len(tail.lstrip(" ,"))   # 後ろのカンマも一緒に外す
            line = line[:s].rstrip().rstrip(",") + ("," if line[:s].rstrip().endswith(",") else "") + tail[cut:]
            line = re.sub(r",\s*,", ",", line)
            line = re.sub(r"\[\s*,", "[", line)
            line = re.sub(r",\s*\]", " ]", line)
        lines[ln - 1] = line

    out = "\n".join(lines)
    print("外す対象: %d 件 / 外せた: %d 件 / 行が見つからず保留: %d 件"
          % (len(targets), len(moved), len(missed)))
    for m in moved:
        print("  外す: %s の棚から「%s」（本来 %s）"
              % (m["artist"], m["title"], "/".join(m["other"])))

    if apply:
        open(path + ".bak", "w", encoding="utf-8").write(
            open(path, encoding="utf-8").read())
        open(path, "w", encoding="utf-8").write(out)
        open(path + ".moved.json", "w", encoding="utf-8").write(
            json.dumps({"moved": moved, "missed": missed},
                       ensure_ascii=False, indent=2))
        print("→ 反映しました。控え: %s.moved.json / 元: %s.bak" % (path, path))
    else:
        print("→ 下見のみ。反映するには --apply を付けてください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
