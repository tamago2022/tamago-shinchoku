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

# ---- 2026-09-12（776番）：心臓が詰まったまま二度と戻らない事故への根本対策 ----
# それまでは machine_status_push.sh が「180秒何も書いていなければ心臓を入れ直す」
# 外側の見張りしか持っておらず、中身（auto_launcher.py / command_ingest.py）が
# 何らかの理由で固まる原因そのものは直っていなかった。実測：2026-09-12 12:58〜16:49の
# 230分間、立て直しては数分〜十数分でまた詰まる、を繰り返した（heartbeat.log参照）。
# 「見張りの見張り」を増やすのではなく、一番下（この15秒ループ自体）に
# 「どんな理由で固まっても必ず自分で抜け出す」保険を1つ置く。
# 戻り値：タイムアウトで強制終了した時だけ 124（GNU timeoutと同じ慣例）を返す。
# それ以外（コマンド自身が正常/異常終了した場合）はそのままの終了コードを返す＝
# 呼び出し側が今までどおり || true で握りつぶせる。
run_with_timeout() {
  local secs="$1"; shift
  "$@" &
  local cpid=$!
  local killed_flag="$REPO/status/.heartbeat_killed_$$_$cpid"
  ( sleep "$secs" 2>/dev/null; if kill -0 "$cpid" 2>/dev/null; then : > "$killed_flag"; kill -9 "$cpid" 2>/dev/null; fi ) &
  local watcher=$!
  wait "$cpid" 2>/dev/null
  local rc=$?
  kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
  if [ -f "$killed_flag" ]; then rm -f "$killed_flag" 2>/dev/null; return 124; fi
  return $rc
}

echo "$(date '+%F %T') 心臓を起動しました（pid $$）" >> "$LOG"
while :; do
  # 自分が正規の心臓でなくなっていたら（誰かが入れ直した）静かに退く
  CUR="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${CUR:-}" ] && [ "$CUR" != "$$" ]; then
    echo "$(date '+%F %T') 新しい心臓（pid $CUR）に交代します" >> "$LOG"
    exit 0
  fi
  run_with_timeout 45 python3 "$REPO/tools/auto_launcher.py"  >/dev/null 2>&1
  [ $? -eq 124 ] && echo "$(date '+%F %T') ⏱ auto_launcher.pyが45秒以内に終わらず強制終了しました" >> "$LOG"
  run_with_timeout 45 python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1
  [ $? -eq 124 ] && echo "$(date '+%F %T') ⏱ command_ingest.pyが45秒以内に終わらず強制終了しました" >> "$LOG"
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
  # 2026-09-07（620番）：確認ページ(share/check)が上限も掃除も無いまま増え続けていた。
  #   60日以上さわられていないものだけ、店主が拾えるようゴミ箱へ退避する（6時間に1回でよい）。
  ( python3 "$REPO/tools/check_page_pruner.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-07（626番）：support@anthropic.comへの問い合わせ返信を1日1回チェックする見張り。
  #   新しいlaunchd便は増やさず、既存の心臓に相乗り。実際にIMAPへ繋ぐのはスクリプト内部で
  #   1日1回に間引いている（それ以外の15秒ごとの呼び出しは即座に戻るだけで負荷ゼロに近い）。
  ( python3 "$REPO/tools/check_anthropic_reply.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-11（756番）：毎朝の入荷見回り（707番）を手作業から自動へ。前日にjoy-relief-stationへ
  #   新規登録された動画を見回るタスクを、1日1回だけ発車待ちへ積む（check_anthropic_reply.pyと
  #   同じ間引きパターン。新しいlaunchd便は増やさない）。
  ( python3 "$REPO/tools/daily_ingest_scheduler.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # ログが太らないように、たまに刈る
  if [ "$(( $(date +%s) % 3600 ))" -lt 20 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
    echo "$(date '+%F %T') 心臓は動いています" >> "$LOG"
  fi
  sleep 15
done
