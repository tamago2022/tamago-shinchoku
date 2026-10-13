#!/bin/bash
# ベッドホットキー：音量を5%上げる
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$HERE/_volume_step.sh" 5
