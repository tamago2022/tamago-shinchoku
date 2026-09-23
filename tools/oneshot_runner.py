#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""977番（Cowork側から設置）サンドボックス→Macの「一発コマンド」窓口。

■ なぜ要るか（2026-09-21 実測）
  Cowork(サンドボックス)からは Mac の ~/ が見えない（マウントは
  Desktop/tamago-shinchoku だけ）。また api.github.com / raw.githubusercontent.com へは
  回線が出ない（proxyが blocked-by-allowlist で403を返す。github.com は200）。
  → Obsidian Vault を読む・gh を叩く、はどちらも Mac 側でしか出来ない。

■ 動き方
  status/oneshot/pending/*.sh を拾って bash で実行し、
  status/oneshot/done/<名前>.out（標準出力＋標準エラー）と .rc（終了コード）を書く。
  拾った票は running/ へ移してから実行するので二重実行しない。
  待ちが空なら1回 listdir するだけで即座に戻る＝心臓は重くならない。
  status/ は .gitignore 済みなので、票も結果も公開リポには入らない。

■ 心臓への入れ方（枷5番「Pythonファイルへ1行足すのが正しい入れ方」に従う）
  tools/top_status.py（心臓が毎周回で呼ぶ＝毎回読み直される）の末尾から投げっぱなしで呼ぶ。
"""
import io
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "status", "oneshot")
PEND = os.path.join(BASE, "pending")
RUN = os.path.join(BASE, "running")
DONE = os.path.join(BASE, "done")
TIMEOUT_SEC = 240
MAX_OUT = 400000


RESCUE_AFTER_SEC = 600   # running/ に これだけ居座ったら「心臓ごと殺された」と見て拾い直す
RESCUE_MAX = 2           # 同じ票を拾い直す回数の上限（無限に回さない）


def rescue():
    """1144番（2026-09-25 実測）止まったら自動で再開する。

    心臓(tools/heartbeat.sh)は再起動のたびに自分のプロセスグループを kill -9 する。
    この係は心臓の子なので、長い票は途中で殺され、running/ に .sh が残ったまま
    二度と走らない（9/24から kansei が本番に出なかったのはこれ）。
    → 10分以上 running/ に居る票は、pending/ に戻して次の周回で走らせる。
      戻した回数は .try に記録し、2回で諦めて done/ に「拾い直しても終わらない」と書く。
    """
    if not os.path.isdir(RUN):
        return
    now = time.time()
    for n in sorted(os.listdir(RUN)):
        if not n.endswith(".sh"):
            continue
        p = os.path.join(RUN, n)
        try:
            if now - os.path.getmtime(p) < RESCUE_AFTER_SEC:
                continue
        except Exception:
            continue
        stem = n[:-3]
        tryf = os.path.join(RUN, stem + ".try")
        try:
            cnt = int(io.open(tryf).read().strip() or 0)
        except Exception:
            cnt = 0
        if cnt >= RESCUE_MAX:
            try:
                with io.open(os.path.join(DONE, stem + ".out"), "w", encoding="utf-8") as f:
                    f.write("拾い直しを%d回しても終わりませんでした（心臓が殺している疑い）。"
                            "長い仕事は tools/1144_hanareru.py で切り離して走らせる。\n" % cnt)
                with io.open(os.path.join(DONE, stem + ".rc"), "w", encoding="utf-8") as f:
                    f.write("126 rescue-gaveup\n")
                os.remove(p)
                os.remove(tryf)
            except Exception:
                pass
            continue
        try:
            with io.open(tryf, "w", encoding="utf-8") as f:
                f.write("%d\n" % (cnt + 1))
            os.replace(p, os.path.join(PEND, n))
        except Exception:
            pass


def main():
    if not os.path.isdir(PEND):
        return
    for d in (RUN, DONE):
        os.makedirs(d, exist_ok=True)
    rescue()
    names = sorted(n for n in os.listdir(PEND) if n.endswith(".sh"))
    if not names:
        return
    for name in names[:2]:
        src = os.path.join(PEND, name)
        dst = os.path.join(RUN, name)
        try:
            os.replace(src, dst)
        except Exception:
            continue
        out, rc = "", -1
        started = time.time()
        try:
            p = subprocess.run(["/bin/bash", dst], cwd=REPO, capture_output=True,
                               timeout=TIMEOUT_SEC)
            out = (p.stdout or b"").decode("utf-8", "replace") + \
                  (p.stderr or b"").decode("utf-8", "replace")
            rc = p.returncode
        except subprocess.TimeoutExpired:
            out, rc = "TIMEOUT %ds\n" % TIMEOUT_SEC, 124
        except Exception as e:
            out, rc = "ERROR %s\n" % e, 125
        stem = name[:-3]
        try:
            with io.open(os.path.join(DONE, stem + ".out"), "w", encoding="utf-8") as f:
                f.write(out[:MAX_OUT])
            with io.open(os.path.join(DONE, stem + ".rc"), "w", encoding="utf-8") as f:
                f.write("%d %.1fs\n" % (rc, time.time() - started))
        except Exception:
            pass
        try:
            os.remove(dst)
        except Exception:
            pass
        try:
            os.remove(os.path.join(RUN, stem + ".try"))
        except Exception:
            pass


if __name__ == "__main__":
    main()
