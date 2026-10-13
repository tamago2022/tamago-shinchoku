#!/bin/bash
# 1401番【Chromeタブ掃除便の中身】2026-09-28
#   ① ポートを開ける係（条件を満たしたときだけ1回だけ開き直す）
#   ② CDPでClaude製タブだけを閉じる
# ★AppleScript / osascript / System Events を1行も呼ばない。
# ★止めたいとき： touch status/1401_cdp.nostop
set -u
REPO="/Users/mac/tamago/tamago-shinchoku"
[ -f "$REPO/status/1401_cdp.nostop" ] && exit 0
cd "$REPO" || exit 0
echo "--- $(date '+%F %T') ---"
# 急ぎの1本（status/1401_now/*.sh）はここでも拾う＝心臓が混んでいても2分で必ず通る
/usr/bin/python3 "$REPO/tools/1401_kidou.py" 2>&1 | tail -3
/usr/bin/python3 "$REPO/tools/1401_cdp_arm.py"  2>&1 | tail -3
/usr/bin/python3 "$REPO/tools/1401_tab_cdp.py" --recon --sweep 2>&1 | tail -3
# ★CDPが開くまでのあいだ実際に閉じているのはこちら（Chrome宛のAppleScript／System Events不使用）。
#   Chrome 153 は既定プロファイルでの --remote-debugging-port を無効化しており、
#   CDPが開かない（実測：status/oneshot/done/0002_cdp.out）。
#   Chromeへのオートメーション許可は既に降りているので、新しい許可ダイアログは出ない。
#   CDPが開いた瞬間に上の行が本番になり、この行は候補0枚で素通りする。
/usr/bin/python3 "$REPO/tools/chrome_tab_sweeper.py" --recon --sweep 2>&1 | tail -2
# ログが太らないように刈る
LOG="$REPO/status/1401_cdp_launchd.log"
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 600 ]; then
  tail -n 200 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
fi
exit 0
