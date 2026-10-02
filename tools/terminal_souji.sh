#!/bin/bash
# Terminalの散らかし点検（読むだけ。勝手に閉じない）。何も動いていない空のシェル窓を一覧にする。
# 閉じるのは「Claude由来と確認できたもの」だけ：該当ttyの子プロセスをkill→全窓が空ならTerminalを終了。
for t in $(ps -axo tty= | grep '^ttys' | sort -u); do
  n=$(ps -t "$t" -o command= 2>/dev/null | grep -vE '^(login|-?zsh|-?bash)' | wc -l | tr -d ' ')
  echo "$t 実行中の仕事=$n"
done
