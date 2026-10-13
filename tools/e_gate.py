#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""絵の門（e_gate）― 絵・映像を、たまごさんの画面に出す前に止める唯一の門。

━━ なぜ作ったか（2026-09-23・たまごさん）━━

  「今、絵本のやつ見たんだけど、こういうのを出してくる時点で違うんだよね。
   さっき貼ったものと、クオリティが明らかに違う。10分の1くらいしかない。
   よくそれを今平気で出してくるねって半分呆れてる。」
  「まず俺の基準を持った分身が必要なんだよね。それこそ鬼監督でいい。
   『このレベルじゃ社長に見せられない』って突き返してくれる存在が必要なんだよ。」

━━ 実測して分かったこと（この工場の中で数えた）━━

  tools/oni_gate.py は **文章の関所**である。規則はR1〜R9の9本で、その全部が
  「書いてある日本語の文字」を見ている（謝罪・diff・水道水コピー・fal の金額…）。
  **絵のピクセルを見る規則は1本も無い。**

  つまり 2026-09-23 の絵本3枚は、oni_gate を通っても**必ず素通りしていた。**
  呼び忘れの問題ではない。**門の種類が違った。**
  文章の門しか無い工場から絵を出した ＝ 検品されていない絵が出た。これが失敗の正体。

━━ この門が見るもの（絵の良し悪しは見ない）━━

  絵の良し悪しは、この工場のAIが一番できないこと（実測済み・自己採点は甘くなる）。
  だからこの門は **「外の目を通ったか」だけを見る。**採点は一切しない。

    ① お手本（正本）が決まっているか        … share/ohon/ohon.json
    ② 出すものを実際に描画した画が有るか      … 静止画の実物
    ③ お手本と並べた画が有るか               … 横に並べたもの
    ④ 外部の判定が有るか                     … 0 か 1 だけ＋理由1行
    ⑤ その判定が 1 か

  どれか1つでも欠けたら **出さない。**
  判定役がどこにも繋がらないときは「判定役が今いない」と書いて、
  **人が見るまで出さない**に倒す。黙って通すことはしない。

━━ 自己採点の禁止（機械で殺す）━━

  判定ファイルに「点数」「/10」「自己評価」の類が入っていたら **その時点で不合格。**
  たまごさん「点数の自己申告は書かない」。書けないようにする。

使い方:
  python3 tools/e_gate.py --check share/check/xxx.html
  python3 tools/e_gate.py --count          # 呼び出し回数を実測で出す
  python3 tools/e_gate.py --self-test      # 門が本当に落とすか見本で試す

終了コード: 0=出してよい / 1=出すな
"""
from __future__ import annotations

import argparse
import datetime
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OHON = os.path.join(REPO, "share", "ohon", "ohon.json")
HANTEI_DIR = os.path.join(REPO, "status", "e_gate", "hantei")
SHOT_DIR = os.path.join(REPO, "status", "e_gate", "shot")
LOG = os.path.join(REPO, "status", "e_gate.log")
JST = datetime.timezone(datetime.timedelta(hours=9))

# これが1つでも本文に入っていたら、その判定は自己採点とみなして落とす。
JIKO_SAITEN = re.compile(
    r"[0-9]\s*/\s*10|[0-9]+\s*点|点数|自己評価|自己採点|score\s*[:：]\s*[0-9]", re.I)

# 絵を出しているページの見分け方。canvas か svg か 画像タグが有れば「絵」とみなす。
E_RE = re.compile(r"<canvas\b|<svg\b|<img\b|<video\b", re.I)


def _log(line: str) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with io.open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.datetime.now(JST).strftime("%F %T"), line))


def count_calls() -> int:
    """呼び出し回数を実測で出す。0回なら門は無いのと同じ。"""
    n = 0
    try:
        with io.open(LOG, encoding="utf-8") as f:
            n = sum(1 for _ in f)
    except Exception:
        pass
    print("e_gate の呼び出し回数（実測）: %d回" % n)
    print("台帳: %s" % LOG)
    try:
        with io.open(LOG, encoding="utf-8") as f:
            for line in f.readlines()[-8:]:
                print("  " + line.rstrip())
    except Exception:
        pass
    return 0


def is_picture_page(path: str) -> bool:
    try:
        raw = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return False
    return bool(E_RE.search(raw))


def _key(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def check(path: str) -> list:
    """止める理由の一覧を返す。空なら出してよい。"""
    stop = []
    key = _key(path)

    # ① お手本が決まっているか
    if not os.path.exists(OHON):
        stop.append("お手本（正本）が決まっていない。share/ohon/ohon.json が無い。")
    else:
        try:
            oh = json.load(io.open(OHON, encoding="utf-8"))
            if not oh.get("画のURL"):
                stop.append("お手本に『画のURL』が入っていない（文章の説明は正本にしない）。")
        except Exception as e:
            stop.append("お手本が読めない: %s" % e)

    # ② 描画した実物
    shots = glob.glob(os.path.join(SHOT_DIR, key + "*"))
    if not shots:
        stop.append("出すものを実際に描画した画が無い。"
                    "コードを読んだだけでは絵は判定できない（キットの規則："
                    "You cannot judge a frame from code）。")

    # ③④⑤ 外部の判定
    hp = os.path.join(HANTEI_DIR, key + ".json")
    if not os.path.exists(hp):
        stop.append("外部の判定が無い。判定役が居ないなら"
                    "『判定役が今いない』と書いて人が見るまで出さない。")
        _fin(path, stop)
        return stop

    try:
        h = json.load(io.open(hp, encoding="utf-8"))
    except Exception as e:
        stop.append("判定が読めない: %s" % e)
        _fin(path, stop)
        return stop

    if not h.get("並べた画"):
        stop.append("お手本と並べた画が無い。並べていない判定は受け取らない。")

    if JIKO_SAITEN.search(json.dumps(h, ensure_ascii=False)):
        stop.append("判定に点数・自己採点が書いてある。"
                    "たまごさん『点数の自己申告は書かない』。0か1だけにする。")

    who = (h.get("判定役") or "").strip()
    if not who or who in ("なし", "self", "claude", "自分"):
        stop.append("判定役がこちらのAI／空になっている。"
                    "絵の良し悪しはこちらが一番できない（実測）。外の目を通すこと。")

    v = h.get("判定")
    if v not in (0, 1):
        stop.append("判定が 0 か 1 になっていない（いまの値: %r）。" % (v,))
    elif v == 0:
        stop.append("外部の判定が 0（社長に見せられない）。理由: %s"
                    % (h.get("理由") or "（理由1行が書かれていない）"))

    if v == 1 and not (h.get("理由") or "").strip():
        stop.append("判定は1だが理由1行が無い。")

    _fin(path, stop)
    return stop


def _fin(path: str, stop: list) -> None:
    _log("%s %s%s" % ("NG" if stop else "OK", os.path.basename(path),
                      ("  理由=" + stop[0][:60]) if stop else ""))


def _self_test() -> int:
    """門が本当に落とすかを見本で試す。
    『実は何も見ていなかった』を防ぐのはこの試験だけ。"""
    import tempfile
    global HANTEI_DIR, SHOT_DIR
    tmp = tempfile.mkdtemp()
    # 見本試験の置き場は /tmp に逃がす。本番の台帳を汚さないため。
    HANTEI_DIR = os.path.join(tmp, "hantei")
    SHOT_DIR = os.path.join(tmp, "shot")
    cases = []

    def run(name, hantei, shot, expect_stop):
        key = "selftest-" + name
        p = os.path.join(tmp, key + ".html")
        io.open(p, "w", encoding="utf-8").write("<canvas id=c></canvas>")
        os.makedirs(HANTEI_DIR, exist_ok=True)
        os.makedirs(SHOT_DIR, exist_ok=True)
        hp = os.path.join(HANTEI_DIR, key + ".json")
        sp = os.path.join(SHOT_DIR, key + ".txt")
        if hantei is not None:
            json.dump(hantei, io.open(hp, "w", encoding="utf-8"), ensure_ascii=False)
        if shot:
            io.open(sp, "w", encoding="utf-8").write("shot")
        stop = check(p)
        ok = bool(stop) == expect_stop
        cases.append((name, ok, stop[:1]))
        for f in (hp, sp):
            if os.path.exists(f):
                os.remove(f)

    good = {"判定": 1, "理由": "お手本と同じ密度に届いている。",
            "判定役": "chatgpt", "並べた画": "share/ohon/narabe.png"}
    run("判定なし", None, True, True)
    run("描画なし", good, False, True)
    run("判定0", dict(good, **{"判定": 0, "理由": "密度が足りない"}), True, True)
    run("自己採点あり", dict(good, **{"理由": "7/10くらい"}), True, True)
    run("判定役が自分", dict(good, **{"判定役": "claude"}), True, True)
    run("並べた画なし", dict(good, **{"並べた画": ""}), True, True)
    run("全部そろっている", good, True, False)

    bad = 0
    for name, ok, why in cases:
        print("%s %-12s %s" % ("OK " if ok else "NG ", name,
                               (why[0][:60] if why else "（止めない）")))
        if not ok:
            bad += 1
    print("\n見本試験：%d件中 %d件 合格" % (len(cases), len(cases) - bad))
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="絵の門 — 絵を出す前に外の目を通す")
    ap.add_argument("--check", nargs="+", default=None)
    ap.add_argument("--count", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.count:
        return count_calls()
    if a.self_test:
        return _self_test()
    if not a.check:
        ap.print_help()
        return 0

    bad = 0
    for p in a.check:
        if not is_picture_page(p):
            print("（絵ではないので絵の門は通しません: %s）" % os.path.basename(p))
            continue
        stop = check(p)
        if not stop:
            print("E_GATE: OK — %s は出してよい" % os.path.basename(p))
            continue
        bad = 1
        print("\n🛑 絵の門が止めました: %s\n" % os.path.basename(p))
        for s in stop:
            print("  ● " + s)
        print()
    return bad


if __name__ == "__main__":
    sys.exit(main())
