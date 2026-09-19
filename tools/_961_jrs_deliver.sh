#!/usr/bin/env bash
# 【961番・2026-09-19】今日直したのに本番に出ていないものを、出し切る。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station がマウントされておらず、
#   GitHub の資格情報も外向きの回線（api.github.com / lovable.dev）も無い。
#   _930 / _936 / _937 / _938 / _951 / _954 と同じ理由・同じ形。
#   ただし joy_push の口はスマホのボタンからしか来ないので、今日は何時間も回っていない。
#   → **5分おきに必ず走る便（tools/machine_status_push.sh）に相乗りする。**
#     この工場の決まり通り、新しい launchd 常駐は増やさない。
#
# 無害であること：
#   status/_961/PHASE が idle（既定）なら即 exit 0。重い処理は一切しない。
#   二重起動しないようロックを取る。1回の実行は run_step.sh の中身次第だが、
#   呼び出し側（machine_status_push.sh）で打ち切り時間を掛けてある。
#
# PHASE（status/_961/PHASE）:
#   idle … 何もしない（既定）
#   run  … status/_961/run_step.sh をホスト側で実行する
set -uo pipefail
export PATH="/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_961"
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
    # Macのメモリが逼迫しているので、必ず1本だけ・優先度を下げて走らせる
    nice -n 10 bash "${STEP}" 2>&1 | tail -n 400
    echo "step rc=${PIPESTATUS[0]}"
  fi
  echo "=== done $(date '+%F %T') ==="
} >>"${LOG}" 2>&1

tail -n 1200 "${LOG}" >"${LOG}.tmp" && mv "${LOG}.tmp" "${LOG}"
exit 0
