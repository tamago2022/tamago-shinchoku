#!/bin/bash
# 止まらない係を launchd に載せる（1分おき）。冪等：何回流しても同じ。
#
# たまごさん（2026-09-26）「launchdで1分おき。『やることがない』を存在させない。」
#
# ★この1本は Mac 側で流す必要がある（サンドボックスからは ~/Library に書けない）。
#   心臓（tools/heartbeat.sh）が毎周これを呼ぶので、たまごさんが手で流さなくても入る。
#   既に入っていれば何もしない＝毎周呼んでも安い。

set -u
REPO="/Users/mac/Desktop/tamago-shinchoku"
LABEL="com.tamago.tomaranai"
SRC="$REPO/tools/$LABEL.plist"
DST="$HOME/Library/LaunchAgents/$LABEL.plist"
MARK="$REPO/status/.tomaranai_launchd_ok"

[ -f "$SRC" ] || { echo "plist が無い: $SRC"; exit 1; }

# 中身が同じで、既に登録されていれば何もしない
if [ -f "$DST" ] && cmp -s "$SRC" "$DST" && launchctl list 2>/dev/null | grep -q "$LABEL"; then
  echo "$(date '+%F %T') 既に入っています（何もしません）" >> "$MARK"
  exit 0
fi

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SRC" "$DST"
launchctl unload "$DST" >/dev/null 2>&1 || true
launchctl load  "$DST" >/dev/null 2>&1 || true

if launchctl list 2>/dev/null | grep -q "$LABEL"; then
  echo "$(date '+%F %T') 載せました（1分おき）" >> "$MARK"
  echo "載せました：$LABEL（1分おき）"
else
  echo "$(date '+%F %T') ★載せられませんでした" >> "$MARK"
  echo "★載せられませんでした。心臓からの呼び出しだけで動きます（tick_every 4）。"
fi
