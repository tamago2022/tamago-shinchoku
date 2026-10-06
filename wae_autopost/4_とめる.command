#!/bin/bash
cd "$(dirname "$0")"
touch .stop
launchctl unload ~/Library/LaunchAgents/com.tamago.wae-autopost.plist 2>/dev/null
echo "○ 止めました。"
read -r _
