#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/main_kanmon.py ── メイン不在の門

たまごさん（2026-09-24・原文）:
  「これから入れるものに関しては、ページを作る上でメインのコンテンツがないとかは、
    もうあり得ないからね。年号が抜けているとかならまだしも、タイトルがあるのに
    メインのものがないだとか、そういうのはもうゼロにして。あり得ないから。」

★門は「入れてから直す」ためのものではない。「入る前に止める」ためのもの。

  メイン ＝ その曲の音源・動画（coverGuide.ts の youtubeId / altYoutubeIds）
  メイン不在 ＝ title はあるのに youtubeId も altYoutubeIds も無い

  軽いもの（年号が無い・紹介文が短い）は通す。たまごさんが「まだしも」と言っている。
  ★重いのは「メイン不在」だけ。ここだけは1件も通さない。

使い方
  python3 tools/main_kanmon.py --jissoku
      本番のcoverGuide.tsを全部数えて status/main_kanmon.json に書く。
      （タイトルはあるがメインが無いページが今何件あるか）

  python3 tools/main_kanmon.py --check '{"id":"..","title":"..","youtubeId":".."}'
      1件を門に通す。通れば exit 0、弾けば exit 1。
      通った／弾いたは status/main_kanmon_daicho.jsonl に残る。

  python3 tools/main_kanmon.py --check-file kouho.json
      配列でまとめて通す。通ったものだけを標準出力にJSONで返す。

決まり
  - たまごさんのファイルを書き換えない。数えるだけ・弾くだけ。
  - ブラウザを使わない。課金しない。
"""
from __future__ import annotations

import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
SEKISHO = os.path.join(HERE, "sekisho")
if SEKISHO not in sys.path:
    sys.path.insert(0, SEKISHO)

JISSOKU = os.path.join(ST, "main_kanmon.json")
DAICHO = os.path.join(ST, "main_kanmon_daicho.jsonl")

# 本番の棚（joy-relief-station）
JOY_CANDIDATES = [
    "/Users/mac/Desktop/joy-relief-station",
    os.path.join(os.path.expanduser("~"), "Desktop", "joy-relief-station"),
]
CG_REL = [
    "src/lib/coverGuide.ts",     # ★本番（2026-09-24 実測）
    "src/data/coverGuide.ts",
    "app/data/coverGuide.ts",
    "data/coverGuide.ts",
]
# ★worktree の写しを本番と間違えない（.claude/worktrees 以下は数えない）
NOT_HONBAN = (".claude", "worktrees", "node_modules", "dist", ".next", "build", ".git")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _append(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def find_coverguide():
    """本番のcoverGuide.tsを探す。見つからなければ None。"""
    for root in JOY_CANDIDATES:
        if not os.path.isdir(root):
            continue
        for rel in CG_REL:
            p = os.path.join(root, rel)
            if os.path.exists(p):
                return p
        # 決め打ちで見つからなければ1回だけ掘る（worktreeの写しは除く）
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in NOT_HONBAN]
            if "coverGuide.ts" in filenames:
                return os.path.join(dirpath, "coverGuide.ts")
    return None


# ────────────────────────────────────────────────────────────
# ★門そのもの：1件を見て、通すか弾くか
# ────────────────────────────────────────────────────────────
def kanmon(song: dict):
    """1件を門に通す。

    返り値 (tooru: bool, riyuu: str)
      tooru=False のとき、それは本番に出してはいけない。
    """
    song = song or {}
    title = (song.get("title") or "").strip()
    yt = (song.get("youtubeId") or "").strip()
    alt = song.get("altYoutubeIds") or []
    if isinstance(alt, str):
        alt = [alt]
    alt = [str(a).strip() for a in alt if str(a).strip()]

    if not title:
        return False, "タイトルが無い"
    if yt or alt:
        return True, "メインあり"
    return False, "★メイン不在（タイトルはあるが、音源・動画が1本も無い）"


def check_one(song, doko="unknown"):
    tooru, riyuu = kanmon(song)
    _append(DAICHO, {
        "at": now(), "doko": doko,
        "id": (song or {}).get("id"), "title": (song or {}).get("title"),
        "tooshita": tooru, "riyuu": riyuu,
    })
    return tooru, riyuu


# ────────────────────────────────────────────────────────────
# ★既に本番にある分を数える
# ────────────────────────────────────────────────────────────
def jissoku():
    path = find_coverguide()
    if not path:
        out = {"at": now(), "yometa": False,
               "naze": "coverGuide.ts が見つかりません（このMac上に joy-relief-station が無い）",
               "mainFuzaiN": None}
        _write(JISSOKU, out)
        return out

    try:
        import parse_coverguide_deep as deep
    except Exception as e:
        out = {"at": now(), "yometa": False,
               "naze": "読み取り器が読めません: %s: %s" % (type(e).__name__, e),
               "mainFuzaiN": None}
        _write(JISSOKU, out)
        return out

    artists = deep.parse_deep(path)
    zen = 0
    fuzai = []
    # ★棚（cover-guide.tsx の playable）の実装に合わせて数える。
    #   notDiscarded = hideFromArtistList でないもの
    #   filtered     = そのうち再生できるもの
    #   base         = filtered.length > 0 ? filtered : notDiscarded
    #   ★つまり「その棚の曲が全部メイン不在」のときだけ、メイン不在が棚に出る。
    #     ここが穴。ふつうの棚では既に隠れている。
    karappo_tana = []     # 全曲メイン不在の棚（＝フォールバックで出てしまう）
    for a in artists:
        songs = a.get("songs", [])
        hyouji = [s for s in songs if not s.get("hideFromArtistList")]
        arus, nais = [], []
        for s in songs:
            zen += 1
            tooru, riyuu = kanmon(s)
            rec = {
                "artist": a.get("name"), "artistId": a.get("id"),
                "id": s.get("id"), "title": s.get("title"),
                "line": s.get("line"), "riyuu": riyuu,
                "hideFromArtistList": bool(s.get("hideFromArtistList")),
            }
            if tooru:
                arus.append(rec)
            else:
                nais.append(rec)
                fuzai.append(rec)
        # 棚に出る候補のうち、メインのあるものが1本も無い棚
        hyouji_aru = [s for s in hyouji if kanmon(s)[0]]
        if hyouji and not hyouji_aru:
            karappo_tana.append({
                "artist": a.get("name"), "artistId": a.get("id"),
                "line": a.get("line"),
                "kyokuN": len(hyouji),
                "rei": [s.get("title") for s in hyouji[:5]],
            })

    deteru = [f for f in fuzai if not f["hideFromArtistList"]]
    kakureteru = [f for f in fuzai if f["hideFromArtistList"]]
    # ★本当に本番の棚に「メイン不在のカード」が出てしまう本数
    dete_shimau = sum(t["kyokuN"] for t in karappo_tana)

    out = {
        "at": now(), "yometa": True, "coverGuide": path,
        "kyokuZen": zen,
        "mainFuzaiN": len(fuzai),
        "mainFuzaiDeteruN": len(deteru),
        "mainFuzaiKakureteruN": len(kakureteru),
        # ★ここが赤の本体
        "karappoTanaN": len(karappo_tana),
        "tanaNiDeteShimauN": dete_shimau,
        "aka": dete_shimau > 0,
        "note": ("棚は既に『再生できる曲』だけに絞っている（cover-guide.tsx の playable）。"
                 "ただし filtered.length>0 ? filtered : notDiscarded のフォールバックがあるので、"
                 "★その棚の曲が全部メイン不在のときだけ、メイン不在のカードが棚に出てしまう。"
                 "tanaNiDeteShimauN がその本数。0でなければ赤。"
                 "mainFuzaiDeteruN は『データ上メインが無い曲』の総数で、"
                 "その大半は棚では既に隠れている。"),
        "karappoTana": karappo_tana[:300],
        "meisai": deteru[:300],
    }
    _write(JISSOKU, out)
    return out


def main():
    a = sys.argv[1:]
    if "--jissoku" in a:
        out = jissoku()
        if not out.get("yometa"):
            print("読めませんでした：%s" % out.get("naze"))
            return 2
        print("全曲 %d 件／データ上メイン不在 %d 件"
              % (out["kyokuZen"], out["mainFuzaiN"]))
        print("★棚にメイン不在のカードが出てしまう：%d 件（全曲メイン不在の棚 %d 個）"
              % (out["tanaNiDeteShimauN"], out["karappoTanaN"]))
        print("→ %s" % JISSOKU)
        return 1 if out["aka"] else 0

    if "--check" in a:
        song = json.loads(a[a.index("--check") + 1])
        tooru, riyuu = check_one(song, doko="cli")
        print(("通す" if tooru else "★弾く") + "：" + riyuu)
        return 0 if tooru else 1

    if "--check-file" in a:
        p = a[a.index("--check-file") + 1]
        with open(p, encoding="utf-8") as f:
            songs = json.load(f)
        ok, ng = [], []
        for s in songs:
            tooru, riyuu = check_one(s, doko=os.path.basename(p))
            (ok if tooru else ng).append({"song": s, "riyuu": riyuu})
        sys.stderr.write("通した %d 件／★弾いた %d 件\n" % (len(ok), len(ng)))
        print(json.dumps([x["song"] for x in ok], ensure_ascii=False, indent=1))
        return 0

    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
