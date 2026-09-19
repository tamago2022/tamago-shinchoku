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
LOG = os.path.join(REPO, "status", "heartbeat_watchdog.log")
LABEL = "com.tamago.tamago-shinchoku.heartbeat"
STALE_SECS = 60  # 心臓の1周期15秒の4倍。それでも無反応なら死んでいるとみなす。


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


def alive_age() -> float:
    try:
        return time.time() - os.path.getmtime(ALIVE)
    except OSError:
        return float("inf")  # ファイルが無い＝最初から死んでいる扱い


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
    age = alive_age()
    if age <= STALE_SECS:
        return 0  # 正常。ログも書かない（太らせない）
    log(f"💀 心臓が{age:.0f}秒（{STALE_SECS}秒超）touchしていません。launchdへkickstartを依頼します")
    rc, msg = kickstart()
    if rc == 0:
        log("→ kickstart成功")
    else:
        log(f"→ kickstart失敗 rc={rc} {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
