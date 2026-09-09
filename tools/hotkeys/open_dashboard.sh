#!/bin/bash
# ベッドホットキー：進捗表（発車待ち・確認待ちの一覧）を開く
# たまごさん本人がこのキーを押した時だけ実行される想定なので、ここでの open は問題ない
# （AIが勝手にウィンドウを前に出す操作とは別物＝本人の意思によるホットキー起動）。
set -euo pipefail
open "https://tamago2022.github.io/tamago-shinchoku/"
echo "進捗表を開きました"
