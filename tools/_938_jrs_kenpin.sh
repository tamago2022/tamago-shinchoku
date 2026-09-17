#!/usr/bin/env bash
# 【938番・2026-09-18】たまごさんが本番で見つけた2点（①上部の重複ブロック ②ページごとの標準要素の抜け）
# を joy-relief-station 側で直すための、ホスト側実行スクリプト。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station がマウントされておらず、
#   GitHub の資格情報も無い。tools/_930_push_joy_footer_fix.sh ／ _936 ／ _937 と同じ理由・同じ形。
#
# ★937番のセッションと同じ joy_push の口を共有しているので、**奪わない**作りにしてある。
#   _930 側は「938が idle でなければ 938 を1回走らせてから、いつも通り 937 へ exec する」。
#   仕事が終わったら status/_938/PHASE に idle と書けば、この口は完全に元通りになる。
#
# PHASE（status/_938/PHASE）:
#   idle … 何もしない（既定）
#   run  … status/_938/run_step.sh をホスト側で実行する（調査・適用・撮影すべてここで切り替える）
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_938"
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
    bash "${STEP}" 2>&1 | tail -n 400
    echo "step rc=${PIPESTATUS[0]}"
  fi
  echo "=== done $(date '+%F %T') ==="
} >>"${LOG}" 2>&1

tail -n 1200 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
exit 0
