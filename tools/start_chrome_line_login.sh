#!/usr/bin/env bash
# 769番：LINE Creators Market専用のChromeプロファインを開くための、たまごさん自身が実行するスクリプト。
# これはAIが自動で実行するものではない。たまごさんが自分の意思でターミナルから1回だけ実行し、
# 開いたウィンドウでLINEにログインしてもらうためのもの（ログインは本人にしかできない）。
#
# 使い方：
#   1. ターミナルで  bash /Users/mac/Desktop/tamago-shinchoku/tools/start_chrome_line_login.sh  を実行
#   2. 開いたChromeウィンドウで https://creator.line.me/ja/ を開き、いつものLINEアカウントでログイン
#   3. ログインできたことを確認したら、そのウィンドウは閉じてよい（ログイン情報は保存される）
#
# これ以降、この専用プロファイル(~/.tamago/chrome-line)にログイン情報が残るので、
# 次回からは自動化スクリプト側がheadless(画面なし)で同じプロファインを使って作業できる。
set -euo pipefail
PROFILE_DIR="${HOME}/.tamago/chrome-line"
mkdir -p "${PROFILE_DIR}"
open -na "Google Chrome" --args \
  --remote-debugging-port=9224 \
  --user-data-dir="${PROFILE_DIR}"
echo "起動しました。開いたウィンドウで https://creator.line.me/ja/ にアクセスし、ログインしてください。"
