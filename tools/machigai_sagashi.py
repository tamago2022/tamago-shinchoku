#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/machigai_sagashi.py ── 間違い探し（全曲総当たり・0円）

たまごさん（2026-09-24）:
  「仕入れるなり間違いを探すなり、何かしらやっててくださいよ。」

★ここは「空いたら回す順番」の1番。★AIを1回も呼ばない・外へ1回も出ない＝0円。
★だからクレジットが天井でも止めない。工場が黙る時間を作らない。

見るもの（全部 coverGuide.ts を読むだけ）
  ① メイン不在        … title はあるのに youtubeId も altYoutubeIds も無い
  ② 空の紹介文        … note が空／短すぎる（15文字未満）
  ③ 途中で切れた紹介文 … 「。」「、」「…」で終わらず、助詞で終わっている
  ④ 年の矛盾          … year が 1900未満 / 来年より先
  ⑤ 同じ棚に同じid    … 1つの棚に同じ曲idが2回
  ⑥ 動画idの形が変    … YouTubeのidは11文字。違うものは繋がらない

結果は status/machigai.json に置く。★直さない。見つけて数えるだけ。

使い方
  python3 tools/machigai_sagashi.py
  python3 tools/machigai_sagashi.py --ue 20     # 多い順に20件だけ見る
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ST = os.path.join(REPO, "status")
SEKISHO = os.path.join(HERE, "sekisho")
for p in (HERE, SEKISHO):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = os.path.join(ST, "machigai.json")

YT11 = re.compile(r"^[A-Za-z0-9_-]{11}$")
OWARI_NG = ("は", "が", "を", "に", "へ", "と", "で", "も", "の", "や", "から", "より")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def shiraberu(ue=None):
    import main_kanmon as MK
    import parse_coverguide_deep as deep

    path = MK.find_coverguide()
    if not path:
        out = {"at": now(), "yometa": False,
               "naze": "coverGuide.ts が見つかりません（このMac上に joy-relief-station が無い）"}
        _write(out)
        return out

    artists = deep.parse_deep(path)
    kyou = time.localtime().tm_year
    mi = {k: [] for k in ("mainFuzai", "karaNote", "kireteru",
                          "toshiMujun", "onajiId", "idNoKatachi")}
    zen = 0

    for a in artists:
        mita = {}
        for s in a.get("songs", []):
            zen += 1
            base = {"artist": a.get("name"), "artistId": a.get("id"),
                    "id": s.get("id"), "title": s.get("title"),
                    "line": s.get("line")}

            # ① メイン不在
            if not MK.kanmon(s)[0]:
                mi["mainFuzai"].append(base)

            # ② 空の紹介文 ③ 途中で切れている
            note = (s.get("note") or "").strip()
            if not note:
                mi["karaNote"].append(dict(base, naze="紹介文が空"))
            elif len(note) < 15:
                mi["karaNote"].append(dict(base, naze="紹介文が%d文字しかない" % len(note)))
            elif note[-1] not in "。」）!?！？…" and note.endswith(OWARI_NG):
                mi["kireteru"].append(dict(base, owari=note[-12:]))

            # ④ 年の矛盾
            y = s.get("year")
            try:
                if y is not None and (int(y) < 1900 or int(y) > kyou + 1):
                    mi["toshiMujun"].append(dict(base, year=y))
            except Exception:
                pass

            # ⑤ 同じ棚に同じid
            sid = s.get("id")
            if sid:
                if sid in mita:
                    mi["onajiId"].append(dict(base, mae=mita[sid]))
                else:
                    mita[sid] = s.get("line")

            # ⑥ 動画idの形
            yt = (s.get("youtubeId") or "").strip()
            if yt and not YT11.match(yt):
                mi["idNoKatachi"].append(dict(base, youtubeId=yt))

    kazu = {k: len(v) for k, v in mi.items()}
    out = {
        "at": now(), "yometa": True, "coverGuide": path,
        "kyokuZen": zen,
        "kazu": kazu,
        "goukei": sum(kazu.values()),
        "midashi": {
            "mainFuzai": "★メイン不在（タイトルはあるが音源・動画が無い）",
            "karaNote": "紹介文が空／短すぎる",
            "kireteru": "紹介文が途中で切れている",
            "toshiMujun": "年がおかしい",
            "onajiId": "同じ棚に同じ曲が2回",
            "idNoKatachi": "動画idの形がYouTubeのものではない",
        },
        "meisai": {k: v[: (ue or 200)] for k, v in mi.items()},
        "note": "見つけて数えるだけ。直さない。0円（AIを呼ばない・外へ出ない）。",
    }
    _write(out)
    return out


def _write(out):
    os.makedirs(ST, exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    os.replace(tmp, OUT)


def main():
    a = sys.argv[1:]
    ue = int(a[a.index("--ue") + 1]) if "--ue" in a else None
    o = shiraberu(ue)
    if not o.get("yometa"):
        print("読めませんでした：%s" % o.get("naze"))
        return 2
    print("全曲 %d 件を総当たり。見つかった間違い 合計 %d 件" % (o["kyokuZen"], o["goukei"]))
    for k, v in sorted(o["kazu"].items(), key=lambda x: -x[1]):
        if v:
            print("  %-6d %s" % (v, o["midashi"][k]))
    print("→ %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
