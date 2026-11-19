#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""フェスの名簿と、棚の穴を数える。

たまごさん（2026-09-22）:
  「フジロックをはじめ、有名なフェスに出てるアーティストは全員入れるくらいの勢いでいてほしい。
   調べて、とりあえず4〜5曲ずつは入れておくとかさ。要するに、誰が来ても
   『いや、それはないですね』っていう状態をなくしたい。」

■ この道具がやること
  1. `status/fes_meibo/<fes>.json`（公式サイトのラインナップから取った名簿）を読む
  2. 棚（coverGuide.ts）と突き合わせて、**まだ1曲も無いアーティスト＝穴**を数える
  3. **「それはありませんね率」**＝穴 ÷ 出演者 を出す
  4. 穴を、有名な順（名簿の上から＝ヘッドライナー順）に並べた仕入れ待ち行列にする

■ この道具がやらないこと
  ★**棚に入れない。**書き込むのは status/fes_meibo/ だけ。
  ★**名前が一致したことを「同じ人だ」と確定しない。**
    ここでの突き合わせは**数を数えるため**だけのもので、
    実際に曲を入れるときは必ず入荷の関所（tools/nyuka_sekisho.py 門2）と
    skill sekisho-artist-song を通す。名前一致で棚に入れるのが例の事故（akiko／矢野顕子）。
    そのため、一致したものには "howMatched": "名前一致（同定はまだ）" を付けて残す。

■ 出演者ではないもの
  フェスの名簿にはトーク・ワークショップ・サーカスも混ざる。
  それらを「棚に無い＝穴」と数えると率が嘘になるので、kind で仕分けて率から外す。
"""

import io
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEIBO = os.path.join(REPO, "status", "fes_meibo")

# 棚の本体は非公開リポジトリ側にある。あるものを上から順に使う。
SHELF_CANDIDATES = (
    os.path.join(os.path.dirname(REPO), "joy-relief-station", "src", "lib", "coverGuide.ts"),
    os.path.join(REPO, "..", "joy-relief-station", "src", "lib", "coverGuide.ts"),
    os.path.join(REPO, "status", "_936", "keep", "src", "lib", "coverGuide.ts"),
)

# 出演者ではない枠（率から外す）
NOT_A_MUSICIAN = (
    "トーク", "ワークショップ", "ヨガ", "サーカス", "カフェ トーク",
    "アトミック・カフェ トーク",
)
# 出演者だが、棚に入れる対象として扱いにくいもの（DJセット・別名義の付記）
SIDE_FORMS = ("(DJ)", "(DJ Set)", "(DJ SET)", "DJs", "(Night Ambient Set)",
              "SOUND CLASH")


def norm(s):
    """突き合わせ用に名前をならす。**ならしても別人は別人**なので、
    ここで一致したことは『同じ人らしい』までしか意味しない。"""
    s = (s or "").lower()
    s = re.sub(r"[（(\[].*?[）)\]]", " ", s)          # 括弧の中は落とす
    s = s.replace("＆", "&").replace("・", " ").replace("’", "'")
    s = re.sub(r"\b(the|a|an)\b", " ", s)
    s = re.sub(r"[^0-9a-z぀-ヿ一-鿿]+", "", s)
    return s


def load_shelf():
    path = next((p for p in SHELF_CANDIDATES if os.path.exists(p)), None)
    if not path:
        return {}, None
    src = io.open(path, encoding="utf-8", errors="ignore").read()
    shelf = {}
    for m in re.finditer(r'\{ id: "([^"]+)", name: "([^"]+)"(.{0,400}?)\], songs:',
                         src, re.S):
        aid, name, mid = m.group(1), m.group(2), m.group(3)
        names = [name] + re.findall(r'"([^"]+)"', (re.search(
            r'aliases: \[([^\]]*)\]', mid) or re.match(r"()", "")).group(1)
            if re.search(r'aliases: \[([^\]]*)\]', mid) else "")
        for n in names:
            shelf.setdefault(norm(n), aid)
    # aliases を拾えなかった棚も name だけで入れておく
    for m in re.finditer(r'\{ id: "([^"]+)", name: "([^"]+)"', src):
        shelf.setdefault(norm(m.group(2)), m.group(1))
    return shelf, path


def kind_of(name):
    if any(w in name for w in NOT_A_MUSICIAN):
        return "出演者ではない枠"
    if any(w in name for w in SIDE_FORMS):
        return "DJ・別形態"
    return "出演者"


def load_kouho():
    """仕入れ候補（status/shiire_kouho/*.json）に名前が積んであるアーティスト。

    ★これは**棚ではない。**棚に出すかどうかはたまごさんの判断（憲法・棚の最終判断）。
    ここで数えるのは「もう素材が揃っていて、あとは判断待ち」の組。
    率を2本出すのは、**棚の率（本当の数字）を薄めないため**。
    """
    d = os.path.join(REPO, "status", "shiire_kouho")
    got = {}
    if not os.path.isdir(d):
        return got
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        try:
            o = json.load(io.open(os.path.join(d, fn), encoding="utf-8"))
        except Exception:
            continue
        nm = ((o.get("entry") or {}).get("artist") or "").strip()
        if nm and (o.get("candidates") or []):
            got[norm(nm)] = {"file": fn, "n": len(o["candidates"])}
    return got


def coverage():
    shelf, shelf_path = load_shelf()
    kouho = load_kouho()
    files = sorted(f for f in os.listdir(MEIBO)
                   if f.endswith(".json") and not f.startswith("_"))
    report = {"shelfSource": shelf_path, "shelfArtists": len(shelf),
              "festivals": []}
    for fn in files:
        d = json.load(io.open(os.path.join(MEIBO, fn), encoding="utf-8"))
        have, holes, skipped = [], [], []
        for i, a in enumerate(d.get("artists") or []):
            k = kind_of(a)
            if k == "出演者ではない枠":
                skipped.append(a)
                continue
            aid = shelf.get(norm(a))
            row = {"rank": i + 1, "name": a, "kind": k}
            if aid:
                row["shelfId"] = aid
                row["howMatched"] = "名前一致（同定はまだ）"
                have.append(row)
            else:
                k = kouho.get(norm(a))
                if k:
                    row["kouho"] = k["n"]
                    row["kouhoFile"] = k["file"]
                holes.append(row)
        total = len(have) + len(holes)
        stocked = len([h for h in holes if h.get("kouho")])
        report["festivals"].append({
            "festival": d.get("festival"), "source": d.get("source"),
            "takenAt": d.get("takenAt"),
            "listed": len(d.get("artists") or []),
            "counted": total, "have": len(have), "holes": len(holes),
            "notMusicians": len(skipped),
            "naiRate": round(len(holes) * 100.0 / total, 1) if total else 0.0,
            # ★候補まで積んだ分を引いた率。棚の率とは別物として必ず両方出す。
            "stocked": stocked,
            "naiRateWithKouho": round((len(holes) - stocked) * 100.0 / total, 1) if total else 0.0,
            "queue": holes,      # 有名な順＝名簿の上から。これが仕入れ待ち行列
            "already": have,
        })
    return report


def main():
    r = coverage()
    _w(os.path.join(MEIBO, "_coverage.json"), r)
    if not r["shelfSource"]:
        print("★赤：棚（coverGuide.ts）が見つからない。率が数えられない。")
        return 1
    print("棚のアーティスト %d組（%s）" % (r["shelfArtists"], r["shelfSource"]))
    for f in r["festivals"]:
        print("%s ／ 数えた%d組：棚にある%d・穴%d ／ それはありませんね率 %.1f%%"
              % (f["festival"], f["counted"], f["have"], f["holes"], f["naiRate"]))
        print("   └ 候補まで積んだ %d組 ／ 候補まで含めた率 %.1f%%（★棚出しはたまごさんの判断）"
              % (f.get("stocked", 0), f.get("naiRateWithKouho", f["naiRate"])))
        if "--queue" in sys.argv:
            for h in f["queue"][:40]:
                print("   %3d. %s" % (h["rank"], h["name"]))
    return 0


def _w(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(
        json.dumps(o, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
