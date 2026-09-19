#!/bin/bash
cd "$(dirname "$0")"
mkdir -p ~/Library/LaunchAgents
cp com.tamago.wae-autopost.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.tamago.wae-autopost.plist 2>/dev/null
launchctl load ~/Library/LaunchAgents/com.tamago.wae-autopost.plist
rm -f .stop
echo "○ 毎日9:00と19:00に自動で出るようにしました。"
echo "  止めたいときは『4_とめる.command』を押してください。"
read -r _
