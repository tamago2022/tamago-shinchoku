#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1158番【claudeの同時起動を機械で止める関所】(2026-09-26)

たまごさん：「鍵を取り直さなくても、取り合いが起きなければ切れない。」

■ なぜ要るか（実測。推測ではない）
  鍵が消える真因は期限切れではなく**同時起動の競合**：
  /login のOAuthの refreshToken は1回しか使えず、使うと新しい対に入れ替わる。
  2本が同時に更新へ走ると負けた側が invalid_grant を受け取り、
  **その「空っぽの結果」をキーチェーンへ書き戻して勝った側の鍵を消す。**
  （実測：accessToken/refreshToken が両方 長さ0。報告 #79685 / #81937 / #93521）

  status/dojisu_jougen.json は前から「同時上限 1」と出していた。
  **しかし起動口で強制していなかった。** 同ファイルの calibration標本数が証拠：
      2本=534回  3本=89回  4本=8回  5本=1回  6本=1回
  上限を決める係はいたが、止める係がいなかった。この関所がその役。

■ 何をするか
  claude を起動する全経路をこの関所に通し、同時に走る本数を
  status/dojisu_jougen.json の「同時上限」まで（既定1本）に**物理的に**絞る。
  空きスロットを fcntl.flock で1つ取ってから本物の claude を exec する。

■ なぜ flock なのか（PIDファイルではなく）
  PIDファイルは kill -9 で残骸になり、詰まりの原因になる（この工場で実害あり）。
  flock はプロセスが死ねばカーネルが必ず解放する＝**残骸が構造的に出ない。**
  さらに exec 後もロックは生きる（os.set_inheritable でCLOEXECを外す）ので、
  「claude が走っている間だけ」正確に押さえられる。投げっぱなし起動でも効く。

■ 使い方（呼ぶ側は1文字も変えなくていい）
  CLAUDE 定数をこのファイルに差し替えるだけ。引数はそのまま素通しする。
      CLAUDE = os.path.join(HERE, "1158_kanmon.py")

■ 空きが出ないとき
  既定30分まで待つ。それでも空かなければ rc=75 で戻る（EX_TEMPFAIL＝一時的な失敗）。
  **失敗ではなく「待ち」なので、呼ぶ側はやり直し回数に数えないこと。**

戻し方（1行）:
  git checkout -- tools/1158_kanmon.py tools/claude_auth.py
"""
import fcntl
import io
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LOCKDIR = os.path.join(STATUS, "claude_slots")
JOUGEN = os.path.join(STATUS, "dojisu_jougen.json")
LOG = os.path.join(STATUS, "kanmon.jsonl")

MATI_MAX_SEC = int(os.environ.get("KANMON_MATI_SEC", "1800"))  # 30分
SOKO, TENJO = 1, 8
RC_MACHI = 75  # EX_TEMPFAIL


def jougen():
    """同時上限を読む。読めなければ1本（いちばん安全な側）に倒す。"""
    try:
        n = int(json.load(io.open(JOUGEN, encoding="utf-8"))["同時上限"])
    except Exception:
        return 1
    return max(SOKO, min(TENJO, n))


def nokosu(rec):
    """関所の通過記録。鍵の中身は一切扱わない（長さも値も触らない）。"""
    try:
        os.makedirs(STATUS, exist_ok=True)
        rec["t"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def honmono():
    """本物の claude の場所。関所自身を指してしまわないよう必ず実在確認する。"""
    c = os.environ.get("KANMON_CLAUDE_BIN")
    if c and os.path.exists(c):
        return c
    for p in ("~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        p = os.path.expanduser(p)
        if os.path.exists(p):
            return p
    return None


def toru(n):
    """空きスロットを1つ取る。取れたら fd を返す。取れなければ None。"""
    os.makedirs(LOCKDIR, exist_ok=True)
    for i in range(n):
        fd = None
        try:
            fd = os.open(os.path.join(LOCKDIR, "slot%d.lock" % i),
                         os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            if fd is not None:
                os.close(fd)
            continue
        # exec してもロックを離さない（PEP446でos.openはCLOEXEC付きなので外す）
        os.set_inheritable(fd, True)
        try:
            os.write(fd, ("%d\n" % os.getpid()).encode())
        except Exception:
            pass
        return fd
    return None


def main():
    argv = sys.argv[1:]
    claude = honmono()
    if claude is None:
        sys.stderr.write("1158関所: claude 本体が見つかりません\n")
        return 127

    # ---- 入れ子は素通しする（2026-09-26）----
    # claude の中からさらに claude が起動される経路（hook・MCP・孫プロセス）が
    # あると、上限1本のとき子が親のスロットを30分待って**必ず詰まる**。
    # 親が既にスロットを持っているなら、その中の起動は数えない。
    if os.environ.get("KANMON_SLOT"):
        os.execv(claude, [claude] + argv)

    hajime = time.time()
    n = jougen()
    while True:
        fd = toru(n)
        if fd is not None:
            break
        matta = time.time() - hajime
        if matta > MATI_MAX_SEC:
            nokosu({"結果": "待ちきれず戻した", "上限": n, "待ち秒": int(matta)})
            sys.stderr.write(
                "1158関所: %d本すべて使用中。%d秒待って空かないので戻します"
                "（失敗ではなく待ち。やり直し回数に数えないこと）\n" % (n, int(matta)))
            return RC_MACHI
        time.sleep(1.0 + random.random())  # 同時に群がらないよう少しずらす
        n = jougen()  # 待っている間に上限が変わることがある

    matta = int(time.time() - hajime)
    if matta > 0:
        nokosu({"結果": "待ってから通した", "上限": n, "待ち秒": matta})
    os.environ["KANMON_SLOT"] = "1"  # この下で起きる孫の claude は素通しさせる
    os.execv(claude, [claude] + argv)  # ロックは claude が死ぬまで生きる


if __name__ == "__main__":
    sys.exit(main())
