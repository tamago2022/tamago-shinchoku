#!/usr/bin/env bash
# 【954番・2026-09-19】たまごさん指摘「Xの投稿ページで本文に動画が出ず、画面半分が緑の空白になる」。
#   joy-relief-station 側で直すためのホスト側の口。_938 / _951 と同じ形。**exec で奪わない**。
#   status/_954/PHASE が idle なら即 exit 0（＝完全に無害）。用が済んだら idle に戻す。
set -uo pipefail
export PATH="/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_954"
LOG="${WORK}/run.log"
mkdir -p "${WORK}"

PHASE="$(cat "${WORK}/PHASE" 2>/dev/null || echo idle)"
[ "${PHASE}" = "idle" ] && exit 0

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
    nice -n 10 bash "${STEP}" 2>&1 | tail -n 500
    echo "step rc=${PIPESTATUS[0]}"
  fi
  echo "=== done $(date '+%F %T') ==="
} >>"${LOG}" 2>&1

tail -n 1200 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
exit 0
