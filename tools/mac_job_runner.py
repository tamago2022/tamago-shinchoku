#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""962番：サンドボックス→Mac の「1回きりの使い走り」窓口。

なぜ要るか（実測）：
  Cowork/Dispatchのbashは**Linuxのサンドボックス**で、Macの ~/.claude.json にも
  claude CLI にも手が届かない。Macの上で常に動いているのは心臓(heartbeat.sh)だけ。
  962番では毎回 tools/ にスクリプトを足して top_status.py を書き換える、という
  使い捨ての配線をしていた。**同じ配線を何度もやるのは事故のもと**なので、
  「置けば1回だけ走る」共通の窓口を1本にする。

使い方（サンドボックス側）：
  status/mac_jobs/pending/<名前>.sh を置く → 15秒以内にMacが1回だけ走らせる
  → 結果が status/mac_jobs/done/<名前>.out に出る（スクリプト本体もdone/へ移す）

安全のため：
  - 1本ずつ・同時に走らせない（ロック）
  - 180秒で強制終了
  - 走らせたら必ずdone/へ移す＝**同じものは二度と走らない**
  - 待ちが空ならディレクトリを1回見るだけで即戻る（心臓は重くならない）
"""
import os
import shutil
import subprocess
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(REPO, "status", "mac_jobs")
PEND = os.path.join(JOBS, "pending")
DONE = os.path.join(JOBS, "done")
LOCK = os.path.join(JOBS, ".runner.lock")
TIMEOUT = 180


def run():
    try:
        if not os.path.isdir(PEND):
            return
        names = sorted(n for n in os.listdir(PEND) if n.endswith(".sh"))
        if not names:
            return
    except Exception:
        return
    # 二重に走らせない（古いロックは壊れたものとみなして奪う）
    try:
        if os.path.exists(LOCK) and (time.time() - os.path.getmtime(LOCK)) < TIMEOUT + 60:
            return
        with open(LOCK, "w") as f:
            f.write("%d %s\n" % (os.getpid(), time.strftime("%F %T")))
    except Exception:
        return
    try:
        os.makedirs(DONE, exist_ok=True)
        name = names[0]
        src = os.path.join(PEND, name)
        out = os.path.join(DONE, name[:-3] + ".out")
        started = time.strftime("%F %T")
        try:
            p = subprocess.run(["/bin/bash", src], capture_output=True, text=True,
                               timeout=TIMEOUT, cwd=REPO)
            body = "== %s 開始 / rc=%s ==\n--- stdout ---\n%s\n--- stderr ---\n%s\n" % (
                started, p.returncode, (p.stdout or "")[:200000], (p.stderr or "")[:40000])
        except subprocess.TimeoutExpired:
            body = "== %s 開始 ==\n%d秒で強制終了しました\n" % (started, TIMEOUT)
        except Exception as e:
            body = "== %s 開始 ==\n走らせられませんでした: %r\n" % (started, e)
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write(body)
        except Exception:
            pass
        try:
            shutil.move(src, os.path.join(DONE, name))
        except Exception:
            try:
                os.remove(src)
            except Exception:
                pass
    finally:
        try:
            os.remove(LOCK)
        except Exception:
            try:
                os.utime(LOCK, (0, 0))
            except Exception:
                pass
