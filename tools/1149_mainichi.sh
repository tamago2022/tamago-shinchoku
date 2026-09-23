#!/bin/bash
# 1149番【毎日1回これだけ叩けばいい】4帳簿を数え直し、直せるものを直し、表を作り直す。
# 全部が「落ちても続きから」の外袋の中で走る。認証で落ちたら止まる。
#
#   tools/1149_mainichi.sh
#
# 戻し方（1行）: この便を止めるだけ（何も本番に触っていない）
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"
"$R/tools/1149_fukkyuu.sh" dojisu  -- python3 "$R/tools/1149_dojisu.py"
"$R/tools/1149_fukkyuu.sh" daicho  -- python3 "$R/tools/1149_daicho.py" --naosu
"$R/tools/1149_fukkyuu.sh" page    -- python3 "$R/tools/1149_page.py"
