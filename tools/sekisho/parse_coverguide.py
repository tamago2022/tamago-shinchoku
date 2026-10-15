# -*- coding: utf-8 -*-
"""coverGuide.ts から アーティスト → 曲 の対応を取り出すだけの読み取り器。書き換えはしない。"""
import re, json, sys

# アーティスト宣言：1行型（{ id:.., name:.., ... songs: [）と 複数行型の両対応
ART_1L = re.compile(r'\{\s*id:\s*"((?:[^"\\]|\\.)*)"\s*,\s*name:\s*"((?:[^"\\]|\\.)*)"')
ART_ML_ID = re.compile(r'^\s*id:\s*"((?:[^"\\]|\\.)*)"\s*,\s*$')
ART_ML_NAME = re.compile(r'^\s*name:\s*"((?:[^"\\]|\\.)*)"\s*,\s*$')
ALIAS_IN = re.compile(r'aliases:\s*\[([^\]]*)\]')
SONG = re.compile(r'\{\s*id:\s*"((?:[^"\\]|\\.)*)"\s*,\s*title:\s*"((?:[^"\\]|\\.)*)"')
STR = re.compile(r'"((?:[^"\\]|\\.)*)"')


def parse(path):
    lines = open(path, encoding="utf-8").read().split("\n")
    artists, cur = [], None
    for i, ln in enumerate(lines):
        new = None
        m = ART_1L.search(ln)
        if m and ("songs:" in ln or "about:" in ln or "aliases:" in ln):
            al = ALIAS_IN.search(ln)
            new = {"id": m.group(1), "name": m.group(2),
                   "aliases": STR.findall(al.group(1)) if al else [],
                   "line": i + 1, "songs": []}
        else:
            m = ART_ML_ID.match(ln)
            if m and i + 1 < len(lines):
                m2 = ART_ML_NAME.match(lines[i + 1])
                if m2:
                    al = ALIAS_IN.search("\n".join(lines[i + 2:i + 5]))
                    new = {"id": m.group(1), "name": m2.group(1),
                           "aliases": STR.findall(al.group(1)) if al else [],
                           "line": i + 1, "songs": []}
        if new:
            artists.append(new)
            cur = new
            rest = ln.split("songs:", 1)[1] if "songs:" in ln else ""
            for sm in SONG.finditer(rest):
                cur["songs"].append({"id": sm.group(1), "title": sm.group(2),
                                     "line": i + 1, "raw": ln.strip()})
            continue
        if cur is not None:
            for sm in SONG.finditer(ln):
                cur["songs"].append({"id": sm.group(1), "title": sm.group(2),
                                     "line": i + 1, "raw": ln.strip()})
    return artists


if __name__ == "__main__":
    a = parse(sys.argv[1])
    print(json.dumps({"artists": len(a), "songs": sum(len(x["songs"]) for x in a)}, ensure_ascii=False))
