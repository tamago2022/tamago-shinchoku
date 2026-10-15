#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1133番【OGカードの型】1200x630のカードを、テンプレート1枚＋データから作る。

たまごさん（2026-09-25・実測の指摘）:
  「8割が空っぽのクリーム色。卵が豆粒。地図アイコンとコンパスが写り込んでいる。
    曲の顔が無い。タイムラインで指が止まらない。」
  「1枚ずつ手作りしない。テンプレート1枚＋データで自動生成。」

■ 決め（変える理由が出るまで動かさない）
  ・画像の権利：`share/1131-hikidashi-gazou.html` の「安全03 自前で作る
    （タイポグラフィと抽象ビジュアル）」だけを使う。
    ジャケット写真・アーティスト写真・YouTubeのサムネイルは**焼かない**。
    → 権利者に確認が要らない唯一の道。26,421曲を一括で焼ける唯一の道でもある。
  ・トーン：tamago-tone。生成り #EDE6D6 ／ 夜の藍 #22304A ／ 朱 #C1442E。
    色は3色まで。差し色は朱1点。余白を広く。細いセリフ体。生き物は描かない。
  ・サイトのUIは1つも写さない（スクショではないので構造的に混入しない）。
  ・日本語カードと英語カードを別に焼く（海外発信が前提）。

■ 使い方
    python3 tools/1133_og_card.py --title "夏の終りのハーモニー" \
        --artist "井上陽水・安全地帯" --year 1986 --out /tmp/a.png
    python3 tools/1133_og_card.py --lang en --title "Harmony at Summer's End" ...
    python3 tools/1133_og_card.py --json data.json --outdir out/   # 一括
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
KINARI = (237, 230, 214)      # 生成り
AI = (34, 48, 74)             # 夜の藍
SHU = (193, 68, 46)           # 朱
SUMI = (28, 26, 24)

FONT_DIRS = [
    "/usr/share/fonts/opentype/noto",
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]
# 明朝・セリフ体を、上から順に探す。Mac（工場）とLinux（Cowork）の両方で同じ顔になるよう、
# まず Noto Serif CJK を探し、無ければヒラギノ明朝に落ちる。
SERIF_PATTERNS = [
    ("NotoSerifCJK-Regular.ttc", 0),
    ("NotoSerifCJK-Bold.ttc", 0),
    ("NotoSerifJP-Regular.otf", 0),
    ("ヒラギノ明朝 ProN.ttc", 0),
    ("ヒラギノ明朝 ProN W3.ttc", 0),
    ("HiraMinProN-W3.otf", 0),
    ("Hiragino Mincho ProN.ttc", 0),
    ("ToppanBunkyuMinchoPr6N-Regular.otf", 0),
    ("YuMincho.ttc", 0),
    ("Times New Roman.ttf", 0),
    ("Times.ttc", 0),
]


def _find_font():
    for d in FONT_DIRS:
        for name, idx in SERIF_PATTERNS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p, idx
    # 名前で見つからなければ、明朝っぽいものを拾う（工場と手元で名前が違うことがある）
    import glob
    for d in FONT_DIRS:
        for pat in ("*Mincho*", "*Serif*", "*明朝*"):
            for p in sorted(glob.glob(os.path.join(d, pat))):
                if p.lower().endswith((".ttc", ".otf", ".ttf")):
                    return p, 0
    raise SystemExit("明朝/セリフ体のフォントが見つかりません（探した場所: %s）" % FONT_DIRS)


FONT_PATH, FONT_INDEX = _find_font()
_CACHE = {}


def font(size):
    key = size
    if key not in _CACHE:
        _CACHE[key] = ImageFont.truetype(FONT_PATH, size, index=FONT_INDEX)
    return _CACHE[key]


def _w(draw, s, f, tracking=0):
    if not s:
        return 0
    return int(draw.textlength(s, font=f) + tracking * (len(s) - 1))


def _text(draw, xy, s, f, fill, tracking=0, anchor_left=True):
    """字間（tracking）を開けて置く。たまごさんの採用例の文字組み。"""
    x, y = xy
    for ch in s:
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f) + tracking


def _wrap(draw, s, f, maxw, tracking, maxlines):
    """入るところで折る。日本語は文字単位、英語は単語単位。"""
    if any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in s):
        units, joiner = list(s), ""
    else:
        units, joiner = s.split(" "), " "
    lines, cur = [], ""
    for u in units:
        t = (cur + joiner + u) if cur else u
        if _w(draw, t, f, tracking) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = u
            if len(lines) == maxlines:
                break
    if cur and len(lines) < maxlines:
        lines.append(cur)
    if len(lines) > maxlines:
        lines = lines[:maxlines]
    return lines


def _paper(seed):
    """紙の目。ノイズを主張させない（ざらざらが見えたら負け）。濃淡のムラ＋ごく薄い粒。"""
    rnd = random.Random(seed)
    # 大きなムラ（染みのような濃淡）
    blot = Image.frombytes("L", (24, 13), rnd.randbytes(24 * 13)).point(
        lambda v: 108 + v * 40 // 255)
    blot = blot.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(26))
    # ごく細かい粒
    fine = Image.frombytes("L", (W // 2, H // 2), rnd.randbytes((W // 2) * (H // 2))).point(
        lambda v: 116 + v * 24 // 255)
    fine = fine.resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))
    base = Image.new("RGB", (W, H), KINARI)
    dark = Image.new("RGB", (W, H), (224, 216, 199))
    img = Image.composite(dark, base, blot.point(lambda v: 255 - v))
    img = Image.blend(img, Image.composite(dark, base, fine), 0.35)
    return img


def _hinowa(img, seed):
    """朱の日輪。右に大きく、画面の外へ逃がす。刷り物の地であって、アイコンにしない。"""
    rnd = random.Random(seed + 7)
    r = rnd.randint(280, 330)
    cx, cy = W - rnd.randint(30, 90), H + rnd.randint(10, 70)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([cx - r, cy - r, cx + r, cy + r], fill=SHU + (30,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2)))


def _balance(d, lines, f, tracking):
    """2行のとき、1文字だけ落ちる（孤児）のを避けて、長さを揃え直す。"""
    if len(lines) != 2:
        return lines
    a, b = lines
    if any("぀" <= c <= "ヿ" or "一" <= c <= "鿿" for c in a + b):
        s = a + b
        best, bestdiff = (a, b), 10 ** 9
        for i in range(1, len(s)):
            diff = abs(_w(d, s[:i], f, tracking) - _w(d, s[i:], f, tracking))
            if diff < bestdiff:
                bestdiff, best = diff, (s[:i], s[i:])
        return list(best)
    return lines


TITLE_ZONE = 262   # 曲名が使ってよい高さ（ここを越えたら級数を落とす）


def _fit(d, title, lang, maxw):
    """2行・TITLE_ZONE の中に必ず収まる、いちばん大きい級数を選ぶ。"""
    tracking = 3 if lang == "ja" else 0
    size = 122 if lang == "ja" else 112
    while size > 40:
        f = font(size)
        lines = _balance(d, _wrap(d, title, f, maxw, tracking, 2), f, tracking)
        got = "".join(lines).replace(" ", "")
        want = title.replace(" ", "")
        fits = all(_w(d, ln, f, tracking) <= maxw for ln in lines)
        if got == want and fits and int(size * 1.26) * len(lines) <= TITLE_ZONE:
            return f, lines, size, tracking
        size -= 4
    f = font(40)
    return f, _wrap(d, title, f, maxw, tracking, 2), 40, tracking


# ── 地（紙＋日輪）は8種類だけ先に作って使い回す。
#    1枚ずつ作ると1.64秒かかり、8万曲で37時間になる（実測 2026-09-25）。
#    使い回しても曲ごとに8通りに散るので、並べたときに同じ顔にはならない。
_JI = {}


def _ji(seed):
    k = seed % 8
    if k not in _JI:
        img = _paper(k * 977 + 13).convert("RGBA")
        _hinowa(img, k * 977 + 13)
        _JI[k] = img
    return _JI[k].copy()


def card(title, artist, year="", lang="ja", kicker="", seed=None):
    seed = seed if seed is not None else int(
        hashlib.md5((title + artist).encode("utf-8")).hexdigest()[:8], 16)
    img = _ji(seed)
    d = ImageDraw.Draw(img)

    L, R = 84, W - 84
    maxw = R - L

    # ── 上段：左に肩書き、右に年（編集紙面の見出し回り）
    fk = font(25)
    k = kicker or ("この曲の寄り道" if lang == "ja" else "A LITTLE DETOUR")
    _text(d, (L, 74), k, fk, (128, 118, 100), 7)
    if year:
        fy = font(30)
        ys = str(year)
        _text(d, (R - _w(d, ys, fy, 7), 72), ys, fy, SHU, 7)

    # ── 曲名＝顔。いちばん大きい。ここだけが主役
    f, lines, size, tracking = _fit(d, title, lang, maxw)
    lh = int(size * 1.26)
    block = lh * len(lines)
    top = 150 + (TITLE_ZONE - block) // 2
    for i, ln in enumerate(lines):
        _text(d, (L, top + i * lh), ln, f, SUMI, tracking)

    # ── 朱の短い罫。差し色はここと日輪と年だけ
    ry = 470
    d.line([(L, ry), (L + 86, ry)], fill=SHU, width=5)

    # ── 下段：左にアーティスト名、右に署名（採用済みの文字組み）
    fa = font(44 if lang == "ja" else 42)
    _text(d, (L, ry + 28), artist, fa, AI, 2 if lang == "ja" else 0)
    fs1, fs2 = font(20), font(14)
    s1, s2 = "ごきげん補給所", "JOY RELIEF STATION"
    _text(d, (R - _w(d, s1, fs1, 7), ry + 32), s1, fs1, AI, 7)
    _text(d, (R - _w(d, s2, fs2, 4.2), ry + 62), s2, fs2, SHU, 4.2)

    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title")
    ap.add_argument("--artist", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--lang", default="ja", choices=["ja", "en"])
    ap.add_argument("--kicker", default="")
    ap.add_argument("--out", default="/tmp/og.png")
    ap.add_argument("--json", help="[{title,artist,year,lang,slug}] の一括")
    ap.add_argument("--outdir")
    a = ap.parse_args()
    if a.json:
        rows = json.load(open(a.json, encoding="utf-8"))
        os.makedirs(a.outdir, exist_ok=True)
        for r in rows:
            p = os.path.join(a.outdir, "%s-%s.png" % (r["slug"], r.get("lang", "ja")))
            card(r["title"], r.get("artist", ""), r.get("year", ""),
                 r.get("lang", "ja")).save(p, optimize=True)
        print("%d枚 → %s" % (len(rows), a.outdir))
        return
    if not a.title:
        sys.exit("--title が要ります")
    card(a.title, a.artist, a.year, a.lang, a.kicker).save(a.out, optimize=True)
    print(a.out)


if __name__ == "__main__":
    main()
