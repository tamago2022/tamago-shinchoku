#!/bin/bash
# ベッドホットキー：再生/一時停止（スペースキー相当）
# 今いちばん手前にあるアプリへそのままキーを送る。アプリを前面に出す操作（activate）は一切しない。
set -euo pipefail
osascript -e 'tell application "System Events" to keystroke " "'
echo "再生/一時停止キーを送りました"
