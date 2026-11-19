#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1058番【棚の中にあるのに繋がっていない組を割り出す】

━━ たまごさんの言葉（2026-09-24・原文）━━

  「今ごきげん補給所の中に入ってるので、カバーがあるのに繋がってないだとか、
    そういうのがあったら割り出して繋げてほしいな。カバーかどうかは俺が決めるけどね。
    カバーが何十人もいるんだったら、それも絞らないといけない。いいものだけ繋ぎたいから。」

━━ 何をするか ━━

  棚（coverGuide.ts）の中で、**同じ曲名が2人以上のアーティストに入っているのに、
  互いにリンク（curated の covers / originalRef）が張られていない組**を一覧にする。
  ★新しく仕入れるより先に、今あるものの間に道を通す（憲法第7条・関連づけ）。

━━ 決めたこと ━━

  ① **外へ1回も出ない。AIを1回も呼ばない。クレジット0円。**手元の棚を突き合わせるだけ。
  ② **勝手に本番へ繋がない。**出すのは「候補」の一覧だけ。採否はたまごさん（憲法・棚出しの判断）。
  ③ **1曲につき最大3件まで**（たまごさん「何十人もいるなら絞る」）。
     絞る順：公式らしさ（動画IDがある）＞ 棚での扱い（pick）＞ 曲名の一致の強さ。
  ④ 曲名が同じでも**別の曲のことがある**ので、断定しない。「候補」とだけ書く。
  ⑤ 一般名すぎる曲名（1語・数字だけ 等）は誤爆のもとなので落とす。

━━ 使い方 ━━

    python3 tools/tsunagatte_nai.py --src <coverGuide.ts のパス>
    → status/gsk/tsunagatte_nai.json  （機械が読む）
    → share/check/1058-tsunagatte-nai.html （たまごさんが見る一覧）
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_JSON = os.path.join(REPO, "status", "gsk", "tsunagatte_nai.json")
OUT_HTML = os.path.join(REPO, "share", "check", "1058-tsunagatte-nai.html")

MAX_PER_SONG = 3          # 1曲につき最大3件（たまごさんの指示）
MIN_TITLE_LEN = 4         # 短すぎる曲名は誤爆のもと


# ───────────── TSをなめる（構文解析はしない。括弧だけ数える） ─────────────

def brace_blocks(text: str, start: int):
    """start 以降の、対応の取れた { ... } を順に返す。文字列の中の括弧は数えない。"""
    i = start
    n = len(text)
    while i < n:
        if text[i] == "{":
            depth = 0
            j = i
            in_str = None
            while j < n:
                c = text[j]
                if in_str:
                    if c == "\\":
                        j += 2
                        continue
                    if c == in_str:
                        in_str = None
                elif c in "\"'`":
                    in_str = c
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        yield text[i:j + 1]
                        i = j
                        break
                j += 1
            else:
                return
        elif text[i] == "]" :
            return
        i += 1


def field(obj: str, name: str):
    m = re.search(r'\b%s:\s*"((?:[^"\\]|\\.)*)"' % name, obj)
    if m:
        return m.group(1).replace('\\"', '"')
    m = re.search(r'\b%s:\s*(\d+)' % name, obj)
    return m.group(1) if m else None


def parse_artists(text: str):
    m = re.search(r"export const artists:\s*CoverGuideArtist\[\]\s*=\s*\[", text)
    if not m:
        return []
    out = []
    for blk in brace_blocks(text, m.end()):
        aid = field(blk, "id")
        name = field(blk, "name")
        if not aid or not name:
            continue
        songs = []
        sm = re.search(r"\bsongs:\s*\[", blk)
        if sm:
            for sb in brace_blocks(blk, sm.end()):
                sid = field(sb, "id")
                title = field(sb, "title")
                if not sid or not title:
                    continue
                songs.append({
                    "id": sid, "title": title,
                    "youtubeId": field(sb, "youtubeId"),
                    "pick": "pick: true" in sb,
                    "originalRef": bool(re.search(r"\boriginalRef:\s*\{", sb)),
                    "originalArtistId": (re.search(r'originalRef:\s*\{[^}]*artistId:\s*"([^"]+)"', sb) or [None, None])[1]
                    if re.search(r"\boriginalRef:\s*\{", sb) else None,
                })
        out.append({"id": aid, "name": name, "songs": songs})
    return out


def parse_curated(text: str):
    """curated のキーごとに、繋がっている先（youtubeId・by）を集める。"""
    linked = {}
    for m in re.finditer(r"export const (?:curated|curatedGenerated):\s*Record<[^>]*>\s*=\s*\{", text):
        i = m.end()
        for km in re.finditer(r'\n\s{2}"([^"]+)":\s*\{', text[i:i + 6000000]):
            key = km.group(1)
            blocks = list(brace_blocks(text, i + km.end() - 1))
            body = blocks[0] if blocks else ""
            ids = set(re.findall(r'youtubeId:\s*"([^"]+)"', body))
            bys = set(x for x in re.findall(r'\bby:\s*"((?:[^"\\]|\\.)*)"', body))
            linked.setdefault(key, {"youtubeIds": set(), "by": set()})
            linked[key]["youtubeIds"] |= ids
            linked[key]["by"] |= bys
    return linked


# ───────────── 曲名をそろえる ─────────────

PAREN = re.compile(r"[（(\[【].*?[）)\]】]")
NOISE = re.compile(r"(clipe oficial|official (music )?video|official|mv|live|audio|remaster(ed)?|feat\.?.*$|ft\.?.*$|ver\.?|version|歌詞|字幕)", re.I)


def norm_title(t: str) -> str:
    s = unicodedata.normalize("NFKC", t or "").lower()
    s = PAREN.sub(" ", s)
    s = s.split("•")[0].split("|")[0].split("/")[0]
    s = NOISE.sub(" ", s)
    s = re.sub(r"[^\w\u3040-\u30ff\u4e00-\u9fff]+", "", s)
    return s


GENERIC = {"heaven", "love", "home", "you", "me", "hello", "so", "sun", "rain", "yes", "one", "again", "why"}

# ★曲名ではないもの（番組名・体裁）は落とす。これを入れると一覧の上位が全部ゴミになる（実測）。
JUNK = re.compile(
    r"(tinydesk|tiny desk|npr ?music|fullconcert|full concert|fullperformance|full performance|"
    r"liveat|live at|livesession|live session|inthe?studio|medley|メドレー|fullalbum|full album|"
    r"完全版|ダイジェスト|コンサート|ライブ映像)", re.I)


# ───────────── 本体 ─────────────

def shiraberu(src: str):
    with open(src, "r", encoding="utf-8") as f:
        text = f.read()
    artists = parse_artists(text)
    linked = parse_curated(text)

    # 曲名ごとに、誰が持っているかを集める
    tana = defaultdict(list)
    for a in artists:
        for s in a["songs"]:
            nt = norm_title(s["title"])
            if len(nt) < MIN_TITLE_LEN or nt in GENERIC:
                continue
            if JUNK.search(s["title"]) or JUNK.search(nt):
                continue
            tana[nt].append({
                "artistId": a["id"], "artistName": a["name"],
                "songId": s["id"], "title": s["title"],
                "youtubeId": s.get("youtubeId"),
                "pick": s.get("pick"),
                "originalRef": s.get("originalRef"),
                "key": "%s/%s" % (a["id"], s["id"]),
            })

    kumi = []
    for nt, rows in tana.items():
        # 同じアーティストの中だけの重複は対象外（別人同士のときだけ「繋がる」意味がある）
        if len({r["artistId"] for r in rows}) < 2:
            continue
        # すでに繋がっているか？
        def is_linked(a_row, b_row):
            la = linked.get(a_row["key"], {})
            lb = linked.get(b_row["key"], {})
            if b_row.get("youtubeId") and b_row["youtubeId"] in la.get("youtubeIds", set()):
                return True
            if a_row.get("youtubeId") and a_row["youtubeId"] in lb.get("youtubeIds", set()):
                return True
            if a_row["artistName"] in lb.get("by", set()) or b_row["artistName"] in la.get("by", set()):
                return True
            if a_row.get("originalRef") or b_row.get("originalRef"):
                return True
            return False

        nokori = []
        base = sorted(rows, key=lambda r: (not r.get("pick"), not r.get("youtubeId")))
        head = base[0]
        for r in base[1:]:
            if r["artistId"] == head["artistId"]:
                continue
            if is_linked(head, r):
                continue
            # ★同じ人の棚が2つに割れているだけの組は「カバー」ではないので外す
            #   （大滝詠一 / 大滝詠一・山下達郎 / 山下達郎(名演選) のような分裂）
            na, nb = norm_title(head["artistName"]), norm_title(r["artistName"])
            if na and nb and (na in nb or nb in na):
                continue
            nokori.append(r)
        if not nokori:
            continue
        # ★1曲につき最大3件まで。動画IDがあるもの・棚でpickされているものを先に
        nokori.sort(key=lambda r: (not r.get("youtubeId"), not r.get("pick"), r["artistName"]))
        kumi.append({
            "曲名": head["title"],
            "そろえた名前": nt,
            "軸": {"アーティスト": head["artistName"], "key": head["key"], "youtubeId": head.get("youtubeId")},
            "繋がっていない候補": nokori[:MAX_PER_SONG],
            "候補の総数": len(nokori),
        })

    # ★並べ方（実測で直した）：候補が多い順に並べたら、上位が全部「同名の別曲」だった
    #   （Dreams / Beautiful / Stay のような一般名は、何十人も出るが1人も同じ曲ではない）。
    #   同名の衝突が**少ない**ほど、本当に同じ曲である見込みが高い。
    #   ＋曲名が長い（固有性が高い）ものを上に。Corcovado のような当たりが上へ来る。
    kumi.sort(key=lambda k: (k["候補の総数"], -len(k["そろえた名前"]), k["曲名"]))
    return {
        "説明": "棚の中に同じ曲名が2人以上いるのに、互いに繋がっていない組。★候補であって断定ではない。採否はたまごさん。",
        "棚のアーティスト数": len(artists),
        "棚の曲数": sum(len(a["songs"]) for a in artists),
        "繋がっていない組": len(kumi),
        "1曲あたりの上限": MAX_PER_SONG,
        "組": kumi,
    }


def kaku_html(d):
    # ★スマホ1画面（375px）で横にはみ出さないこと。表は必ずはみ出すのでカードにする（実測で427pxだった）。
    cards = []
    for k in d["組"][:400]:
        cand = "".join(
            "<li>%s<span class=t>%s</span>%s</li>" % (
                html.escape(c["artistName"]), html.escape(c["title"]),
                "" if c.get("youtubeId") else "<span class=x>動画なし</span>")
            for c in k["繋がっていない候補"])
        more = "" if k["候補の総数"] <= MAX_PER_SONG else "<div class=x>ほか%d件</div>" % (k["候補の総数"] - MAX_PER_SONG)
        cards.append(
            "<div class=c><div class=ttl>%s</div>"
            "<div class=jiku>軸：%s<span class=t>%s</span></div>"
            "<div class=lbl>繋がっていない相手（候補）</div><ul>%s</ul>%s</div>" % (
                html.escape(k["曲名"]),
                html.escape(k["軸"]["アーティスト"]), html.escape(k["軸"]["key"]),
                cand, more))
    return """<!doctype html><meta charset=utf-8><title>棚の中で繋がっていない組</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>*{box-sizing:border-box;min-width:0}
body{font:15px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans",sans-serif;margin:0;padding:16px 14px 60px;background:#faf8f4;color:#221;overflow-wrap:anywhere;word-break:break-word}
h1{font-size:19px;margin:0 0 4px}p{color:#665;margin:4px 0 16px;font-size:12px}
.c{background:#fff;border:1px solid #e8e2d6;border-radius:12px;padding:12px 14px;margin:0 0 10px}
.ttl{font-size:15px;font-weight:700;line-height:1.45}
.jiku{font-size:12.5px;color:#443;margin-top:6px}
.lbl{font-size:11px;color:#887;margin-top:10px}
ul{margin:4px 0 0;padding-left:18px;font-size:13px}
li{margin-bottom:4px}
.t{display:block;color:#887;font-size:11px}.x{display:block;color:#b64;font-size:11px}</style>
<h1>棚の中にあるのに繋がっていない組</h1>
<p>棚 %d組／アーティスト%d・曲%d。<b>候補であって断定ではありません。</b>同じ曲名でも別の曲のことがあります。
1曲につき最大%d件まで（公式らしさ→棚でのpick→名前の一致の順に絞ってあります）。<b>採否はたまごさん。</b>こちらでは本番に繋いでいません。</p>
%s
""" % (d["繋がっていない組"], d["棚のアーティスト数"], d["棚の曲数"], MAX_PER_SONG, "".join(cards))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    a = ap.parse_args()
    if not os.path.exists(a.src):
        print("棚のファイルがありません: %s" % a.src)
        return 1
    d = shiraberu(a.src)
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(kaku_html(d))
    print(json.dumps({k: d[k] for k in ("棚のアーティスト数", "棚の曲数", "繋がっていない組")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
