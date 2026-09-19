#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""案内人に「うちの言葉」を渡す棚を1つ足す（1020番）。

なぜ要るか
----------
たまごさん 2026-09-22：
  「コンシェルジュが短く受け答えしてるのはすごくいいんだけど、
    もうちょっとだけ説明が欲しいかな。ちょっとシンプルすぎるんだよね。」

案内人が薄いのは、喋る量が少ないからではない。**手持ちの材料が薄いから。**
いま案内人に渡している事実は「アーティスト名／発表年／年代」だけ。
アーティスト紹介文(ab)が入っているのは 2475人のうち 476人（19%）しかない。
だから「代表曲のひとつ。」相当の水道水しか言えない。

ところが、うちの棚（coverGuide.ts）には **曲ごとの note / copy が約12,000本** ある。
人が書いた、裏の取れている、うちの言葉。**案内人に渡していなかっただけ。**

なぜ a/ に足さないのか（一度やって、やめた）
--------------------------------------------
最初は a/NN.json の各行の末尾に足した。動いたが **a/ が 2,984KB → 3,992KB（+34%）** になった。
a/ は1回の検索で最大24枚読む棚なので、**1回探すたびに約190KB重くなる。**
「機能は付いたが少し重くなった」は不合格（鬼監督 7.軽さ）。なので作り直した。

いまの形
--------
    share/check/assets/953-songs/n/NN.json   … {"アーティスト番号/曲id": "うちの言葉"}

**探すときには読まない。4枚の札が画面に出てから、その4枚が入っている棚だけ読む。**
1枚あたりの棚は約9KB。4枚出しても最大4枚ぶん＝**約36KB**しか増えない。
探す速さは1バイトも変わらない（a/ は元のまま・1行も書き換えていない）。

使い方
------
    python3 tools/_1020_add_note_to_shelf.py           # 書き込む
    python3 tools/_1020_add_note_to_shelf.py --dry     # 数えるだけ
"""
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import importlib
B = importlib.import_module("_953_build_song_index")

OUT_DIR = B.OUT_DIR
NOTE_DIR = OUT_DIR / "n"
CAP = 100          # 1本あたりの上限。中央値33字なので、ほとんどは切れない。


def tidy_note(s: str) -> str:
    """途中で切れた文を案内人に渡さない。切るなら句点で切る。"""
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return ""
    if len(s) <= CAP:
        return s
    cut = s[:CAP]
    for mark in ("。", "！", "？", "．"):
        i = cut.rfind(mark)
        if i >= 20:
            return cut[: i + 1]
    return cut[:CAP].rstrip("、,・ ") + "…"


def main() -> int:
    dry = "--dry" in sys.argv
    if not B.SRC.exists():
        print("元データが無い:", B.SRC)
        return 1
    src = B.strip_comments(B.SRC.read_text(encoding="utf-8", errors="replace"))
    artists = B.read_artists(src)

    # (アーティストid, 曲id) → うちの言葉
    note_by = {}
    for a in artists:
        aid = a.get("id")
        for s in (a.get("songs") or []):
            if not isinstance(s, dict):
                continue
            sid = s.get("id")
            if not aid or not sid:
                continue
            n = tidy_note(s.get("copy") or s.get("note") or "")
            if n:
                note_by[(aid, sid)] = n
    print(f"元データの note/copy：{len(note_by)}本")

    head = json.loads((OUT_DIR / "head.json").read_text(encoding="utf-8"))
    A = head["A"]
    nb = head["nb"]

    # 棚に実際に載っている曲だけを拾う。載っていない曲の言葉は持っていても使えない。
    buckets = {}
    total = hit = 0
    for fp in sorted((OUT_DIR / "a").glob("*.json")):
        for r in json.loads(fp.read_text(encoding="utf-8")):
            total += 1
            ai = r[0]
            if not (0 <= ai < len(A)):
                continue
            n = note_by.get((A[ai]["i"], r[1]))
            if not n:
                continue
            buckets.setdefault(ai % nb, {})[f"{ai}/{r[1]}"] = n
            hit += 1

    if not dry:
        NOTE_DIR.mkdir(parents=True, exist_ok=True)
        for i in range(nb):
            (NOTE_DIR / f"{i}.json").write_text(
                json.dumps(buckets.get(i, {}), ensure_ascii=False,
                           separators=(",", ":")), encoding="utf-8")

    kb = sum(p.stat().st_size for p in NOTE_DIR.glob("*.json")) / 1024 if NOTE_DIR.is_dir() else 0
    akb = sum(p.stat().st_size for p in (OUT_DIR / "a").glob("*.json")) / 1024
    print(f"棚の行：{total} ／ うちの言葉が付いた行：{hit}（{hit/max(1,total)*100:.0f}%）")
    print(f"n/ 合計 {kb:.0f}KB（1枚あたり平均 {kb/max(1,nb):.1f}KB）"
          + ("　--dry：書いていない" if dry else ""))
    print(f"a/ は元のまま {akb:.0f}KB（1行も書き換えていない）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
