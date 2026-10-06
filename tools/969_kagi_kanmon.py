#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""969番【関門】鍵の置き場が、また枝分かれしていないか見張る。

なぜ要るか（2026-09-20 実測）
  たまごさんがスマホで 958番の「見た目の版」を開いて「話す」を押したら、
  「Geminiの鍵が空です」だけが出て、鍵を入れる欄がどこにも無かった。
  鍵の欄は ?dev=1 のときしか出ない作りだった。
  同じ形の不具合が 958・959・966 と番号が増えるたびに起きていたので、
  その場を直すのではなく、二度と起きない形にした。その形を守るのがここ。

見張ること（どれか1つでも破れたら赤で止める）
  1. 鍵の置き場の名前は tamago_gemini_key だけ。ほかの名前を作らせない。
  2. 鍵を触るページは、全ページ共通の鍵（assets/kagi/kagi.js）を必ず読んでいる。
  3. 鍵が空のときに「文句を出して終わり」にしない
     （鍵を入れる窓＝TamagoKagi.ask を呼んでいる）。
  4. 1日100円の栓を外していない。

使い方
  python3 tools/969_kagi_kanmon.py
  ぜんぶ通れば 0 を返す。破れていれば 1 を返して、どこが破れたかを日本語で書く。

★この台本は鍵の値を読まない・書かない・出さない。名前しか見ない。
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
CHECK = os.path.join(REPO, "share", "check")

SEI_NA = "tamago_gemini_key"          # 唯一の置き場の名前
KYOUTSU = "assets/kagi/kagi.js"       # 全ページ共通の鍵

# 鍵らしい名前を見つける目。gemini と key の両方が入っている置き場を拾う。
ME_OKIBA = re.compile(r'localStorage\.(?:get|set|remove)Item\(\s*["\']([^"\']*gemini[^"\']*key[^"\']*)["\']',
                      re.IGNORECASE)
# 画面に出す文としての「鍵が空です」だけを拾う（覚え書きの中の同じ言葉は数えない）
ME_KARA = re.compile(r'["\']Gemini ?の?鍵が空')


def yomu(p):
    return io.open(p, encoding="utf-8", errors="ignore").read()


def main():
    if not os.path.isdir(CHECK):
        print("見に行く場所がありません:", CHECK)
        return 1

    warui = []
    mita = 0

    for root, dirs, files in os.walk(CHECK):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for f in files:
            if not (f.endswith(".html") or f.endswith(".js")):
                continue
            p = os.path.join(root, f)
            s = yomu(p)
            okiba = set(ME_OKIBA.findall(s))
            # 話す台本を読んでいるページも「鍵を触るページ」として数える
            shaberu = ("geminilive.js" in s) or ("958-concierge/app958.js" in s)
            if not okiba and not ME_KARA.search(s) and not shaberu:
                continue
            mita += 1
            midashi = os.path.relpath(p, REPO)

            # 1. 名前が枝分かれしていないか
            hoka = sorted(n for n in okiba if n != SEI_NA)
            if hoka:
                warui.append("%s：鍵の置き場が増えています → %s（%s だけにしてください）"
                             % (midashi, "・".join(hoka), SEI_NA))

            # 2. ページなら、共通の鍵を読んでいるか
            if f.endswith(".html") and KYOUTSU not in s:
                warui.append("%s：全ページ共通の鍵を読んでいません（この1行を head に足してください）"
                             % midashi)

            # 3. 鍵が空のときに、入れる窓を出しているか
            if ME_KARA.search(s) and "TamagoKagi" not in s:
                warui.append("%s：鍵が空のとき、文句を出すだけで終わっています"
                             "（鍵を入れる窓を出してください）" % midashi)

            # 4. 100円の栓を外していないか
            if "SAIFU" in s and "capDefault" in s and not re.search(r"capDefault:\s*100", s):
                warui.append("%s：1日100円の栓が変わっています" % midashi)

    if warui:
        print("■ 鍵の関門：止めました（%d件）" % len(warui))
        for w in warui:
            print("  ✕ " + w)
        return 1

    print("■ 鍵の関門：通りました（鍵を触る %d 件を見ました）" % mita)
    print("  ○ 鍵の置き場は %s の1つだけ" % SEI_NA)
    print("  ○ 鍵を触るページは、全ページ共通の鍵を読んでいる")
    print("  ○ 鍵が空でも、その場で入れる窓が出る")
    print("  ○ 1日100円の栓はそのまま")
    return 0


if __name__ == "__main__":
    sys.exit(main())
