# -*- coding: utf-8 -*-
"""coverGuide.ts を「アーティスト → 曲（属性つき）」に読み取るだけの器。書き換えはしない。

既存の parse_coverguide.py は id/title しか取らない。
棚（アーティストページ）と検索のズレを数えるには、棚側フィルタが見る属性
（youtubeId / altYoutubeIds / originalRef / hideFromArtistList）まで要る。

ブレース対応で物理的に切るので、1行型・複数行型・入れ子（pairedMedia等）が混ざっても崩れない。
"""
import json
import re
import sys


_TOK = re.compile(
    r'//[^\n]*'                      # 行コメント
    r'|/\*[\s\S]*?\*/'               # ブロックコメント
    # 正規表現リテラル。中にバッククォートや引用符が入る（実測：normalize() の
    # 記号クラスに ` が入っていて、ここから6500行が文字列扱いになり、
    # Enya・原田知世・George Winston など236棚が読み落とされていた）。
    r'|(?<=[(,=:\[!&|?{};+\-*%~^\s])/(?![/*])'
    r'(?:\[(?:[^\]\\\n]|\\.)*\]|[^/\\\n\[]|\\.)+/[gimsuy]*'
    r'|"(?:[^"\\\n]|\\.)*"'          # 二重引用符（JSは改行をまたげない）
    r'|\'(?:[^\'\\\n]|\\.)*\''       # 単引用符（同上）
    r'|`(?:[^`\\]|\\.)*`'            # テンプレート文字列
)


def _blank(s: str, keep_edges: bool) -> str:
    """中身を空白に潰す。改行だけは残す（行番号をずらさないため）。"""
    body = "".join(" " if c != "\n" else "\n" for c in s)
    if keep_edges and len(s) >= 2:
        return s[0] + body[1:-1] + s[-1]
    return body


def _strip_for_scan(src: str) -> str:
    """文字列・コメントの中身だけを空白に潰した走査用の写し。位置は元と1対1。

    引用符をまたいで対応がずれると棚がまるごと読み落とされる
    （実測：Enya と 原田知世 の2棚・40曲が消えていた）。
    JSの文字列は改行をまたげないので、そこで必ず切る。閉じられない引用符
    （歌詞の中の don't、T'en Va Pas）は文字列として扱わない。
    """
    out = []
    last = 0
    for m in _TOK.finditer(src):
        out.append(src[last:m.start()])
        tok = m.group(0)
        out.append(_blank(tok, keep_edges=tok[0] in "\"'`"))
        last = m.end()
    out.append(src[last:])
    return "".join(out)


def _strip_for_scan_old(src: str):
    """文字列リテラル・コメントの中を空白に潰した走査用の写しを作る。
    位置は元と1対1で保つ（オフセットがずれると切り出せないため）。"""
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # 文字列の囲みは " と ` だけを見る。coverGuide.ts のデータは全部 " 囲みで、
        # ' はコメントや歌詞の中のアポストロフィ（don't, T'en Va Pas）として出てくる。
        # ' を囲みとして扱うと、そこから先の対応がずれて棚がまるごと読み落とされる
        # （実測：Enya と 原田知世 の2棚・40曲が消えていた）。
        if c in "\"`":
            q = c
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == q:
                    break
                j += 1
            # 引用符そのものは残す（構造は潰さず中身だけ潰す）
            for k in range(i + 1, min(j, n)):
                out[k] = " "
            i = j + 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def _match_brace(scan: str, start: int) -> int:
    """scan[start] == '{' から対応する '}' の位置を返す。"""
    pairs = {"}": "{", "]": "["}
    stack = []
    for i in range(start, len(scan)):
        c = scan[i]
        if c in "{[":
            stack.append(c)
        elif c in "}]":
            if not stack or stack[-1] != pairs[c]:
                return -1          # 対応が壊れている。飲み込まずに諦める
            stack.pop()
            if not stack:
                return i
    return -1


STR = r'"((?:[^"\\]|\\.)*)"'
KEY_ID = re.compile(r'(?<![A-Za-z])id:\s*' + STR)
KEY_NAME = re.compile(r'(?<![A-Za-z])name:\s*' + STR)
KEY_TITLE = re.compile(r'(?<![A-Za-z])title:\s*' + STR)
KEY_YT = re.compile(r'(?<![A-Za-z])youtubeId:\s*' + STR)
KEY_ALT = re.compile(r'altYoutubeIds:\s*\[([^\]]*)\]')
KEY_ORIGREF = re.compile(r'originalRef:\s*\{')
KEY_HIDE = re.compile(r'hideFromArtistList:\s*true')
KEY_ALIAS = re.compile(r'aliases:\s*\[([^\]]*)\]')
ALLSTR = re.compile(STR)


def _unesc(s: str) -> str:
    return s.encode().decode("unicode_escape") if "\\u" in s else s.replace('\\"', '"')


def parse_deep(path: str):
    src = open(path, encoding="utf-8").read()
    scan = _strip_for_scan(src)
    line_of = [0] * (len(src) + 1)
    ln = 1
    for i, ch in enumerate(src):
        line_of[i] = ln
        if ch == "\n":
            ln += 1
    line_of[len(src)] = ln

    artists = []
    seen_spans = []
    # 「songs:」を見つけ、その外側のオブジェクト（＝アーティスト）を割り出す
    for m in re.finditer(r'(?<![A-Za-z])songs:\s*\[', scan):
        # 外側のアーティストオブジェクトの '{' を左に探す
        depth = 0
        j = m.start() - 1
        obj_start = -1
        while j >= 0:
            c = scan[j]
            if c in "}]":
                depth += 1
            elif c in "{[":
                if depth == 0:
                    if c == "{":
                        obj_start = j
                    break
                depth -= 1
            j -= 1
        if obj_start < 0:
            continue
        obj_end = _match_brace(scan, obj_start)
        if obj_end < 0:
            continue
        head = scan[obj_start:m.start()]
        mid = KEY_ID.search(head)
        mnm = KEY_NAME.search(head)
        if not mid or not mnm:
            continue
        aid = _unesc(src[obj_start:m.start()][mid.start(1):mid.end(1)])
        anm = _unesc(src[obj_start:m.start()][mnm.start(1):mnm.end(1)])
        mal = KEY_ALIAS.search(head)
        aliases = []
        if mal:
            seg = src[obj_start + mal.start(1):obj_start + mal.end(1)]
            aliases = [_unesc(x) for x in ALLSTR.findall(seg)]

        # songs 配列を物理で切る
        arr_start = m.end() - 1
        arr_end = _match_brace(scan, arr_start)
        if arr_end < 0:
            continue
        songs = []
        k = arr_start + 1
        while k < arr_end:
            if scan[k] == "{":
                s_end = _match_brace(scan, k)
                if s_end < 0 or s_end > arr_end:
                    break
                body_scan = scan[k:s_end + 1]
                body_src = src[k:s_end + 1]
                sid_m = KEY_ID.search(body_scan)
                st_m = KEY_TITLE.search(body_scan)
                if sid_m and st_m:
                    yt_m = KEY_YT.search(body_scan)
                    alt_m = KEY_ALT.search(body_scan)
                    alts = []
                    if alt_m:
                        alts = [_unesc(x) for x in ALLSTR.findall(
                            body_src[alt_m.start(1):alt_m.end(1)])]
                    songs.append({
                        "id": _unesc(body_src[sid_m.start(1):sid_m.end(1)]),
                        "title": _unesc(body_src[st_m.start(1):st_m.end(1)]),
                        "youtubeId": _unesc(body_src[yt_m.start(1):yt_m.end(1)]) if yt_m else None,
                        "altYoutubeIds": alts,
                        "originalRef": bool(KEY_ORIGREF.search(body_scan)),
                        "hideFromArtistList": bool(KEY_HIDE.search(body_scan)),
                        "line": line_of[k],
                    })
                k = s_end + 1
                continue
            k += 1
        seen_spans.append((obj_start, obj_end))
        artists.append({"id": aid, "name": anm, "aliases": aliases,
                        "line": line_of[obj_start], "songs": songs})
    return artists


def parse_curated_with_video(path: str):
    """curated / curatedGenerated の "artistId/songId" のうち
    officialVideos に id があるキーの集合を返す（棚の再生可否判定に要る）。"""
    src = open(path, encoding="utf-8").read()
    scan = _strip_for_scan(src)
    keys = set()
    for m in re.finditer(r'^\s*' + STR + r'\s*:\s*\{', src, re.M):
        key = _unesc(m.group(1))
        if "/" not in key:
            continue
        b = scan.find("{", m.start())
        e = _match_brace(scan, b)
        if e < 0:
            continue
        body = scan[b:e + 1]
        mo = re.search(r'officialVideos:\s*\[', body)
        if not mo:
            continue
        ab = b + mo.end() - 1
        ae = _match_brace(scan, ab)
        if ae < 0:
            continue
        if re.search(r'(?<![A-Za-z])id:\s*"', src[ab:ae + 1]):
            keys.add(key)
    return keys


if __name__ == "__main__":
    arts = parse_deep(sys.argv[1])
    print(json.dumps({"artists": len(arts),
                      "songs": sum(len(a["songs"]) for a in arts)},
                     ensure_ascii=False))
