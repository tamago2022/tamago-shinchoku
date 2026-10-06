#!/bin/bash
# 今日の1本が気に入らないとき。押すと次の1本に差し替わります。文面は書かなくていいです。
cd "$(dirname "$0")"
python3 tools/aki_toko.py --kore-ja-nai
echo ""
python3 tools/aki_toko.py --show
echo ""
echo "これでよければ 秋の投稿_これを出す.command を押してください。"
echo ""
read -r _
