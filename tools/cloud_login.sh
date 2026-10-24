#!/bin/bash
# クラウド起動用の「本物のログイン」を、工場のログイン（setup-token）とは別の置き場で1回だけ作る（2026-10-22）。
# なぜ：工場の Mac の CLI は setup-token（user:inference だけ）なので `claude --cloud` が 403
#   （デバッグ実測：「[Bootstrap] Skipped: 403 for OAuth token without profile scope」「fetchEnvironments failed: 403」）。
#   クラウドの作成には user:sessions:claude_code・user:profile の権限が要る＝claude.ai のアカウントで1回ログインが要る。
# 置き場：CLAUDE_CONFIG_DIR=~/.tamago/claude_cloud（工場の ~/.claude のログインには触らない）。
# 使い方：
#   bash tools/cloud_login.sh start   → URL を status/cloud_credit/login_url.txt に出して待つ（60時間）
#   （人：URL を開いて「許可」→ 画面に出たコードを Dispatch に貼る）
#   bash tools/cloud_login.sh code <コード>   → 待っているログインにコードを渡す
#   bash tools/cloud_login.sh status
export PATH=$HOME/.local/bin:/opt/homebrew/bin:$PATH
export CLAUDE_CONFIG_DIR=$HOME/.tamago/claude_cloud
D=$HOME/.tamago/claude_cloud; mkdir -p $D
S=/Users/mac/tamago/tamago-shinchoku/status/cloud_credit
LOG=$D/login.log
# ブラウザ（Brave）を勝手に開かせない：この道具の中だけ open／xdg-open を空にする（URL は Dispatch 経由で人に渡す）
mkdir -p $D/bin; printf '#!/bin/sh\nexit 0\n' > $D/bin/open; cp $D/bin/open $D/bin/xdg-open; chmod +x $D/bin/open $D/bin/xdg-open
export PATH=$D/bin:$PATH BROWSER=/usr/bin/true
case "$1" in
start)
  pkill -f "cloud_login.exp" 2>/dev/null; rm -f $S/code.txt $D/code.txt $S/login_url.txt $S/login_result.txt
  nohup /usr/bin/expect /Users/mac/tamago/tamago-shinchoku/tools/cloud_login.exp >/dev/null 2>&1 &
  pkill -f cloud_login_watch.sh 2>/dev/null; nohup bash /Users/mac/tamago/tamago-shinchoku/tools/cloud_login_watch.sh >/dev/null 2>&1 &
  disown; sleep 20
  cat $S/login_url.txt 2>/dev/null || echo "URLが出ない（$LOG を見る）" ;;
code)
  printf '%s' "$2" > $D/code.txt; sleep 25
  cat $S/login_result.txt 2>/dev/null; claude auth status 2>&1 | head -8
  # ログインできたら、junban.txt の上から3本（白飛び・ずれ・初回表示）をその場で起動（cloud_mainichi が done.txt へ移すので心臓と二重にならない）
  if grep -q OK $S/login_result.txt 2>/dev/null; then
    nohup bash -c 'for i in 1 2 3; do CLOUD_IGNORE_HOURS=1 python3 /Users/mac/tamago/tamago-shinchoku/tools/cloud_mainichi.py; done' >> /Users/mac/tamago/tamago-shinchoku/status/cloud_credit/mainichi.log 2>&1 &
    disown; echo "3本の起動を切り離して開始"
  fi ;;
status)
  claude auth status 2>&1 | head -8 ;;
esac
