#!/usr/bin/env bash
# 【952番・2026-09-19】隠し扉「生きる」＋棚「お役立ち（生活編）」を joy-relief-station に足す。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station がマウントされておらず、
#   GitHub の資格情報も無い。_930 / _936 / _937 / _938 / _951 と同じ理由・同じ形。
#   ホスト側で動く command_ingest.py（joy_push）から1回だけ呼んでもらう。
#
# ★他の番号のセッションと joy_push の口を共有しているので **奪わない**。
#   _930 側は「952が idle でなければ 952 を1回走らせてから、いつも通り先へ進む」。
#   仕事が終わったら status/_952/PHASE に idle と書けば口は完全に元通りになる。
#
# PHASE（status/_952/PHASE）:
#   idle … 何もしない（既定）
#   run  … status/_952/run_step.sh をホスト側で実行する
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_952"
LOG="${WORK}/run.log"
mkdir -p "${WORK}"

PHASE="$(cat "${WORK}/PHASE" 2>/dev/null || echo idle)"
[ "${PHASE}" = "idle" ] && exit 0

# 30秒おきの command_ingest から二重に走らないように1本へ絞る
LOCK="${WORK}/.lock"
if ! mkdir "${LOCK}" 2>/dev/null; then
  if [ -d "${LOCK}" ] && [ -z "$(find "${LOCK}" -maxdepth 0 -mmin -20 2>/dev/null)" ]; then
    rm -rf "${LOCK}" 2>/dev/null || true
    mkdir "${LOCK}" 2>/dev/null || exit 0
  else
    echo "$(date '+%F %T') 他の実行が動いているので見送ります（skip）" >>"${LOG}"
    exit 0
  fi
fi
trap 'rm -rf "${LOCK}" 2>/dev/null || true' EXIT

{
  echo "=== run $(date '+%F %T') phase=${PHASE} ==="
  STEP="${WORK}/run_step.sh"
  if [ ! -f "${STEP}" ]; then
    echo "NG: ${STEP} がありません"
  else
    # Macのメモリが逼迫しているので、必ず1本だけ・優先度を下げて走らせる
    nice -n 10 bash "${STEP}" 2>&1 | tail -n 600
    echo "step rc=${PIPESTATUS[0]}"
  fi
  echo "=== done $(date '+%F %T') ==="
} >>"${LOG}" 2>&1

tail -n 1500 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
exit 0
