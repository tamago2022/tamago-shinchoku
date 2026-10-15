#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★1051番【出庫係】魂を、脳から独立した1枚のデータに抜き出す係。

━━ なぜ作ったか（2026-09-24・たまごさん）━━

  「基礎AIを自前で作ってはいけない。ごきげん補給所が持つべき資産は
    『何を出せば、この人が少しごきげんになるか』という選球眼とデータ。
    モデルは交換部品にする。」

  いまの案内人（voiceConcierge.ts）は、**脳と魂が1本のコードに混ざっている。**
  xAIのWebSocketの話と、どの曲を出すかの話が、同じファイルに同居している。
  この形だと、脳を替えるたびに魂を書き写すことになる。写すたびに劣化する。

  だからここで **魂だけを引き剥がして、1枚のJSONにする。**
  脳は1バイトも知らなくていい。JSONを読むだけ。

━━ この係がやること ━━

  読む（本番のソースそのまま。書き換えない）:
    status/_1039/lib/coverGuide.ts          … 100人のアーティストと曲・うんちく
    status/_1039/lib/worldMeta.ts           … 棚（音楽・食・かわいい・笑い・旅・踊り・ごきげん）

  出す:
    tamashii/data/tamashii.json             … 魂の本体（アーティスト・曲・棚）
    tamashii/data/tamashii.meta.json        … いつ・どのファイルの何行から取ったか（出典）

  ★AIを1回も呼ばない。★1円もかからない。★毎回同じ答えが出る。
  ★取れなかったものは空欄にする。推測で埋めない（憲法・§11-3）。

━━ 使い方 ━━

    python3 tamashii/shukkoshi.py
    python3 tamashii/shukkoshi.py --self-test
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
JST = timezone(timedelta(hours=9))

SRC_COVER = os.path.join(REPO, "status", "_1039", "lib", "coverGuide.ts")
SRC_WORLD = os.path.join(REPO, "status", "_1039", "lib", "worldMeta.ts")

OUT_DIR = os.path.join(HERE, "data")
OUT_JSON = os.path.join(OUT_DIR, "tamashii.json")
OUT_META = os.path.join(OUT_DIR, "tamashii.meta.json")


# ──────────────────────────────────────────────────────────────
# JSオブジェクトリテラルを、そこだけ読む小さな読み取り器
#   （TypeScript全体を解釈しない。{ ... } の中の key: value だけを見る）
#   文字列の中の } や " に引っかからないよう、引用符を数えながら進む。
# ──────────────────────────────────────────────────────────────
def _skip_string(s: str, i: int) -> int:
    """s[i] が引用符のとき、その文字列の終わりの次の位置を返す。"""
    q = s[i]
    i += 1
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == q:
            return i + 1
        i += 1
    return i


def _match_brace(s: str, start: int) -> int:
    """s[start] == '{' のとき、対応する '}' の位置を返す。見つからなければ -1。"""
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c in "\"'`":
            i = _skip_string(s, i)
            continue
        if c == "{" or c == "[":
            depth += 1
        elif c == "}" or c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


_KEY = re.compile(r'(?:^|[{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:')


def _read_value(s: str, i: int):
    """s[i] から値を1つ読んで (値, 次の位置) を返す。"""
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    if i >= len(s):
        return None, i
    c = s[i]
    if c in "\"'":
        j = _skip_string(s, i)
        raw = s[i + 1 : j - 1]
        return _unescape(raw), j
    if c == "[" or c == "{":
        j = _match_brace(s, i)
        if j < 0:
            return None, len(s)
        return s[i : j + 1], j + 1
    # 数値・true・false・null・識別子
    j = i
    while j < len(s) and s[j] not in ",}\n":
        j += 1
    tok = s[i:j].strip()
    if tok == "true":
        return True, j
    if tok == "false":
        return False, j
    if re.fullmatch(r"-?\d+", tok):
        return int(tok), j
    if re.fullmatch(r"-?\d+\.\d+", tok):
        return float(tok), j
    return tok or None, j


def _unescape(raw: str) -> str:
    out = []
    i = 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):
            n = raw[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "'": "'", "\\": "\\"}.get(n, n))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def parse_obj(block: str) -> dict:
    """'{ ... }' 1つぶんの文字列から、トップレベルの key: value を辞書にする。"""
    assert block.startswith("{")
    inner = block
    fields: dict = {}
    i = 1
    end = len(inner) - 1
    while i < end:
        c = inner[i]
        if c in "\"'`":
            i = _skip_string(inner, i)
            continue
        if c in "{[":
            i = _match_brace(inner, i) + 1
            continue
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", inner[i:])
        if m:
            key = m.group(1)
            val, i = _read_value(inner, i + m.end())
            if key not in fields:
                fields[key] = val
            continue
        i += 1
    return fields


def parse_str_array(raw) -> list:
    """'["a","b"]' → ['a','b']。文字列以外・空は []。"""
    if not isinstance(raw, str) or not raw.startswith("["):
        return []
    out = []
    i = 1
    while i < len(raw) - 1:
        c = raw[i]
        if c in "\"'":
            j = _skip_string(raw, i)
            out.append(_unescape(raw[i + 1 : j - 1]))
            i = j
            continue
        i += 1
    return out


def parse_obj_array(raw) -> list:
    """'[{..},{..}]' → [ {..}, {..} ]（それぞれ parse_obj した辞書）。"""
    if not isinstance(raw, str) or not raw.startswith("["):
        return []
    out = []
    i = 1
    while i < len(raw) - 1:
        c = raw[i]
        if c in "\"'`":
            i = _skip_string(raw, i)
            continue
        if c == "{":
            j = _match_brace(raw, i)
            if j < 0:
                break
            out.append(parse_obj(raw[i : j + 1]))
            i = j + 1
            continue
        i += 1
    return out


# ──────────────────────────────────────────────────────────────
# アーティストと曲を抜く
# ──────────────────────────────────────────────────────────────
def extract_artists(text: str) -> list:
    """`export const artists: CoverGuideArtist[] = [ ... ]` の中身を読む。"""
    m = re.search(r"export const artists\s*:[^=]*=\s*\[", text)
    if not m:
        raise SystemExit("coverGuide.ts に artists 配列が見つからない（形が変わった可能性）")
    start = m.end() - 1  # '[' の位置
    end = _match_brace(text, start)
    body = text[start : end + 1]

    artists = []
    i = 1
    while i < len(body) - 1:
        c = body[i]
        if c in "\"'`":
            i = _skip_string(body, i)
            continue
        if c == "{":
            j = _match_brace(body, i)
            if j < 0:
                break
            fields = parse_obj(body[i : j + 1])
            if fields.get("id") and fields.get("name"):
                artists.append(_shape_artist(fields))
            i = j + 1
            continue
        i += 1
    return artists


def _shape_artist(f: dict) -> dict:
    songs = []
    for s in parse_obj_array(f.get("songs")):
        sid = s.get("id")
        title = s.get("title")
        if not sid or not title:
            continue
        # うんちく＝note。★無ければ null のまま。推測で埋めない。
        note = s.get("note") or None
        if isinstance(note, str) and not note.strip():
            note = None
        copy = s.get("copy") or None
        if isinstance(copy, str) and not copy.strip():
            copy = None
        songs.append(
            {
                "id": sid,
                "title": title.strip(),
                "youtubeId": s.get("youtubeId") or None,
                "year": s.get("year") if isinstance(s.get("year"), int) else None,
                "unchiku": note,       # ★あるときだけ1行。無ければ null
                "hitokoto": copy,      # ★案内人の一言。無ければ null
                "pick": bool(s.get("pick")),
            }
        )
    about = f.get("about") or None
    if isinstance(about, str) and not about.strip():
        about = None
    return {
        "id": f["id"],
        "name": f["name"],
        "aliases": parse_str_array(f.get("aliases")),
        "eras": parse_str_array(f.get("eras")),
        "about": about,
        "songs": songs,
    }


# ──────────────────────────────────────────────────────────────
# 棚を抜く
# ──────────────────────────────────────────────────────────────
def extract_worlds(text: str) -> list:
    worlds = []
    i = 0
    while True:
        m = re.search(r'\{\s*\n?\s*id:\s*"([a-z0-9\-]+)"', text[i:])
        if not m:
            break
        pos = i + m.start()
        j = _match_brace(text, pos)
        if j < 0:
            break
        f = parse_obj(text[pos : j + 1])
        wid = f.get("id")
        title = f.get("title") or f.get("label") or f.get("name")
        if wid and title:
            worlds.append(
                {
                    "id": wid,
                    "title": title,
                    "subtitle": f.get("subtitle") or None,
                    "emoji": f.get("emoji") or None,
                }
            )
        i = j + 1
    # 重複を落とす（先に出たものを残す）
    seen, out = set(), []
    for w in worlds:
        if w["id"] in seen:
            continue
        seen.add(w["id"])
        out.append(w)
    return out


# ──────────────────────────────────────────────────────────────
def build() -> dict:
    for p in (SRC_COVER, SRC_WORLD):
        if not os.path.exists(p):
            raise SystemExit(f"元のファイルが無い: {p}")

    cover = open(SRC_COVER, encoding="utf-8").read()
    world = open(SRC_WORLD, encoding="utf-8").read()

    artists = extract_artists(cover)
    worlds = extract_worlds(world)

    songs_total = sum(len(a["songs"]) for a in artists)
    playable = sum(1 for a in artists for s in a["songs"] if s["youtubeId"])
    with_unchiku = sum(1 for a in artists for s in a["songs"] if s["unchiku"])

    soul = {
        "version": 1,
        "tsukutta": datetime.now(JST).strftime("%Y-%m-%d %H:%M JST"),
        "tana": worlds,
        "artists": artists,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fp:
        json.dump(soul, fp, ensure_ascii=False, separators=(",", ":"))

    meta = {
        "tsukutta": soul["tsukutta"],
        "shutten": [
            {
                "file": os.path.relpath(SRC_COVER, REPO),
                "gyou": cover.count("\n") + 1,
                "sha256_12": hashlib.sha256(cover.encode()).hexdigest()[:12],
            },
            {
                "file": os.path.relpath(SRC_WORLD, REPO),
                "gyou": world.count("\n") + 1,
                "sha256_12": hashlib.sha256(world.encode()).hexdigest()[:12],
            },
        ],
        "kazu": {
            "artists": len(artists),
            "tana": len(worlds),
            "songs": songs_total,
            "songs_youtube_ari": playable,
            "songs_unchiku_ari": with_unchiku,
        },
        "bytes": os.path.getsize(OUT_JSON),
    }
    with open(OUT_META, "w", encoding="utf-8") as fp:
        json.dump(meta, fp, ensure_ascii=False, indent=2)
    return meta


def self_test() -> int:
    """★叩いて確かめる。設定に書いてあるは証拠にならない。"""
    ng = []
    meta = build()
    k = meta["kazu"]
    if k["artists"] < 50:
        ng.append(f"アーティストが少なすぎる: {k['artists']}人")
    if k["songs"] < 500:
        ng.append(f"曲が少なすぎる: {k['songs']}曲")
    if k["tana"] < 5:
        ng.append(f"棚が少なすぎる: {k['tana']}個")

    soul = json.load(open(OUT_JSON, encoding="utf-8"))
    # 空のうんちくが空文字で残っていないか（★無ければ黙る、を壊さないため）
    for a in soul["artists"]:
        for s in a["songs"]:
            if s["unchiku"] == "":
                ng.append(f"空文字のうんちくが残っている: {a['id']}/{s['id']}")
                break
        else:
            continue
        break

    for line in ng:
        print("✕", line)
    if not ng:
        print(f"○ 魂を出した：{k['artists']}人 / {k['songs']}曲 "
              f"(YouTubeあり {k['songs_youtube_ari']} / うんちくあり {k['songs_unchiku_ari']}) "
              f"/ 棚 {k['tana']} / {meta['bytes']:,}バイト")
    return 1 if ng else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    m = build()
    print(json.dumps(m, ensure_ascii=False, indent=2))
