#!/bin/bash
# PWAリモコンのコマンドキューを実行し、結果があればpushする（30秒おきにlaunchdから呼ばれる）。
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="/Users/mac/Desktop/tamago-shinchoku"
cd "$REPO" || exit 0

python3 "$REPO/tools/command_ingest.py" >/tmp/command_ingest.log 2>&1

if git status --porcelain -- status/commands.json 2>/dev/null | grep -q .; then
  git add status/commands.json >/dev/null 2>&1
  git -c user.name="command-ingest" -c user.email="command-ingest@local" commit -q -m "cmd: 実行結果 $(date +%H:%M)" >/dev/null 2>&1 || exit 0
  git -c credential.helper='!gh auth git-credential' pull --rebase -q origin main >/dev/null 2>&1
  git -c credential.helper='!gh auth git-credential' push -q origin main >/dev/null 2>&1
fi
