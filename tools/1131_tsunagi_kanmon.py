#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1131番【繋ぎの関所】曲と曲を繋ぐ前に、必ずここを通す。

たまごさん（2026-09-24・原文）:
  「同じ曲名だからってカバーとは限らないからね。繋ぐんであるならば、ちゃんと裏取って繋いでよ。」
  「ただ名前が一緒だから繋いだみたいな間違いは、本当にAI臭いからさ。
    『あ、何も考えてないんだ』『脊髄反射で調べもしないで繋いでるんだな』っていうのが、
    分かる人には分かっちゃうから。」
  「取れないなら繋がない。無いより間違いの方が悪い。」

━━ この関所が通すもの ━━
  ★出典URLが1本以上ある繋ぎだけ。
  根拠（shubetsu）は次のどれか。出典URLと必ずセットで書く。
    credit   … 作詞・作曲のクレジットが原曲と同じ
    official … 公式（本人・レコード会社・公式サイト）が「カバー」と書いている
    jasrac   … JASRAC等のデータベースで同一作品として登録されている
    shiryou  … 信頼できる資料に記載がある

━━ この関所が弾くもの ━━
  ★曲名が同じ → 証拠ではない。弾く。
    （「September」「花」「Volare」… 同じ題名の別の曲は山ほどある。
      実際に棚の中にも「花」が ORANGE RANGE と Fujii Kaze で別々に在る）
  ★アーティスト名が同じ／似ている → 証拠ではない。弾く。
    （akikoの棚に矢野顕子／NON STYLEにHarry Styles の前例。sekisho-artist-song）
  ★年が近い → 「同じ時代」の証拠ではあっても「カバー」の証拠ではない。弾く。
  ★出典URLが無い → 理由が何であれ弾く。

━━ 使い方 ━━
  from importlib import import_module
  kanmon = import_module("1131_tsunagi_kanmon")
  r = kanmon.tooru({
      "from": "pomplamoose:september-earth-wind-and-fire",
      "to":   "earth-wind-fire:september",
      "kind": "originalRef",
      "shubetsu": "official",
      "sources": ["https://..."],
      "verifiedAt": "2026-09-24",
  })
  if not r["ok"]:
      # 繋がない。r["riyuu"] に弾いた理由。
      ...

  コマンドからまとめて：
      python3 tools/1131_tsunagi_kanmon.py status/1131_tsunagi_shinsei.jsonl

━━ 数える ━━
  通した件数・弾いた件数を status/1131_kanmon_daicho.jsonl に必ず残す。
  ★弾き0は「門が効いていない」＝赤。毎日ここを見る。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DAICHO = os.path.join(REPO, "status", "1131_kanmon_daicho.jsonl")

# ★根拠として認めるもの。これ以外は通さない。
SHUBETSU = {
    "credit": "作詞・作曲のクレジットが原曲と同じ",
    "official": "公式（本人・レコード会社・公式サイト）がカバーと書いている",
    "jasrac": "JASRAC等のDBで同一作品として登録されている",
    "shiryou": "信頼できる資料に記載がある",
}

# ★「証拠ではない」もの。ここに当たったら必ず弾く。
DAME = {
    "title_match": "曲名が一致しただけ（同じ題名の別の曲は山ほどある）",
    "artist_match": "アーティスト名が一致しただけ（akiko／NON STYLE の前例）",
    "year_near": "年が近いだけ（それは「同じ時代」の根拠であって、カバーの根拠ではない）",
    "nita": "似ている・影響を受けた（クレジットで確認できていない）",
    "ai": "AIがそう言った（裏を取っていない）",
}

URL = re.compile(r"^https?://[^\s]+$")


def tooru(sh: dict) -> dict:
    """1件の繋ぎ申請を見る。通れば ok=True、弾けば ok=False と理由。"""
    riyuu = []

    f, t = (sh.get("from") or "").strip(), (sh.get("to") or "").strip()
    if not f or not t:
        riyuu.append("from / to が空")
    if f and f == t:
        riyuu.append("自分自身に繋いでいる")

    shubetsu = (sh.get("shubetsu") or "").strip()
    if shubetsu in DAME:
        riyuu.append("根拠にならない：" + DAME[shubetsu])
    elif shubetsu not in SHUBETSU:
        riyuu.append("根拠の種類が無い／知らない種類です（%s）" % (shubetsu or "空"))

    src = [s for s in (sh.get("sources") or []) if isinstance(s, str)]
    yoi = [s for s in src if URL.match(s.strip())]
    if not yoi:
        riyuu.append("出典URLが無い（★これだけで弾く。取れないなら繋がない）")

    hi = (sh.get("verifiedAt") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", hi):
        riyuu.append("確認日（verifiedAt・YYYY-MM-DD）が無い")

    ok = not riyuu
    return {"ok": ok, "from": f, "to": t, "kind": sh.get("kind"),
            "shubetsu": shubetsu, "sources": yoi, "verifiedAt": hi,
            "riyuu": riyuu}


def kazoeru(kekka: list, nani: str = "") -> dict:
    """通した数・弾いた数を台帳に残す。★弾き0は赤。"""
    tooshita = [r for r in kekka if r["ok"]]
    hajita = [r for r in kekka if not r["ok"]]
    rec = {
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "nani": nani,
        "申請": len(kekka),
        "通した": len(tooshita),
        "弾いた": len(hajita),
        "弾いた理由": _kazu([x for r in hajita for x in r["riyuu"]]),
        "赤": (len(kekka) > 0 and len(hajita) == 0),
    }
    os.makedirs(os.path.dirname(DAICHO), exist_ok=True)
    with open(DAICHO, "a", encoding="utf-8") as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def _kazu(xs):
    d = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return dict(sorted(d.items(), key=lambda kv: -kv[1]))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 0
    path = argv[1]
    if not os.path.exists(path):
        print("申請ファイルがありません: %s" % path)
        return 1
    kekka = []
    with open(path, encoding="utf-8") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            kekka.append(tooru(json.loads(line)))
    rec = kazoeru(kekka, nani=os.path.basename(path))
    print("申請 %d ／ 通した %d ／ 弾いた %d" % (rec["申請"], rec["通した"], rec["弾いた"]))
    for r, n in rec["弾いた理由"].items():
        print("   弾いた: %s … %d件" % (r, n))
    if rec["赤"]:
        print("★赤：1件も弾いていません。門が効いていない可能性があります。")
    # 通ったものだけを別ファイルに出す（これが実際に繋いでよい分）
    out = path + ".tootta.jsonl"
    with open(out, "w", encoding="utf-8") as fp:
        for r in kekka:
            if r["ok"]:
                fp.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("通った分 → %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
