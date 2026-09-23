#!/bin/bash
# 1401番：Chromeタブ掃除便を launchd に載せる（2分おき）。冪等：何回流しても同じ。
# ★心臓（tools/heartbeat.sh）が定期的にこれを呼ぶので、たまごさんが手で流さなくても入る。
set -u
REPO="/Users/mac/Desktop/tamago-shinchoku"
LABEL="com.tamago.chrome-tab-cdp"
SRC="$REPO/tools/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"
MARK="$REPO/status/.1401_launchd_ok"

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
