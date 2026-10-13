#!/bin/bash
# ベッドホットキー：今Braveで見ている動画のURLを仕入れ箱（工場の発車待ちキュー）へ入れる。
# Braveを前面に出す操作（activate）は一切しない。今開いているタブのURLを読むだけ。
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

URL="$(osascript -e 'tell application "Brave Browser" to get URL of active tab of front window' 2>&1)" || {
  echo "Braveのタブが取得できませんでした: $URL" >&2
  exit 1
}

if [[ -z "$URL" || "$URL" != http* ]]; then
  echo "有効なURLが取得できませんでした: $URL" >&2
  exit 1
fi

python3 "$HERE/hotkey_cli.py" ingest "$URL"
