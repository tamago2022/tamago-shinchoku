#!/bin/bash
# ベッドホットキー：次の動画（YouTube公式ショートカット Shift+N）
# アプリを前面に出す操作（activate）は一切しない。今手前にあるアプリへそのまま送る。
set -euo pipefail
osascript -e 'tell application "System Events" to keystroke "n" using shift down'
echo "次の動画キー（Shift+N）を送りました"
