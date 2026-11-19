#!/bin/bash
# 押すだけ：①心臓を起こす ②Devinの発車線(launchd)を載せる ③その場で1本発車 ④成績表を作る
# ★これを押すのは1回だけ。次からはlaunchdが60秒おきに勝手にやる（再起動しても戻る）。
cd "$(dirname "$0")" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
echo "=== $(date '+%F %T') 起こします ==="

if ! pgrep -f "tools/heartbeat.sh" >/dev/null 2>&1; then
  echo "心臓が止まっていたので起こす"
  nohup bash tools/heartbeat.sh >/dev/null 2>&1 &
  sleep 2
else
  echo "心臓は動いている"
fi

PL="$HOME/Library/LaunchAgents/com.tamago.wakuban.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PL" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.tamago.wakuban</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$PWD/tools/1500_tick.sh</string>
  </array>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$PWD/status/1500_launchd.out</string>
  <key>StandardErrorPath</key><string>$PWD/status/1500_launchd.err</string>
</dict></plist>
PLIST
launchctl unload "$PL" 2>/dev/null
launchctl load -w "$PL" 2>&1 | head -3
launchctl list | grep -i wakuban && echo "発車線：載りました" || echo "発車線：載っていません"

echo "--- いま1本投げてみる（枠が無ければ空振りで0円）---"
python3 tools/1500_wakuban.py
echo "--- 成績表 ---"
python3 tools/1501_devin_seiseki.py --now
echo "=== おわり。この窓は閉じていいです ==="
