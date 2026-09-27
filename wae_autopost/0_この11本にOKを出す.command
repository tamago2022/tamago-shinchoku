#!/bin/bash
cd "$(dirname "$0")"
echo "■ 11本の文面と画像を全部お見せします。"
echo "  見てから、出していいかを1回だけ聞きます。"
echo "  ★OKが出ていない文面は、鍵があっても、時間が来ても、絶対に出ません。"
echo ""
python3 post.py --ok
echo ""
echo "（Enterで閉じます）"; read -r _
