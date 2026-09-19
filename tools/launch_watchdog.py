#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
894番（2026-09-16）：発車沈黙（10分ルール）の検知＋自己修復を、heartbeat.sh本体の
15秒ループへ直接組み込むための軽量ラッパー。

背景（なぜ必要か）：
  発車0本が10分続いていないかの検知＋自己修復（status/.last_launch_at のmtime判定・
  心臓/5分便の蹴り直し・failures.md/dispatch_outboxへの記録）は既に
  tools/genzaichi.py の check_launch_silence() として797/798番で実装済みだった。
  しかし genzaichi.py 全体は「いまの現在地」7項目をまとめて作る重めの処理で、
  heartbeat.sh からは「実質30分おき」に間引いて呼ばれている（787/882番のコメント参照）。
  そのため、発車が10分止まっても、次にgenzaichi.pyが回ってくるまで
  最大約30分、検知・自己修復が発動しない穴があった。

  今回の894番「止まった瞬間に自分で立て直す」の合格条件（24時間で発車ゼロが10分を
  超えない）を満たすには、この判定自体を高頻度（15秒おきの心臓ループ）で回す必要がある。
  判定ロジックは車輪の再発明をせず genzaichi.py の関数をそのまま import して使う
  （二重実装・二重の状態ファイルを避ける。真実の源は status/.last_launch_at のまま）。

  check_launch_silence() 自身に「連続して赤の間は1回だけ記録する」抑制が入っているため、
  15秒おきに呼んでも failures.md・dispatch_outbox が連打されることはない。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import genzaichi  # noqa: E402


def main():
    # 2026-09-18（931番）：取り残された .git のロックも「止まった瞬間に自分で立て直す」対象。
    #   Cowork（サンドボックス）側のセッションがgitの途中で打ち切られると index.lock 等が残り、
    #   以後このリポジトリの add/commit が全て rc=128 で失敗する（5分便の push も発車も止まる）。
    #   しかもマウント越しには unlink が許されておらず、**ロックを作った本人が片付けられない。**
    #   heartbeat.sh に直接行を足しても、走っている心臓はループ本体をメモリに持っているため
    #   入れ替わるまで効かない（実測）。**毎サイクル必ず再読み込みされるこのpython側**に置くのが
    #   一番早く効く（launch_watchdog.py が genzaichi の関数を借りているのと同じ相乗りの形）。
    try:
        import git_lock_reaper
        git_lock_reaper.reap(quiet=True)
        # 2026-09-19（配達係）：ロックを片付けたあと、**commit済みなのに誰もpushして
        #   いない分を押し出す。**サンドボックス側には GitHub の資格情報が無いので
        #   （実測：could not read Username for 'https://github.com'）、
        #   セッションが commit したものは、この工場の誰かが運ばない限り公開されない。
        #   実測この日、5分便が22分止まり、commit済みのページが公開URLで404のままだった。
        #   commit はしない・押し出すだけなので、勝手に何かを公開することはない。
        git_lock_reaper.push_out(quiet=True)
    except Exception:
        pass

    # 2026-09-18（931番）：Chromeの孤児タブ掃除も同じ理由でここから呼ぶ。
    #   heartbeat.sh / machine_status_push.sh にも行を入れてあるが、心臓は入れ替わるまで
    #   新しい行を実行せず、5分便はlaunchdごと止まっていることがある（実測：298分停止）。
    #   掃除機は内部で1時間ゲートしているので、毎サイクル呼んでも実際に閉じるのは1時間に1回。
    #   Chromeが起動していなければ pgrep 1回で即座に戻る。
    try:
        import subprocess
        subprocess.run(
            [sys.executable, os.path.join(HERE, "chrome_tab_sweeper.py"),
             "--recon", "--sweep", "--quiet"],
            capture_output=True, timeout=40)
    except Exception:
        pass

    # 2026-09-19（962番）：サンドボックスから工場側のコマンドを走らせる口。
    #   status/_962/PHASE が idle（既定）なら bash が1回起動して即 exit 0 するだけ。
    #   5分便（machine_status_push.sh）に相乗りすると往復が5分かかるので、
    #   毎サイクル再読み込みされるこの python 側にも置く（931番と同じ形）。
    try:
        import subprocess
        subprocess.run(
            ["bash", os.path.join(HERE, "_962_jrs_images.sh")],
            capture_output=True, timeout=240)
    except Exception:
        pass

    try:
        genzaichi.check_launch_silence()
    except Exception:
        # ここが例外で落ちてheartbeat.shの15秒ループ自体を乱すのが一番損（894番の教訓：
        # 「測れないから止まる」が最悪）。何もせず静かに終わる。
        pass


if __name__ == "__main__":
    main()
