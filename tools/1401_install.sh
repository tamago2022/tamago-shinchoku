#!/bin/bash
# 1401番：Chromeタブ掃除便を launchd に載せる（2分おき）。冪等：何回流しても同じ。
# ★心臓（tools/heartbeat.sh）が定期的にこれを呼ぶので、たまごさんが手で流さなくても入る。
set -u
REPO="/Users/mac/tamago/tamago-shinchoku"
LABEL="com.tamago.chrome-tab-cdp"
SRC="$REPO/tools/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"
MARK="$REPO/status/.1401_launchd_ok"

# ★1186号（2026-09-29）恒久停止。
#   この便（2分おき）が 1401_cdp_arm.py を呼び、Chromeを殺して開き直していた。
#   心臓（tools/1401_kidou.py → install_launchd）が10分おきにここを呼ぶので、
#   launchctl unload だけでは必ず復活する。**入れ直す側をここで止める。**
if [ -f "$REPO/status/1401_cdp.nostop" ]; then
  launchctl unload "$DST" >/dev/null 2>&1 || true
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  mkdir -p "$HOME/Library/LaunchAgents/_retired" 2>/dev/null || true
  [ -f "$DST" ] && mv -f "$DST" "$HOME/Library/LaunchAgents/_retired/${LABEL}.plist" 2>/dev/null
  echo "STOPPED: $LABEL（1186号・status/1401_cdp.nostop があるので載せません）"
  exit 0
fi

[ -f "$SRC" ] || { echo "plist が無い: $SRC"; exit 1; }
chmod +x "$REPO/tools/1401_cdp_run.sh" 2>/dev/null || true

if [ -f "$DST" ] && cmp -s "$SRC" "$DST" && launchctl list 2>/dev/null | grep -q "$LABEL"; then
  echo "$(date '+%F %T') 既に入っています（何もしません）" > "$MARK"
  echo "ALREADY: $LABEL"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"
launchctl unload "$DST" >/dev/null 2>&1 || true
launchctl load  "$DST" >/dev/null 2>&1 || true

if launchctl list 2>/dev/null | grep -q "$LABEL"; then
  echo "$(date '+%F %T') 載せました（2分おき）" > "$MARK"
  echo "LOADED: $LABEL（2分おき）"
else
  echo "$(date '+%F %T') ★載せられませんでした" > "$MARK"
  echo "FAILED: $LABEL"
fi
