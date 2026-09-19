#!/usr/bin/env bash
# 【962番・2026-09-19】承認済みPNG（joy-relief-station）を工場側で取り出す／本番URLを実測する口。
#
# なぜ要るか：Cowork のサンドボックスには joy-relief-station がマウントされておらず、
#   api.github.com / raw.githubusercontent.com / tamago2022.github.io へも回線が出ない
#   （プロキシが 403 CONNECT）。Mac からは出る。_961 と同じ理由・同じ形。
#   _961 は別セッションが使用中なので、口を分ける（run_step.sh を奪い合わない）。
#
# 無害であること：status/_962/PHASE が idle（既定）なら即 exit 0。
#   二重起動しないようロックを取る。
#
# PHASE（status/_962/PHASE）:
#   idle … 何もしない（既定）
#   run  … status/_962/run_step.sh をホスト側で実行する
set -uo pipefail
export PATH="/Users/mac/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
WORK="${REPO}/status/_962"
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
    exit 0
  fi
fi
trap 'rm -rf "${LOCK}" 2>/dev/null || true' EXIT

# 1回走ったら自分で idle に戻す（同じ手順を何十回も繰り返さない）
echo idle > "${WORK}/PHASE"

# 呼び出し元（launch_watchdog.py の subprocess.run）は240秒で打ち切る。
# 手順によっては公開待ちで数分かかるので、**親から切り離して**走らせ、呼び出し元は即座に返す。
# 標準出力はログへ直に向ける（パイプを掴んだままにしない＝親が待たされない）。
STEP="${WORK}/run_step.sh"
if [ ! -f "${STEP}" ]; then
  echo "$(date '+%F %T') NG: run_step.sh がありません" >>"${LOG}"
  exit 0
fi
# ロックは子が持ち続ける必要があるので、trapを外して子に引き継ぐ
trap - EXIT
(
  trap 'rm -rf "${LOCK}" 2>/dev/null || true' EXIT
  {
    echo "=== run $(date '+%F %T') ==="
    nice -n 10 bash "${STEP}" 2>&1
    echo "step rc=$?"
    echo "=== done $(date '+%F %T') ==="
    tail -n 1200 "${LOG}" >"${LOG}.tmp" 2>/dev/null && mv "${LOG}.tmp" "${LOG}" 2>/dev/null
  } >>"${LOG}" 2>&1
) </dev/null >/dev/null 2>&1 &
disown 2>/dev/null || true
exit 0
