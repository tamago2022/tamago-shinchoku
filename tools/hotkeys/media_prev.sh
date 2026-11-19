#!/bin/bash
# ベッドホットキー：前の動画（YouTube公式ショートカット Shift+P）
# アプリを前面に出す操作（activate）は一切しない。今手前にあるアプリへそのまま送る。
set -euo pipefail
osascript -e 'tell application "System Events" to keystroke "p" using shift down'
echo "前の動画キー（Shift+P）を送りました"
