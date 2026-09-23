#!/bin/bash
# 1401番【Chromeタブ掃除便の中身】2026-09-28
#   ① ポートを開ける係（条件を満たしたときだけ1回だけ開き直す）
#   ② CDPでClaude製タブだけを閉じる
# ★AppleScript / osascript / System Events を1行も呼ばない。
# ★止めたいとき： touch status/1401_cdp.nostop
set -u
REPO="/Users/mac/Desktop/tamago-shinchoku"
[ -f "$REPO/status/1401_cdp.nostop" ] && exit 0
cd "$REPO" || exit 0
echo "--- $(date '+%F %T') ---"
/usr/bin/python3 "$REPO/tools/1401_cdp_arm.py"  2>&1 | tail -3
/usr/bin/python3 "$REPO/tools/1401_tab_cdp.py" --recon --sweep 2>&1 | tail -3
# ログが太らないように刈る
LOG="$REPO/status/1401_cdp_launchd.log"
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 600 ]; then
  tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
