#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1164番【口で言った分の受け口】URL1本＋喋った言葉を、そのまま投げ込み箱に積む。

たまごさん（2026-09-26・原文）:
  「例えばマイクでURLだけ貼って、口頭で『夏の棚と2020年代の棚、食べ物ならチーズとご飯』
    みたいに言った方がいいのかな。それをあなたが投げ込み箱に登録して、作業が終わった順に
    スライド式でコピーを精査し、関連もちゃんと4つ付けて完了にしてくれると助かる。」

■ 決め（なぜこの形か）
  ・**たまごさんは棚を押さない。**喋った言葉から棚を当てるのはこちら（機械）の仕事。
  ・**当てられた棚だけ入れる。**「夏の棚」と言われて名簿に無ければ、勝手に近い棚へ寄せない。
    当たらなかった言葉は**そのまま返す**（「その言葉の棚がありません」）。★黙って捨てない。
  ・**新しい道を作らない。**積む先は今までと同じ tools/nagekomi.py の add()。
    棚は複数そのまま渡す（1164番で shelves を受けられるようにした）。
  ・**棚の名簿は1か所だけ。**status/public/tana_ichiran.json（棚の正本から吐いたもの）。
    手打ちの棚名を1つも持たない。
  ・★**たまごさんに何も頼まない。**喋った言葉をそのまま食わせれば通る形にする。

■ 使い方（Dispatch／子セッションから）
    python3 tools/nagekomi_kuchi.py \
        --url "https://x.com/…/status/…" \
        --kuchi "夏の棚と2020年代の棚、食べ物ならチーズとご飯"

    # 何が当たるかだけ見る（台帳に1行も書かない・0円）
    python3 tools/nagekomi_kuchi.py --kuchi "夏の棚と2020年代" --dry-run

    # まとめて（1行に URL␣喋った言葉 の形で並べたファイル）
    python3 tools/nagekomi_kuchi.py --file /tmp/kuchi.txt
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import nagekomi as nk                      # noqa: E402  積む先（今までと同じ口）

MEIBO = os.path.join(REPO, "status", "public", "tana_ichiran.json")

# 喋った言葉の区切り。「と」「や」「、」「・」「／」「かつ」…
KUGIRI = re.compile(r"[、，,。．/／・｜|]+|\s+と\s+|\s+や\s+|\s+および\s+|\s+と$|とか")
# 棚の呼び方のしっぽ。「夏の棚」→「夏」
SHIPPO = re.compile(r"(の棚|棚|に入れて|へ入れて|に入れる|に|へ)\s*$")
# 「食べ物なら」のような前置き。棚の名前ではないので落とす
MAEOKI = re.compile(r"^(それと|あと|あとは|それから|あるいは|または|もし|"
                    r"[^\s]{1,8}なら|[^\s]{1,8}だったら)\s*")


def meibo():
    """棚の名簿。★ここが読めなければ棚は1つも当てない（当てずっぽうを作らない）。"""
    try:
        d = json.load(io.open(MEIBO, encoding="utf-8"))
    except Exception as e:
        return [], "棚の名簿が読めません（%s：%s）" % (os.path.basename(MEIBO), type(e).__name__)
    return (d.get("shelves") or []), ""


def norm(s):
    """比べるための形。全角空白・記号・大文字小文字の差で外さないため。"""
    s = str(s or "").strip().lower()
    s = s.replace("　", " ")
    s = re.sub(r"[()（）『』「」【】\[\]・\-−–—_,.、。!！?？'\"]+", "", s)
    return re.sub(r"\s+", "", s)


# ★棚の名前ではない言葉。これを「棚がありません」と報告すると、
#   毎回ゴミが並んでたまごさんが本当の取りこぼしを見つけられない。
SUTE = set("""両方 両方に 全部 ぜんぶ どっちも 以上 あと それ これ その この
方向性 コピー 感じ 方向 よろしく お願い おねがい たのむ 頼む 入れて いれて
やつ もの ほう 方 なら だったら あたり 系 とか みたいな""".split())


def kotoba(kuchi):
    """喋った1文を、棚の呼び名の候補に割る。★前置きと「の棚」は落とす。

    ★割り方は**粗い順**。「猫と鳥」は2つに割りたいが、「家電と動物たち」は
      棚の名前そのものなので割ってはいけない。だから
      **まず丸ごとで当ててみて、当たらなかったときだけ「と」で割る**（wakeru がやる）。
      ここでは「，。／・」など、確実に別の話になる印だけで割る。
    """
    out = []
    for p in KUGIRI.split(str(kuchi or "")):
        p = MAEOKI.sub("", (p or "").strip()).strip()
        p = SHIPPO.sub("", p).strip()
        if p and p not in out:
            out.append(p)
    return out


def komakaku(p):
    """丸ごとでは当たらなかった1片を、「と」「や」で割る。しっぽも落とす。"""
    out = []
    for q in re.split(r"の棚と|棚と|\sと\s|と|や(?=[^\s])", p):
        q = SHIPPO.sub("", (q or "").strip()).strip()
        if q and q not in out:
            out.append(q)
    return out


def ateru(word, shelves, kanzen_dake=False):
    """1つの言葉に棚を当てる。当たらなければ None。
    ★強い順に見る：完全一致 → 棚名が言葉を丸ごと含む → 言葉が棚名を丸ごと含む。
      ★それ以外（1文字かすっただけ）は当てない。別の棚に入る事故のほうが高い。"""
    w = norm(word)
    if not w:
        return None, "空の言葉"
    # ★たまごさんは「夏の棚」と言う。名簿にも「夏の棚」がある。
    #   しっぽを落として「夏」にしてから当てると「夏の終わりに聴きたい棚」とも当たって
    #   2個になり、当たらなかった扱いになっていた（実測）。
    #   → **言った通りの形（夏の棚）を先に見る。**それで1つに決まるならそれ。
    if kanzen_dake or True:
        for s in shelves:
            if norm(s.get("title")) in [w, w + "の棚", w + "棚"]:
                return s, ""
    if kanzen_dake:
        return None, "「%s」と同じ名前の棚がありません" % word
    cand = []
    for s in shelves:
        t = norm(s.get("title"))
        if not t:
            continue
        if w in t or t in w:
            cand.append(s)
    if len(cand) == 1:
        return cand[0], ""
    if len(cand) > 1:
        # ★2つ以上に当たったら選ばない。どれか分からないまま入れるほうが事故
        return None, ("「%s」に当たる棚が%d個あります（%s）。どれか1つに絞ってください"
                      % (word, len(cand), "／".join(str(c.get("title")) for c in cand[:4])))
    return None, "「%s」の棚がありません" % word


def wakeru(kuchi, shelves):
    """喋った1文 → (当たった棚, 当たらなかった理由の列)

    ★丸ごと → 当たらなければ「と」で割る、の2段。
      これで「家電と動物たち」（棚の名前）は割らずに当たり、
      「猫と鳥」（2つの棚）は割れて2件当たる。
    """
    atari, hazure = [], []

    def tasu(s):
        if s and not any(x.get("id") == s.get("id") for x in atari):
            atari.append(s)

    sute = {norm(x) for x in SUTE}
    for p in kotoba(kuchi):
        if norm(p) in sute:
            continue
        # ① 丸ごとで**名前がぴったり**合う棚があるなら、それ。（例：「家電と動物たち」）
        s, _w = ateru(p, shelves, kanzen_dake=True)
        if s:
            tasu(s)
            continue
        # ② 合わないなら「と」「や」で割って、1片ずつ当てる。（例：「猫と鳥」→ 猫の棚／鳥の棚）
        #    ★ここを飛ばすと「夏の棚と2020年代」が「夏の棚」だけになって、
        #      2つ目の棚が黙って消えていた（2026-09-26 実測）。
        hits, nokori = [], []
        for q in komakaku(p):
            if norm(q) in sute:
                continue
            s2, why2 = ateru(q, shelves)
            (hits.append(s2) if s2 else nokori.append(why2))
        if hits:
            for s2 in hits:
                tasu(s2)
            hazure.extend(nokori)
            continue
        # ③ 割っても当たらない。最後に丸ごとの緩い当て方を試して、それでも無ければ理由を返す
        s3, why3 = ateru(p, shelves)
        if s3:
            tasu(s3)
        else:
            hazure.append(why3)
    return atari, hazure


def tsumu(url, kuchi, dry=False):
    """URL＋喋った言葉を1件積む。返すのは「何をどこへ入れたか」1枚。"""
    shelves, why = meibo()
    if why:
        return {"ok": False, "message": why, "shelves": [], "hazure": []}
    atari, hazure = wakeru(kuchi, shelves)
    shelf_arg = [{"id": s.get("id"), "title": s.get("title"), "world": s.get("world") or ""}
                 for s in atari]
    if dry:
        return {"ok": True, "dry": True,
                "message": "（下見）棚 %d件に当てました" % len(shelf_arg),
                "shelves": shelf_arg, "hazure": hazure,
                "kotoba": kotoba(kuchi)}
    if not str(url or "").strip():
        # ★URLが無いなら、喋った言葉だけを1行として置く（今までと同じ置き場）
        r = nk.shiji(kuchi, atari[0]["title"] if atari else None)
        r["shelves"] = shelf_arg
        r["hazure"] = hazure
        return r
    r = nk.add(url, kuchi, shelves=shelf_arg)
    r["shelves"] = shelf_arg
    r["hazure"] = hazure
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--kuchi", default="", help="喋った言葉そのまま")
    ap.add_argument("--file", help="1行に「URL␣喋った言葉」の形で並べたファイル")
    ap.add_argument("--dry-run", action="store_true", dest="dry")
    a = ap.parse_args()

    shori = []
    if a.file:
        for line in io.open(a.file, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^(https?://\S+)\s*(.*)$", line)
            shori.append((m.group(1), m.group(2)) if m else ("", line))
    else:
        if not a.url and not a.kuchi:
            ap.print_help()
            return 2
        shori.append((a.url, a.kuchi))

    ng = 0
    for url, kuchi in shori:
        r = tsumu(url, kuchi, dry=a.dry)
        mark = "○" if r.get("ok") else "×"
        if not r.get("ok"):
            ng += 1
        tana = "／".join(s["title"] for s in r.get("shelves") or []) or "行き先まだ決まっていません"
        print("%s %s" % (mark, r.get("message", "")))
        print("   行き先：%s" % tana)
        for h in (r.get("hazure") or []):
            print("   ★当たらなかった：%s" % h)
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
