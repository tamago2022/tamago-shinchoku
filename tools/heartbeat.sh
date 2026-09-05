#!/bin/bash
# 工場の心臓。15秒おきに「軽い2つ」だけを回し続ける常駐プロセス。
#
# 2026-09-04 たまごさん「回り続ける仕組みにしたい」「1個空いたら1個繰り上がる、ところてんみたいに」
#
# なぜ常駐にしたか（実測に基づく）：
#   これまで着火と受信箱は、5分おきのlaunchd便（machine_status_push.sh）の中でしか動いていなかった。
#   ところがその便は1回に4〜5分かかる（重い計測 factory_status が27秒〜、走行が増えるとさらに伸びる）ので、
#   実際には**5〜14分に1回しか回っていなかった**。
#   実害：22:25に発車したあと22:32まで7分間、着火も受信箱も一度も動かず、
#         たまごさんがスマホで押したボタンが7分間Macに届かなかった。
#   → 重い計測は5分便のまま。軽い2つ（着火・受信箱）だけをここで15秒おきに回す。
#     どちらも1秒かからないので、Macの負荷はほぼ増えない。
#
# 二重起動しない。落ちても machine_status_push.sh が次の巡回で立て直す（自己修復）。
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$REPO/status/heartbeat.log"

# ---- 心臓は必ず1本だけ（2026-09-05・実害あり）----
# たまごさん「同じものが2つ同時に作業してるよね。これも変だよね」「発車待ちに同じ内容が2番3番」
# 実測：16:25〜16:26の2分間で「心臓を起動しました」が12回。**心臓が何本も走っていた。**
#   心臓が2本なら受信箱も2回読まれ、同じ指示が2回実行される（＝台帳に同じ仕事が2つ増える）。
#   4本走っていたので4つに増えていた。走行中に同じ仕事が2つ並ぶのも同じ理由。
# コメントに「二重起動しない」と書いてあったが、**実装が無かった。**書いただけでは効かない。
PIDF="$REPO/status/heartbeat.pid"
if [ -f "$PIDF" ]; then
  OLD="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${OLD:-}" ] && [ "$OLD" != "$$" ] && kill -0 "$OLD" 2>/dev/null; then
    echo "$(date '+%F %T') 既に心臓が動いています（pid $OLD）。この起動はやめます" >> "$LOG"
    exit 0
  fi
fi
echo $$ > "$PIDF"
# 退くときは「自分のPIDが書いてあるときだけ」消す。
# 2026-09-05 17:25 これを付けずに無条件で消していたため、交代した古い心臓が
#   **新しい心臓のPIDファイルまで道連れに消して**、誰も居ないのに居るように見えたり、
#   逆に立て直しの判断が狂ったりした（17:17を最後に心臓が止まった）。
cleanup_pid() {
  if [ "$(cat "$PIDF" 2>/dev/null || true)" = "$$" ]; then rm -f "$PIDF" 2>/dev/null || true; fi
}
trap cleanup_pid EXIT INT TERM

echo "$(date '+%F %T') 心臓を起動しました（pid $$）" >> "$LOG"
while :; do
  # 自分が正規の心臓でなくなっていたら（誰かが入れ直した）静かに退く
  CUR="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${CUR:-}" ] && [ "$CUR" != "$$" ]; then
    echo "$(date '+%F %T') 新しい心臓（pid $CUR）に交代します" >> "$LOG"
    exit 0
  fi
  python3 "$REPO/tools/auto_launcher.py"  >/dev/null 2>&1 || true
  python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1 || true
  # ログインが戻ったら自分で気づいて再開する（10分に1回だけ試す）
  python3 "$REPO/tools/auth_watch.py"     >/dev/null 2>&1 || true
  # 2026-09-05：中継所（進捗表→Mac）が死ぬと、たまごさんがボタンを押しても何も届かない。
  #   5分便まかせだと最大5分間ボタンが効かないままなので、心臓でも2分に1回見る。
  #   **投げっぱなしにして心臓は待たない**（対話待ちで工場を止めた07:03の事故の教訓）。
  #   生死は「プロセスが居るか」ではなく「外から叩いて200が返るか」で見る。道は2本（relay_watch.py）。
  ( python3 "$REPO/tools/relay_watch.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-05 使い終わった作業場(git worktree)を片づける。放っておくと51個溜まり、
  #   ChatGPT(Codex)がそれを1つずつ「プロジェクト」として拾ってたまごさんの画面を汚す。
  #   本流に入っていて・未保存の変更が無くて・2時間以上経ったものだけ消す（30分に1回）。
  ( python3 "$REPO/tools/worktree_reaper.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # ログが太らないように、たまに刈る
  if [ "$(( $(date +%s) % 3600 ))" -lt 20 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
    echo "$(date '+%F %T') 心臓は動いています" >> "$LOG"
  fi
  sleep 15
done
