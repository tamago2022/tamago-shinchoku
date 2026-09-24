#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1124番【秋に出せる曲の候補リスト】ごきげん補給所の棚（coverGuide.ts）から秋の候補を抜く。

たまごさん（2026-09-24・原文）:
  「ChatGPTと決めたいからリストは早くほしい。今、補給所にある4,500曲と、
    Spotifyにある自分の秋のプレイリスト、それ両方出して。無いものは仕入れてもらうから。」

読む場所（1行で言える形にしておく）:
  /Users/mac/Desktop/joy-relief-station/src/lib/coverGuide.ts の `export const artists`
  ＝名カバー案内所／ごきげん補給所の棚の正本（手更新）。Supabaseの admin_stock は別（公開在庫）。

秋の判定:
  A群（秋そのもの）… 曲名・紹介文に秋の言葉が入っている
  B群（秋に合う）  … しっとり・夜・切ないの言葉が入っている
  ★どちらも「当たった言葉」を根拠として1語だけ添える。憶測の情緒判定はしない。
"""
from __future__ import annotations
import io, json, os, re, sys

CG = "/Users/mac/Desktop/joy-relief-station/src/lib/coverGuide.ts"
SITE = "https://joy-relief-station.lovable.app"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "status", "1124_aki")

AKI = ["秋", "枯葉", "枯れ葉", "落ち葉", "紅葉", "木枯らし", "金木犀", "коスモス", "コスモス",
       "十五夜", "月見", "夜長", "稲", "収穫", "ハロウィン", "autumn", "Autumn", "AUTUMN",
       "September", "september", "October", "october", "November", "november",
       "Harvest", "harvest", "Leaves", "leaves"]
SHITTORI = ["しっとり", "切ない", "せつない", "黄昏", "たそがれ", "夕暮れ", "夕焼け", "暮れ",
            "夜更け", "深夜", "夜の", "月夜", "焚き火", "毛布", "珈琲", "コーヒー", "湯気",
            "冷たい", "肌寒", "さみしい", "寂し", "ひとり", "帰り道", "余韻", "静かな"]


def _scan_array(s, start):
    """start は '[' の位置。対応する ']' の位置を返す（文字列リテラルを飛ばす）。"""
    i, depth = start, 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"' or c == "'" or c == "`":
            q = c
            i += 1
            while i < n:
                if s[i] == "\\":
                    i += 2
                    continue
                if s[i] == q:
                    break
                i += 1
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top(s):
    """配列の中身を、深さ0のカンマで割る。"""
    out, buf, depth, i, n = [], [], 0, 0, len(s)
    while i < n:
        c = s[i]
        if c in "\"'`":
            q = c
            buf.append(c)
            i += 1
            while i < n:
                buf.append(s[i])
                if s[i] == "\\":
                    i += 1
                    if i < n:
                        buf.append(s[i])
                    i += 1
                    continue
                if s[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c in "{[(":
            depth += 1
        elif c in "}])":
            depth -= 1
        if c == "," and depth == 0:
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf))
    return out


def _sval(block, key):
    m = re.search(r'(?<![A-Za-z])%s:\s*"((?:[^"\\]|\\.)*)"' % key, block)
    if m:
        return m.group(1).encode().decode("unicode_escape") if "\\" in m.group(1) else m.group(1)
    return ""


def _nval(block, key):
    m = re.search(r'(?<![A-Za-z])%s:\s*(\d+)' % key, block)
    return int(m.group(1)) if m else None


def songs():
    s = io.open(CG, encoding="utf-8").read()
    i = s.index("export const artists")
    # ★"CoverGuideArtist[]" の [] を拾わないよう、"= [" の [ を使う
    lb = re.search(r"=\s*\[", s[i:]).end() - 1 + i
    rb = _scan_array(s, lb)
    body = s[lb + 1:rb]
    rows = []
    for ab in _split_top(body):
        ab = ab.strip()
        if not ab.startswith("{"):
            continue
        aid = _sval(ab, "id")
        aname = _sval(ab, "name")
        j = ab.find("songs:")
        if j < 0:
            continue
        slb = ab.index("[", j)
        srb = _scan_array(ab, slb)
        for sb in _split_top(ab[slb + 1:srb]):
            sb = sb.strip()
            if not sb.startswith("{"):
                continue
            sid = _sval(sb, "id")
            if not sid:
                continue
            rows.append({"artistId": aid, "artist": aname, "songId": sid,
                         "title": _sval(sb, "title"), "year": _nval(sb, "year"),
                         "note": _sval(sb, "note"), "copy": _sval(sb, "copy")})
    return rows


def hit(text, words):
    for w in words:
        if w and w in text:
            return w
    return ""


def main():
    rows = songs()
    os.makedirs(OUT, exist_ok=True)
    a, b = [], []
    for r in rows:
        t = " ".join([r["title"], r["note"], r["copy"]])
        w = hit(t, AKI)
        if w:
            r2 = dict(r); r2["根拠"] = w; a.append(r2); continue
        w = hit(t, SHITTORI)
        if w:
            r2 = dict(r); r2["根拠"] = w; b.append(r2)
    for r in rows + a + b:
        r["url"] = "%s/song/%s/%s" % (SITE, r["artistId"], r["songId"])
    json.dump({"棚の総曲数": len(rows), "A_秋そのもの": a, "B_秋に合う": b,
               "読んだ場所": CG},
              io.open(os.path.join(OUT, "aki_kouho.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("棚の総曲数=%d  A(秋そのもの)=%d  B(秋に合う)=%d" % (len(rows), len(a), len(b)))
    for r in a[:5]:
        print("  A:", r["title"], "/", r["artist"], r["year"], "根拠=", r["根拠"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
