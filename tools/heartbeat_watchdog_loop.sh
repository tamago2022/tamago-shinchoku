#!/bin/bash
# 心臓(heartbeat.sh)専用ウォッチャーの常駐ループ版。
#
# 2026-09-17（894番・Verifier差し戻し対応）：
#   最初は launchd の StartInterval=30 で heartbeat_watchdog.py を30秒おきに
#   起動する設計にしたが、実機で237秒待っても一度も自動起動されなかった
#   （bootstrap/RunAtLoadの1回だけ動き、その後のStartIntervalが機能していなかった）。
#   StartInterval は「おおよその間隔」で保証が弱いことが実測で確認できたため、
#   常駐して自分でsleepするループ（heartbeat.sh自身と同じ設計）に切り替える。
#
# 役割は1つだけ：10秒おきに status/.heartbeat_alive の年齢を見て、
#   60秒(心臓の4周期)を超えて更新が無ければ launchctl kickstart -k で心臓を叩き起こす。
#   重い処理は一切しない（この処理自体が1秒未満）。
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
while :; do
  python3 "$REPO/tools/heartbeat_watchdog.py" >/dev/null 2>&1 || true
  sleep 10
done
