#!/bin/bash
# これを1回だけ実行すれば、次からは自動で録画できます。
cd "$(dirname "$0")"
clear
cat <<'EOS'
────────────────────────────────────────
 画面収録の許可を1回だけ入れます
────────────────────────────────────────
いま「システム設定 → プライバシーとセキュリティ → 画面収録」を開きます。

 1. リストの下の「＋」を押す
 2. ファイル選択の窓が出たら、キーボードで  command + shift + G
 3. 出た欄に次を貼って Return:

        /usr/sbin/screencapture

 4. 「開く」→ スイッチが入っていることを確認

終わったら、この黒い画面に戻って Return キーを押してください。
（3秒だけ試し録りして、録れるか確かめます）
────────────────────────────────────────
EOS
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
read -r _

T="$HOME/Documents/AI作業/zoom_rec/kakunin.mov"
mkdir -p "$(dirname "$T")"; rm -f "$T"
/usr/sbin/screencapture -x -v -g -V 3 "$T"
if [ -s "$T" ]; then
  echo
  echo "✅ 録れました（$(stat -f%z "$T") バイト）。20:00の自動録画はこのまま走ります。"
  rm -f "$T"
else
  echo
  echo "❌ まだ録れません。上の1〜4をもう一度。"
fi
echo
echo "このウインドウは閉じてかまいません。"
