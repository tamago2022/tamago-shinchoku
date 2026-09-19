#!/usr/bin/env python3
"""心臓(heartbeat.sh)専用の外部ウォッチャー。1回の呼び出しは1秒未満で終わる軽量判定。

2026-09-17（894番・Verifier差し戻し対応・実機で2段階の失敗を踏んで確定した設計）：

  【失敗1】launchdの KeepAlive=true だけに頼る設計を実機で検証したところ、
    `kill -9`（SIGKILL）で心臓を殺した後、launchdは自動では再起動しなかった
    （129秒待っても復旧せず。手動で `launchctl kickstart -k` を呼んだ時だけ即座に起動した）。
    KeepAliveの「異常終了で再起動する」判定は、シグナルによる強制終了を
    必ずしもトリガーにしないOS側の癖があるとみられる。

  【失敗2】そこで「このスクリプトをlaunchdのStartInterval=30で30秒おきに起動する」方式へ
    切り替えたが、bootstrap直後のRunAtLoadで1回動いた後、237秒待っても一度も
    自動再実行されなかった（実機ログ status/heartbeat_watchdog.log が空のまま）。
    StartIntervalはAppleの実装上「おおよその間隔」でしかなく、保証が弱いことが実測で判明した。

  【確定した形】`tools/heartbeat_watchdog_loop.sh`（常駐bashループ・10秒ごとにこのスクリプトを
    呼ぶだけ）を launchd の KeepAlive=true で動かし、判定本体はこのファイルに残す
    （二重実装を避けるため、判定ロジックはここだけに置く）。
    判定材料は心臓が毎周期(15秒)必ずtouchする status/.heartbeat_alive の更新時刻のみ。
    60秒（心臓の4周期分）更新が無ければ「死んでいる」とみなし、
    `launchctl kickstart -k` で launchd管理下の心臓ジョブを明示的に叩き起こす。

    実測（2026-09-17 01:06:50に心臓をkill -9→01:07:41に復旧確認）：**50.4秒で自己復旧**。
    3分（180秒）の合格ラインに対して十分な余裕がある。

  なぜウォッチャーのループ(heartbeat_watchdog_loop.sh)自体は死なない前提にできるか：
    心臓(heartbeat.sh)は毎周期15個以上の子プロセスを起動する重い処理だが、
    ウォッチャーは「ファイルの更新時刻を見るだけ」の軽量処理のみで、落ちる要因がほぼ無い。
    それでも万一ウォッチャーが死んだ場合は、既存の machine_status_push.sh（5分便）内の
    「.heartbeat_aliveが180秒古ければ心臓をkill&再起動」ロジックが保険として残っている
    （多層防御：ウォッチャー常駐ループ→5分便→heartbeat.sh自身の二重起動防止、の3層）。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIVE = os.path.join(REPO, "status", ".heartbeat_alive")
PROGRESS = os.path.join(REPO, "status", ".heartbeat_progress")
LOG = os.path.join(REPO, "status", "heartbeat_watchdog.log")
LABEL = "com.tamago.tamago-shinchoku.heartbeat"

# ---- 2026-09-22（1018番）1つの信号で「生死」と「進行」を兼務させるのをやめた ----
# 上のdocstringの【確定した形】には「心臓が毎周期(15秒)必ずtouchする」と書いてあるが、
# **これは事実ではなかった。**心臓は1周の中で auto_launcher(最大45秒)と
# command_ingest(最大45秒)を順番に待つので、1周は普通に60〜140秒かかる。
# 実測（このログ全349件）：死亡宣告の中央値73秒・最小60秒。600秒超はたった3件。
#   ＝346件（99.1%）は**生きている心臓を殺していた。**
#   kickstart -k は kill を伴うため、殺された拍子に auto_launcher.py が孤児化して
#   ロックを握ったまま残り、投げた仕事が一度も走りきらなくなっていた。
# Kubernetes が liveness と readiness を分けているのと同じ理由。
# liveness に「仕事が終わったか」を混ぜると、仕事が重いだけで再起動ループになる。
#   ALIVE    … 心臓の中の専用子プロセスが5秒ごとに打つ。仕事に邪魔されない＝純粋な生死。
#   PROGRESS … 1周を回りきった時だけ書かれる。本当に固まった時だけ古くなる。
# 判定：
#   鼓動が止まった          → 本当に死んだ。今までどおり即kickstart（実測50.4秒で復旧）。
#   鼓動はあるが進行が古い  → 本当に固まった。ここで初めてkickstart。
#   鼓動があり進行も新しい  → 何秒かかっていようが健康。**絶対に触らない。**
STALE_SECS = 60        # 鼓動は5秒おき。12回分打たなければ、シェルごと落ちている。
STUCK_SECS = 600       # 1周の実測最長は約140秒。その4倍以上なら本当に固まっている。


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n"
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line)
        # 太らせない：5000行を超えたら末尾500行に刈る
        with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if len(lines) > 5000:
            with open(LOG, "w", encoding="utf-8") as f:
                f.writelines(lines[-500:])
    except Exception:
        pass


def age_of(path: str, missing: float = float("inf")) -> float:
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return missing


def alive_age() -> float:
    return age_of(ALIVE)


def kickstart() -> tuple[int, str]:
    uid = os.getuid()
    try:
        r = subprocess.run(
            ["launchctl", "kickstart", "-k", f"gui/{uid}/{LABEL}"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return r.returncode, (r.stderr or r.stdout or "").strip()
    except Exception as e:  # noqa: BLE001
        return -1, str(e)


def main() -> int:
    beat = age_of(ALIVE)
    # 進行ファイルが無い＝旧版の心臓がまだ走っている／起動直後。
    # ここを「無い＝固まっている」と読むと、入れ替えの最中に見張りが暴走して
    # 10秒ごとにkickstartを打ち続ける（＝直した側が新しい誤殺を作る）。
    # 鼓動さえあれば生きているのは確かなので、進行が無い間は0（＝健康）として扱う。
    prog = age_of(PROGRESS, missing=0.0)

    if beat > STALE_SECS:
        reason = f"💀 鼓動が{beat:.0f}秒（{STALE_SECS}秒超）止まっています＝心臓ごと落ちた"
    elif prog > STUCK_SECS:
        # 鼓動はあるのに1周が終わらない＝本当に固まっている。ここは残す価値のある再起動。
        reason = (
            f"🧊 鼓動はある（{beat:.0f}秒前）のに、1周が{prog:.0f}秒"
            f"（{STUCK_SECS}秒超）終わっていません＝本当に固まっています"
        )
    else:
        # 何秒仕事にかかっていようが、生きていて周っているなら健康。触らない。
        # 2026-09-22以前はここで殺していた（349件中346件がこのケース＝99.1%が誤殺）。
        return 0

    log(f"{reason}。launchdへkickstartを依頼します")
    rc, msg = kickstart()
    if rc == 0:
        log("→ kickstart成功")
    else:
        log(f"→ kickstart失敗 rc={rc} {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
