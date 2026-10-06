#!/bin/bash
# ベッドホットキー：音量を20%下げる
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$HERE/_volume_step.sh" "-20"
