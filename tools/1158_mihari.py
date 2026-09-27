#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1158番【同時起動の見張り】1分おきに本数を数えて証拠を残す（2026-09-26）

たまごさん：「同時起動の最大本数を1分おきに記録して、24時間で『2本以上になった回数＝0』を示す。」

■ なぜ要るか
  関所（1158_kanmon.py）を入れても、「入れたから大丈夫」は証拠ではない。
  **実際に2本以上が一度も起きていないことを、時刻つきで示せる形にする。**
  鍵が空になった回数も並べて数える（関所を入れた前と後で比べられるように）。

■ 何を記録するか
  status/kanmon_mihari.jsonl に1行1分:
      {"t": 時刻, "n": そのとき走っていたclaudeの本数}
  鍵の中身には一切触らない（値も長さも読まない）。数えるのはプロセスの本数だけ。

■ 入れ方
  tools/top_status.py（心臓が15秒おきに呼ぶ）の末尾から投げっぱなしで呼ぶ。
  1分たっていなければ即座に戻るので、心臓は重くならない。

戻し方（1行）:
  git checkout -- tools/top_status.py && rm -f tools/1158_mihari.py
"""
import io
import json
import os
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
STATUS = os.path.join(REPO, "status")
LOG = os.path.join(STATUS, "kanmon_mihari.jsonl")
KANKAKU = 60
MAX_GYOU = 60 * 24 * 14  # 2週間分だけ持つ


def honsuu():
    """いま走っている claude の本数。

    数えるのは「本物のCLIが走っているプロセス」だけ。
    ・Claude.app（デスクトップ）とそのHelperは別物なので外す
    ・関所自身（1158_kanmon.py）は claude を exec する前なので外す
    """
    try:
        r = subprocess.run(["/bin/ps", "-Ao", "command="],
                           capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    n = 0
    for line in r.stdout.splitlines():
        if "1158_kanmon.py" in line:
            continue
        if ".app/" in line or "Helper" in line:
            continue
        if "/bin/claude" in line or line.strip().endswith("/claude"):
            n += 1
    return n


def main():
    try:
        if time.time() - os.path.getmtime(LOG) < KANKAKU:
            return
    except OSError:
        pass
    n = honsuu()
    if n is None:
        return
    try:
        os.makedirs(STATUS, exist_ok=True)
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "n": n}) + "\n")
        # 伸びっぱなしにしない
        with io.open(LOG, encoding="utf-8") as f:
            gyou = f.readlines()
        if len(gyou) > MAX_GYOU:
            with io.open(LOG, "w", encoding="utf-8") as f:
                f.writelines(gyou[-MAX_GYOU:])
    except Exception:
        pass


if __name__ == "__main__":
    main()
