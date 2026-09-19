#!/bin/bash
# ベッドホットキー：工場の自動発車を再開する
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$HERE/hotkey_cli.py" resume
