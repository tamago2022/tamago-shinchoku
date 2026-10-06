#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【1178番・Bufferの止め札】Bufferに"書く"係を、札1枚で全部止める門。

■ なぜ要るか（2026-09-28 03:0x JST）
  たまごさんの指示：
    「ChatGPTが先にBufferへ10件の予約を入れた。こちらの自動補充が動くと二重投稿になる。
      今すぐ止めろ。」
  実測でいちばん危なかったのは tools/1173_kumi_naoshi.py。
    ・status/1173/.stamp が無い＝まだ一度も走っていない
    ・buffer_waku の門が 2026-09-28 05:34 JST に開く
    ・開いた最初の周回で **予約を全部消して** status/1173/plan.json の10本を入れ直す
    ・その plan.json には、ChatGPTが「死亡動画の疑い」で外した
      「Mariya Takeuchi — 駅」が 9/29 09:00 に入っていた
  → 05:34 に放置していたら、ChatGPTの10本が消えて、外した「駅」が復活していた。

■ この札の効き方
  status/buffer_queue/.TOMERU があるあいだ、tomete() は理由を返す。
  Bufferへ **書く**係（作る・消す・書き替える）は、叩く前にここを通って退く。
  ★API は1回も使わない（0叩き＝1日250回の枠を1つも食わない）。
  ★読むだけの係（一覧を取る）は止めない。実データを見る道は塞がない。

■ 剥がし方（たまごさんが二重投稿の心配が無いと決めたとき）
    rm status/buffer_queue/.TOMERU
  自動では剥がれない。時間で消えたりしない。
"""
import io
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUDA = os.path.join(REPO, "status", "buffer_queue", ".TOMERU")


def tomete():
    """止まっているなら理由の文字列、動いてよければ None。"""
    if not os.path.exists(FUDA):
        return None
    try:
        naze = io.open(FUDA, encoding="utf-8").read().strip()
    except Exception:
        naze = ""
    return "★止め札あり（%s）: %s" % (FUDA, naze or "理由は書かれていない")


def haru(naze):
    os.makedirs(os.path.dirname(FUDA), exist_ok=True)
    io.open(FUDA, "w", encoding="utf-8").write(naze)
    return FUDA


if __name__ == "__main__":
    print(tomete() or "止め札は無い（Bufferへ書いてよい）")
