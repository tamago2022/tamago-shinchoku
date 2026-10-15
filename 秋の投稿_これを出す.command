#!/bin/bash
# 秋の投稿・今日の1本を出す。たまごさんが押すのはこれ1つ。
# ★このファイルは投稿しません。Xの投稿画面を文面入りで開くだけです。
#   最後に「ポスト」を押すのはたまごさんです（勝手に出ない形）。
cd "$(dirname "$0")"

echo ""
python3 tools/aki_toko.py --show
RC=$?
if [ "$RC" != "0" ]; then
  echo ""
  echo "まだ今日の1本が出ていません。朝07:00と夜20:30に出ます。"
  echo ""; read -r _; exit 0
fi

echo ""
echo "これでよければ y を押して Enter（Xの投稿画面が文面入りで開きます）。"
echo "これじゃないなら n → 次の1本に差し替えます。"
printf "> "
read -r A

if [ "$A" = "n" ]; then
  python3 tools/aki_toko.py --kore-ja-nai
  echo ""
  echo "差し替えました。もう一度このファイルを押してください。"
  echo ""; read -r _; exit 0
fi

if [ "$A" != "y" ]; then
  echo "やめました。"; echo ""; read -r _; exit 0
fi

# 文面をコピーしておく（貼り付けが要るときのため）
python3 - <<'PY' | pbcopy
import json, io, os
st = json.load(io.open(os.path.join("status", "aki_toko.json"), encoding="utf-8"))
print(st["ima"]["full"], end="")
PY

# Xの投稿画面を、文面入りで開く
URL=$(python3 - <<'PY'
import json, io, os, urllib.parse
st = json.load(io.open(os.path.join("status", "aki_toko.json"), encoding="utf-8"))
print("https://x.com/intent/post?text=" + urllib.parse.quote(st["ima"]["full"], safe=""))
PY
)
open "$URL"

python3 tools/aki_toko.py --ok >/dev/null 2>&1

echo ""
echo "Xの画面を開きました。あとは「ポスト」を1回押すだけです。"
echo "（文面はコピー済みなので、うまく入っていなければ command+V で貼れます）"
echo ""
read -r _
