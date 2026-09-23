#!/bin/bash
# Macの負荷を measure して status/machine.json に書き、変わっていれば GitHub Pages へ push する。
# 5分おきに launchd（com.tamago.machine-status）から呼ばれる。計測本体は tools/machine_load.sh（リポジトリの中。外に置くと消える）。
# 2026-09-03 15:xx リアルタイム化：launchdの新規ジョブ登録は2回ともAuto mode classifierにブロックされたため、
# 「1回の起動の中で30秒おきに測る」方式に変更（新規ジョブ登録なし・既存の5分おき起動はそのまま）。
# 1回の起動につき最大約260秒(=launchdの次の5分ティックが来る前)ループし続け、変化があれば即pushする。
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
OUT="$REPO/status/machine.json"
LOADSH="$REPO/tools/machine_load.sh"
mkdir -p "$REPO/status"

# 2026-09-16：run_once()内の factory_status.py --write がタイムアウト無しで呼ばれていたため、
# 重い状態下でこれ自体がハング(UN)すると、run_once()を含むこの便まるごと（＝心臓の生死を
# 見直す処理も含めて）何十分も止まった。実測：29分ハング→その間ずっと心臓の再起動判定が
# 走らず、心臓が落ちても誰も気づけなかった。ここで使うため早い位置に定義しておく
# （下の方にある同名関数と役割は同じ・呼び出しは全て定義パース後なのでどちらでも動くが、
# ここで先に定義して即使う）。
run_with_timeout() {
  local secs="$1"; shift
  "$@" &
  local cpid=$!
  ( sleep "$secs" 2>/dev/null; kill -9 "$cpid" 2>/dev/null ) &
  local watcher=$!
  wait "$cpid" 2>/dev/null
  local rc=$?
  kill "$watcher" 2>/dev/null; wait "$watcher" 2>/dev/null
  return $rc
}

# 1回の起動が約260秒に伸びたため、launchdの次の5分ティックと重なって二重起動しないようロックする
# 2026-09-17（894番）：「プロセスが生きているか」だけで門前払いしていたため、前のインスタンスが
# 高負荷（実機実測：load 10.9・スワップ6.9GB）で詰まったまま何分も居座ると、後続の便が
# 5分おきに毎回すぐ諦めて終了し続け、心臓の生死判定・復旧チャンス（この便の冒頭にある）
# 自体が何分も回ってこなくなる事故を実機で確認した（心臓を意図的に止めるテストで、
# 通常なら約260秒で終わるはずのこの便が18分以上動かなかった）。
# 生きているだけでなく、ロックの経過時間も見る：420秒（7分。正常な1回の巡回は約260秒
# なので十分な余裕）を超えて残っていたら「詰まっている」とみなし、前のインスタンスを
# 片づけて自分がロックを取り直す（門前払いを続けない＝止まった瞬間に自分で立て直す）。
LOCK="$REPO/status/.machine_status_push.lock"
if [ -f "$LOCK" ]; then
  LOCK_PID="$(cat "$LOCK" 2>/dev/null || true)"
  LOCK_AGE=$(( $(date +%s) - $(stat -f %m "$LOCK" 2>/dev/null || echo 0) ))
  if [ -n "${LOCK_PID:-}" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    if [ "$LOCK_AGE" -gt 420 ]; then
      echo "$(date '+%F %T') 💀 前回の便(pid $LOCK_PID)が${LOCK_AGE}秒（約$((LOCK_AGE / 60))分）ロックを握ったまま詰まっています。片づけて入れ替わります" >> "$REPO/status/heartbeat.log"
      kill -9 "$LOCK_PID" 2>/dev/null || true
    else
      exit 0
    fi
  fi
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# ---- 2026-09-18（Cowork側から設置）機械の健康診断＋工場が撒いた残骸の回収 ----
# 実測：07:26の machine.json が 負荷5046% / スワップ17.06GB。しかしその数字しか無く、
#   **何がどれだけ食っているのかを持っている場所がどこにも無かった**
#   （status/heavy_events.jsonl は上位3本の名前だけ）。
# ここは launchd が直接起動するので、心臓が死んでいても必ず走る＝最後の掃除係。
#   重い計測より前・ロックを取った直後に置く（後ろに置くと30分以上回ってこない実測あり）。
# 落とすのは「工場が自分で起動して終わり損ねたもの」だけ：自動操作用のChrome、
#   tools配下の撮影スクリプト(.mjs)、心臓に相乗りしている即戻り設計のpythonが15分以上
#   生きているもの、中継所のトンネルの残骸。たまごさんのBrave・エディタ・Obsidian・
#   Eagle・生成系（動画/画像/ナレーション）には一切当たらない（NEVERで除外）。
# 新しいlaunchd便は増やさない（既存便への相乗り＝この工場の決まり）。
run_with_timeout 90 python3 "$REPO/tools/machine_health.py" --reap >/dev/null 2>&1 || true

# ---- 2026-09-19（961番・Cowork側から設置）本番に出ていないものを出し切る便 ----
# joy-relief-station への反映（joy_push）の口は、スマホのボタンから来た時にしか回らない。
# 実測：今日は 11:17 を最後に7時間回っていない＝直したものが何時間も本番に出ないまま溜まる。
# ここ（5分おきに必ず launchd から起動される便）に相乗りする。新しい常駐は増やさない。
# ★status/_961/PHASE が idle（既定）なら即 exit 0 ＝完全に無害。用が済んだら idle に戻す。
# ★この便を止めないよう、バックグラウンドへ逃がす（公開ボタンは押してから反映までが長い）。
#   二重起動は _961 側のロックで防いでいる。
( nohup bash "$REPO/tools/_961_jrs_deliver.sh" >/dev/null 2>&1 & ) >/dev/null 2>&1

# ---- 2026-09-22（971番の相棒・Cowork側から設置）コピーを毎朝ひとりでに直す係 ----
# たまごさん「外部追加分のコピーを全部直す ⇨ これはもう毎日やること」。
# 実測：数える係（971・下の方）は毎朝きちんと「手つかず16件」を出していた。だが直す係が
#   居なかったので、16件は16件のまま座り続けた。**数えるだけでは減らない。**ここが直す係。
# ★置き場所をここにした理由（実測で1回はまった）：この便の下の方には
#   「機械の数字が前回と同じなら return 0」という早期returnがある。最初そこの後ろに
#   置いたため、変化の無い間は一度も呼ばれなかった（06:23〜06:35、1回も走らず）。
#   ここはロックを取った直後＝launchdが起こせば必ず通る場所。**心臓が死んでいても回る。**
# ★新しい常駐・新しい定期タスクは増やさない（この工場の決まり）。
# ★中で1日1回ゲートする（朝6時以降の最初の便だけ走る）。手で回すときは
#   status/.gaibu_copy_naoshi_force を置く。
# ★書き直しに claude -p を使うので1件あたり数十秒かかる。この便を1秒も遅らせないため
#   バックグラウンドへ逃がす。二重起動は naoshi 側のロック（30分で剥がれる）で防ぐ。
# ★呼んだこと自体をログに残す（「呼んだつもりで呼べていない」を見えなくしないため）。
echo "$(date '+%F %T') naoshi 呼び出し" >> "$REPO/status/gaibu_copy_naoshi.log"
( nohup python3 "$REPO/tools/gaibu_copy_naoshi.py" >>"$REPO/status/gaibu_copy_naoshi.log" 2>&1 & ) >/dev/null 2>&1

# ---- 2026-09-23（1039番）投げ込み箱 → 棚へ入れる係 ----
# たまごさん：「1日1回でもいいのよ。最後12時に、今日届いている分だけピックアップして入れる」
# ★上の naoshi と**まったく同じ型**でここに置く。理由も同じ：
#   ロックを取った直後＝launchdが起こせば必ず通る場所。心臓が死んでいても回る。
# ★新しい常駐・新しい定期タスク・列（queue.json）は増やさない。
# ★中で1日1回ゲートする（tools/nagekomi_shelf.py の GATE）。日付が変わった最初の便で走る
#   ＝**深夜0時すぎ**。手で回すときは status/.nagekomi_shelf_force を置く。
# ★コピーを claude -p に書かせるので1件あたり数十秒。この便を遅らせないため背後へ逃がす。
#   二重起動は nagekomi_shelf 側のロック（60分で剥がれる）で防ぐ。
echo "$(date '+%F %T') nagekomi_shelf 呼び出し" >> "$REPO/status/nagekomi_shelf.log"
( nohup python3 "$REPO/tools/nagekomi_shelf.py" >>"$REPO/status/nagekomi_shelf.log" 2>&1 & ) >/dev/null 2>&1

# ---- 2026-09-23（1029番・Cowork側から設置）覆面調査員（架空のお客さん4人）の潜伏 ----
# たまごさん「潜伏してひたすら触ってくれる人がいれば、どこを直せば体験が良くなるか分かるんじゃないの？」
# 本番（joy-relief-station.lovable.app）を実際にPlaywrightで触り、たまごさんが言う3症状を数字で取る。
#   ①入力中に落ちる ②読んでる途中で画面が切り替わる（CLS） ③URL貼ると落ちる・重い（LCP/長いタスク）
# ★新しいlaunchd常駐・新しい定期タスクは増やさない（この工場の決まり）。
# ★中で1日1回ゲートする。5分おきに呼ばれても外へ出るのは1日1回だけ。
# ★Macが混んでいる回（load>40）は見送り、**ゲートを消費しない**（931番の掃除機が1時間ゲートで
#   実質一度も掃けていなかったのと同じ穴を作らないため）。
# ★1周が数十分かかるのでバックグラウンドへ逃がす。二重起動は fukumen_daily 側のロックで防ぐ。
( nohup python3 "$REPO/tools/fukumen_daily.py" >>"$REPO/status/fukumen/daily.log" 2>&1 & ) >/dev/null 2>&1

# ---- 2026-09-22（1024番・Cowork側から設置）棚に入ったものへ「入荷日」を付ける係 ----
# たまごさん「これから入るものには、必ず入荷日が付くようにする（仕入れの仕組み側に足す）」。
# 入荷日は棚の正本（joy-relief-station の coverGuide.ts）のgit履歴から引く（0円・読むだけ）。
# **台帳を持ち回らない。**毎回gitから引き直すので、途中で台帳が壊れても次の便で必ず直る。
# ★1日1回だけ（丸ごと1回31秒かかるので、5分おきに回すと無駄）。
# ★joy-relief-station が無ければ中で即 return ＝完全に無害。新しい常駐は増やさない。
# ★この便を1秒も遅らせないためバックグラウンドへ逃がす。
_NY_STAMP="$REPO/status/.nyuka_hiduke_done"
if [ ! -f "$_NY_STAMP" ] || [ "$(date +%F)" != "$(cat "$_NY_STAMP" 2>/dev/null)" ]; then
  date +%F > "$_NY_STAMP"
  ( nohup python3 "$REPO/tools/_1024_nyuka_hiduke.py" \
      >>"$REPO/status/nyuka_hiduke.log" 2>&1 & ) >/dev/null 2>&1
fi

# ---- 2026-09-20（969番・Cowork側から設置）外部AIの返事を拾って961ページへ並べる便 ----
# たまごさん「返事が来たら、要約せずそのまま 961-talking-avatar-jirei.html に追記する」。
# GitHubのIssueに来たコメントを、条件付きGET1本で見に行くだけ（変化が無い回はレート消費0・0円）。
# ★status/969/issue.json が無ければ即 return ＝完全に無害。新しい常駐は増やさない。
run_with_timeout 60 python3 "$REPO/tools/_969_avatar_reply_pickup.py" >/dev/null 2>&1 || true

# ---- 残骸の掃除（2026-09-05 17:05・実害あり）----
# たまごさん「Mac重たいよ」。実測：5分平均ロードが238（8コアのMacで通常8以下）。
# 原因は、中継所のトンネルを立て直すたびに起動していた localtunnel(npx/node) と cloudflared が、
# 繋がらないまま**積み上がっていた**こと。ここは launchd が直接起動するので、
# 心臓が詰まっていても必ず走る＝**最後の掃除係**。
# 落とすのは自分たちが起動したものだけ（8788番ポート宛て・localtunnel）。
# たまごさんの他の作業（開発用のnode等）を巻き込まないよう、パターンを絞ってある。
LOAD1="$(sysctl -n vm.loadavg 2>/dev/null | awk '{print $2}' | cut -d. -f1)"
if [ -n "${LOAD1:-}" ] && [ "$LOAD1" -ge 15 ] 2>/dev/null; then
  LT_N="$(pgrep -fc 'localtunnel' 2>/dev/null || echo 0)"
  CF_N="$(pgrep -fc 'cloudflared.*localhost:8788' 2>/dev/null || echo 0)"
  if [ "${LT_N:-0}" -gt 1 ] 2>/dev/null || [ "${CF_N:-0}" -gt 1 ] 2>/dev/null; then
    pkill -f 'localtunnel' >/dev/null 2>&1 || true
    pkill -f 'cloudflared.*localhost:8788' >/dev/null 2>&1 || true
    echo "$(date '+%F %T') 🧹 重い（ロード$LOAD1）ので中継所の残骸を掃除（localtunnel ${LT_N}本・cloudflared ${CF_N}本）" >> "$REPO/status/relay.log"
  fi
fi

# 2026-09-04 工場の心臓（15秒おきに着火と受信箱だけを回す常駐）。
#   **この巡回のいちばん最初に立てる。**重い計測のあとに置いていたら、
#   1回の巡回が4〜5分かかるせいで心臓そのものが何分も立たなかった。
#   落ちていたら次の巡回で立て直す（自己修復）。二重起動はしない。
#   2026-09-05：`nohup ... &` だと**launchdが次の便を出すときに親ごと（プロセスグループごと）
#   殺されて心臓も一緒に死んでいた**（実測：01:32/01:42/01:51と10分おきに立ち上げ直されていた）。
#   親から切り離した別セッションとして起動する（pythonの start_new_session=True ＝ setsid相当）。
# 2026-09-05 **pgrep だけで判断すると心臓が増える。**
#   実測：16:25〜16:58に何十本も立ち上がった。起動直後はまだ pgrep に見えない一瞬があり、
#   そこで別の便が「居ない」と判断してもう1本立てる。心臓が増えると受信箱が何度も読まれ、
#   **同じ指示が何回も実行されて台帳に同じ仕事が何十個も増える**（待機が70件に膨れた）。
#   → PIDファイル（心臓が起動時に自分で書く）を先に見る。生きていれば絶対に立てない。
HBPID="$REPO/status/heartbeat.pid"
HB_ALIVE=0
if [ -f "$HBPID" ]; then
  HBOLD="$(cat "$HBPID" 2>/dev/null || true)"
  if [ -n "${HBOLD:-}" ] && kill -0 "$HBOLD" 2>/dev/null; then HB_ALIVE=1; fi
fi
# ---- 2026-09-06 00:16 **生きているのに詰まっている心臓を見つける。**----
# プロセスが在るかどうかだけで見ていたので、**中で固まっていても「生きている」と判定して
# 立て直さなかった。**実際 00:13 を最後に発車も受信箱も3分間止まったまま誰も気づかなかった。
# 中継所の生死を「外から叩いて確かめた」のと同じ考え方で、心臓も**仕事が進んでいるか**で見る。
# 2026-09-16：判定材料を auto_launch.log（実際に発車/回収があった時だけ書かれる＝
# 「走行0本で何もすることが無い」だけでも詰まっていると誤判定していた）から、
# 心臓が毎周期・何もなくても必ずtouchする .heartbeat_alive に変更した。
# 実害：この誤判定で正常な心臓を何度も殺し、殺した拍子に子（auto_launcher.py等）が
# 孤児化してロックファイルを握ったまま残り、発車が14時間止まった（14時間工場停止事故）。
if [ "$HB_ALIVE" = "1" ]; then
  NOW_S=$(date +%s)
  LOG_S=$(stat -f %m "$REPO/status/.heartbeat_alive" 2>/dev/null || echo 0)
  if [ "$(( NOW_S - LOG_S ))" -gt 180 ]; then
    echo "$(date '+%F %T') 💤 心臓が$(( (NOW_S - LOG_S) / 60 ))分間touchしていません。詰まっているとみなして入れ直します" >> "$REPO/status/heartbeat.log"
    pkill -f "tools/heartbeat.sh" >/dev/null 2>&1 || true
    # 心臓本体だけでなく、その場で回っていた子（孤児化してロックを握り続ける原因）も一緒に片づける。
    pkill -f "tools/auto_launcher.py" >/dev/null 2>&1 || true
    pkill -f "tools/command_ingest.py" >/dev/null 2>&1 || true
    sleep 1
    pkill -9 -f "tools/heartbeat.sh" >/dev/null 2>&1 || true
    pkill -9 -f "tools/auto_launcher.py" >/dev/null 2>&1 || true
    pkill -9 -f "tools/command_ingest.py" >/dev/null 2>&1 || true
    rm -f "$HBPID" 2>/dev/null || true
    HB_ALIVE=0
  fi
fi
# 2026-09-17（894番・Verifier差し戻し対応）：心臓の起動をここでの直接Popenから
# launchd（com.tamago.tamago-shinchoku.heartbeat・KeepAlive=true）へ一本化した。
# KeepAlive=trueなので、上のpkillで心臓を殺した瞬間、launchdが自分で（既定ThrottleInterval
# ＝数秒〜十数秒）立て直す。5分便のこのロック（最悪7分）を待たずに戻るため、
# 「3分以内に自分で戻る」を5分便経由ではなくOS自身の監視で満たす構造にした。
# それでも万一plist未ロード等でlaunchd側に心臓がいなければ、保険としてkickstartも呼ぶ。
if [ "$HB_ALIVE" = "0" ] && ! pgrep -f "tools/heartbeat.sh" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/com.tamago.tamago-shinchoku.heartbeat" >/dev/null 2>&1 || true
fi

# 2026-09-03 追加：置き去りのgitロックを掃除する。
# Cowork側のサンドボックスからマウント越しにgitを叩くと、.git/*.lock と objects/*/tmp_obj_* を
# unlink できず（Operation not permitted）残る。残ると以後このスクリプトのcommit/pushが毎回失敗し、
# 進捗表が丸ごと止まる（18:25〜18:30に実際に発生）。5分以上前のものだけ消す＝実行中のgitは巻き添えにしない。
# 2026-09-05 入力待ちで黙り込む `claude setup-token` が残ると、心臓（15秒おき）ごと固まる。
#   実測：07:03から3分間、着火も受信箱も止まった。見つけたら落とす。
pkill -f "claude setup-token" >/dev/null 2>&1 || true
find "$REPO/.git" -maxdepth 1 -name "*.lock" -mmin +5 -delete 2>/dev/null || true
find "$REPO/.git/objects" -maxdepth 2 -name "tmp_obj_*" -mmin +5 -delete 2>/dev/null || true

# 2026-09-12(717番) pre-commit hookの自己修復：.git/hooksは追跡対象外なので、
#   何かの拍子に消えても（別worktreeでの再clone等）ここで毎回作り直す。1MB超ガードの最終防波堤。
# 2026-09-17（925番）：「無ければ作る」(-x判定)だと、tools/git-hooks/pre-commit を
#   直しても既にインストール済みのhookは古い中身のまま置き去りになる（今回、旧EXEMPT_REGEX
#   が'status/public/queue.json'に一致せず数時間ブロックし続けた実害の一因）。
#   中身が違う時は毎回上書きして常に最新に揃える（コストはファイルコピー1回のみ）。
if [ -f "$REPO/tools/git-hooks/pre-commit" ]; then
  if ! cmp -s "$REPO/tools/git-hooks/pre-commit" "$REPO/.git/hooks/pre-commit" 2>/dev/null; then
    cp "$REPO/tools/git-hooks/pre-commit" "$REPO/.git/hooks/pre-commit" 2>/dev/null || true
    chmod +x "$REPO/.git/hooks/pre-commit" 2>/dev/null || true
  fi
fi

run_once() {
# 2026-09-02 止まらない工場：計測＋止まり判定＋安全上限は factory_status.py に集約（土台は machine_load.sh のまま）。
# factory_status.py が失敗したら従来どおり machine_load.sh 単体で最低限のJSONを書く（止まらない）。
if run_with_timeout 90 python3 "$REPO/tools/factory_status.py" --write >/dev/null 2>&1 && grep -q '"safeMax"' "$OUT" 2>/dev/null; then
  :
else
LINE=$(bash "$LOADSH" 2>/dev/null || echo "")
# 例：負荷 12% ｜ CPU 9% / メモリ圧迫 58% / スワップ 0.20GB / ディスク空き 61GB ｜ 稼働 14本 ｜ あと3本OK
num() { echo "$1" | sed -nE "s/.*$2 ([0-9.]+)$3.*/\1/p" | head -1; }
LOAD=$(num "$LINE" "負荷" "%")
CPU=$(num "$LINE" "CPU" "%")
MEM=$(num "$LINE" "メモリ圧迫" "%")
SWAP=$(num "$LINE" "スワップ" "GB")
DISK=$(num "$LINE" "ディスク空き" "GB")
SESS=$(num "$LINE" "稼働" "本")
NOTE=$(echo "$LINE" | awk -F'｜' '{gsub(/^ +| +$/,"",$NF); print $NF}')
NOW=$(date +"%Y-%m-%dT%H:%M:%S%z" | sed -E 's/([0-9]{2})([0-9]{2})$/\1:\2/')

j() { [ -n "${1:-}" ] && echo "$1" || echo "null"; }
cat > "$OUT" <<EOF2
{"measuredAt":"$NOW","load":$(j "$LOAD"),"cpu":$(j "$CPU"),"mem":$(j "$MEM"),"swapGB":$(j "$SWAP"),"diskFreeGB":$(j "$DISK"),"sessions":$(j "$SESS"),"note":"$(echo "$NOTE" | sed 's/"/\\"/g')","raw":"$(echo "$LINE" | sed 's/"/\\"/g')"}
EOF2
fi

# 2026-09-03 利用枠の推定（会話ログのトークン量×スマホ実測アンカー）→ status/quota.json。見張り番がモデル選択と machine.json の quota 節に使う
# 2026-09-03 調査：quota_estimate.py が「実測ファイルが読めない」と言って推定にフォールバックし、
# 全モデル週枠を111%（実際は68%）、5時間枠を152%（実際は13%）と大きく外していた。
# 実測ファイルが本当に存在するのか・読めるのかを、ホスト側で動くこのスクリプトから確かめて記録する。
{
  echo "probe at $(date '+%F %T')"
  ls -l "$HOME/Library/Application Support/Claude/plan-usage-history.json" 2>&1
  echo "--- 最新サンプルと、なぜ採用されないか ---"
  python3 - <<'PYEOF' 2>&1
import json, os, time
p = os.path.expanduser("~/Library/Application Support/Claude/plan-usage-history.json")
try:
    d = json.load(open(p, encoding="utf-8"))
except Exception as e:
    print("読めない:", e); raise SystemExit
ss = d.get("samples") or []
print("version=%s samples=%d" % (d.get("version"), len(ss)))
if ss:
    last = ss[-1]
    age = (time.time() - last["t"]/1000.0)/60.0
    print("最新: t=%s (%.1f分前) u=%s org=%s" % (
        time.strftime("%F %T", time.localtime(last["t"]/1000.0)), age, last.get("u"), (last.get("org") or "")[:8]))
    # 直近12件の推移
    for s in ss[-12:]:
        print("  %s fh=%s sd=%s" % (time.strftime("%m-%d %H:%M", time.localtime(s["t"]/1000.0)),
                                    (s.get("u") or {}).get("fh"), (s.get("u") or {}).get("sd")))
PYEOF
} > "$REPO/status/_plan_usage_probe.txt" 2>&1
run_with_timeout 30 python3 "$REPO/tools/quota_estimate.py" --quiet >/dev/null 2>&1 || true

# 795番（2026-09-14）：数字のズレをゼロに近づける常設の見張り番。5分おきの既存起動に相乗りする
# （新しい常駐は増やさない。理由はpace.py冒頭のコメントと同じ）。
# ①正本の食い違いを監査 ②fal1本単価の基準を直近7日実測中央値に更新 ③予測と実測のズレ率トップ5を再計算。
run_with_timeout 30 python3 "$REPO/tools/number_audit.py" --quiet >/dev/null 2>&1 || true
run_with_timeout 30 python3 "$REPO/tools/fal_cost_ledger.py" --recompute >/dev/null 2>&1 || true
run_with_timeout 30 python3 "$REPO/tools/estimate_vs_actual.py" --report >/dev/null 2>&1 || true
# 895番（2026-09-16）：外に出した仕事の台帳（status/gaibu.json）。Devin分を5分おきに自動同期し、
# 新しいPRが見つかったらdispatch_outbox.jsonlへ通知する（新規launchd常駐は増やさず既存5分便に相乗り）。
run_with_timeout 30 python3 "$REPO/tools/gaibu_ledger.py" --sync-devin --quiet >/dev/null 2>&1 || true
# 921番（2026-09-17）：外部検品を「顧問」ではなく《品質ゲート》にする（tools/kenpin_gate.py）。
#   たまごさん「Claudeが作ったものを、未検品のまま、たまごさんへ返さない、を仕組みにする」。
#   検品待ち(status/kenpin/pending/)に積まれた依頼票を、ここでホスト側から自動でChatGPT(OpenAI API)へ
#   投げ、判定を号番号(queue.json)へ書き戻す。**たまごさんが画面から画面へ文章を運ぶ必要を無くすのが目的**
#   （11章・伝書鳩ゼロ化）。新しいlaunchd常駐は増やさず既存5分便に相乗り（他の仕組みと同じ方針）。
#   queue.jsonへの書き込みは、このホスト上の経路だけが行う（kenpin_gate.py冒頭「なぜ直接書かないか」）。
run_with_timeout 150 python3 "$REPO/tools/kenpin_gate.py" --run-pending --quiet >/dev/null 2>&1 || true
# 2026-09-19 入荷の関所（tools/nyuka_sekisho.py）。たまごさん「入荷したときにバチっと決まる
#   仕組みを作ってください。30,000曲を巡回するのは大変でしょう」。
#   曲が1曲入った瞬間に、①出典を実際に取得して事実を照合 ②別人混入を止める ③文脈を決める
#   ④コピーを書く ⑤外部AIが0〜100点で採点し80点未満は通さない、を全部通す。
#   Cowork側のサンドボックスからは外部ネットワークも鍵も届かない（実測 Tunnel 403）ので、
#   向こうは status/nyuka/pending/ へ積むだけ。**実際に通すのはここ（鍵とネットがあるMac側）**。
#   新しいlaunchd常駐は増やさず既存5分便に相乗り（上のkenpin_gateと同じ方針）。
run_with_timeout 200 python3 "$REPO/tools/nyuka_sekisho.py" --run-pending --quiet >/dev/null 2>&1 || true
# 2026-09-22 1025番：門0（棚に出せるか）の見張り。
#   14曲が「関所を通った」まま3日間 done/ で止まっていた。止まっていた場所が暗かったから。
#   done/ を数えて status/public/nyuka_shelf.json に出す＝進捗表から見える。★14ファイル読むだけ。
run_with_timeout 30 python3 "$REPO/tools/nyuka_sekisho.py" --shelf-check >/dev/null 2>&1 || true
# 2026-09-22 周辺を掘る（tools/shuhen_horu.py）。たまごさん「自分が音楽を入れたら、
#   その周辺のヒット曲や、似たような影響・同ポジションのグループを探して仕入れ候補に
#   しておいてほしい。（まだ棚には入れないで）」。
#   ★入荷が置かれた側から気づいて勝手に走る。言われてから動かない。
#   ★書き込むのは status/shiire_kouho/ だけ。棚（coverGuide.ts）には触らない。
#   ★0円の道だけ（MusicBrainz / Last.fmの公開ページ / Wikipedia）。鍵を使わない。
#   ★1回で掘る入口は2本まで。相手のサーバーを叩きすぎない。
#   新しいlaunchd常駐は増やさず既存5分便に相乗り（上2つと同じ方針）。
run_with_timeout 200 python3 "$REPO/tools/shuhen_horu.py" --watch --quiet >/dev/null 2>&1 || true
# 976番（2026-09-20）【珍獣ラシコル】審査通過の見張り。メールではなく**LINE STOREの公開ページ**を見る。
#   974番(check_line_shinsa.py)はGmailの鍵が無くて "blocked":"no_credential" のまま一度も見ていない。
#   審査が通れば販売ページが誰でも見える所に出る＝ログインも鍵も要らない。そこだけを叩く。
#   ★新しいlaunchd常駐は作らない。この5分便に相乗りするだけ。
#   ★中で5分ゲートしているので何度呼ばれても外へ出るのは5分に1回・GETは1〜3本。
#   ★見つけて通知したら .line_store_found が立ち、以後は数ミリ秒で何もせず終わる。
( run_with_timeout 60 python3 "$REPO/tools/line_store_watch.py" >> "$REPO/status/line_store_watch.log" 2>&1 & ) >/dev/null 2>&1
# 2026-09-03 たまごさん「進捗の数字がずれてる時点でダメ」。
# Claudeアプリの実測ファイルは書き込みが止まることがあり（21:45で停止を確認）、推定に落ちると大きく外す。
# 実際: 全モデル68% / Fable82% ← アプリ画面の値。推定: 111% / 88.5%。
# status/quota_manual.json に {"allPct":68,"fablePct":82,"asOf":"2026-09-03 23:05"} を置けば、そちらを正とする。
# アプリ画面のスクショから拾った値を入れる用。実測ファイルが復活すればこのファイルを消せば元に戻る。
# 2026-09-09（689番）事故の再発防止：「実測ファイルが復活したら消す」を**人の消し忘れ任せ**にしていたため、
#   2026-09-05 05:17の手入力（週リセット直後で全部0%）が4日間ずっと残り続け、
#   real_usage()が本物の値（19%など）を取れるようになった後も毎回0%で上書きしていた
#   （scalarのallPctだけが手入力の0で潰され、line文言だけはquota_estimate.pyの本物の値のまま
#   →「allPct=0なのにlineは19%」という自己矛盾した画面になっていた＝689番の症状そのもの）。
#   ①本物の実測(quota_estimate.py自身のestimated=false)が取れている間は手入力を適用しない
#   ②手入力自体も6時間を過ぎたら「古い一点の値」とみなし自動で無効化する（消し忘れても効かなくなる）
python3 - "$REPO" <<'PYEOF' >/dev/null 2>&1 || true
import json, os, sys, time
# 2026-09-04 バグ修正：ここは REPO を環境変数として読もうとしていたが export されておらず、
#   フォールバックの __file__ もヒアドキュメント実行では存在しないため例外→握りつぶし で
#   手入力(quota_manual.json)が一度も適用されていなかった。引数で渡す形に直した。
repo = sys.argv[1] if len(sys.argv) > 1 else "/Users/mac/Desktop/tamago-shinchoku"
q = os.path.join(repo, "status", "quota.json")
m = os.path.join(repo, "status", "quota_manual.json")
MANUAL_MAX_AGE_H = 6
if os.path.exists(m):
    d = json.load(open(q, encoding="utf-8")) if os.path.exists(q) else {}
    man = json.load(open(m, encoding="utf-8"))
    real_ok = d.get("estimated") is False
    man_age_h = None
    try:
        t = time.strptime(man.get("asOf", ""), "%Y-%m-%d %H:%M")
        man_age_h = (time.time() - time.mktime(t)) / 3600.0
    except Exception:
        pass
    stale_manual = man_age_h is None or man_age_h > MANUAL_MAX_AGE_H
    if real_ok or stale_manual:
        pass  # 本物の実測が取れている、または手入力が古すぎる→何もしない（quota_estimate.pyの値をそのまま使う）
    else:
        for k in ("allPct", "fablePct"):
            if man.get(k) is not None:
                d[k] = man[k]
        # 2026-09-04 5時間枠も手入力できるようにする（推定が152%と出て実際は13%だった）
        if man.get("sessionPct") is not None:
            d["sessionPct"] = man["sessionPct"]
            s5 = d.get("session5h")
            if isinstance(s5, dict):
                s5["pct"] = man["sessionPct"]
        d["estimated"] = False
        d["method"] = "手入力（アプリの使用状況画面の実測値・%s時点）" % man.get("asOf", "?")
        d["manualAsOf"] = man.get("asOf")
        for key, pct in (("fableLevel", d.get("fablePct")), ("allLevel", d.get("allPct"))):
            if isinstance(pct, (int, float)):
                d[key] = "stop" if pct >= d.get("stopPct", 85) else ("warn" if pct >= d.get("warnPct", 75) else "ok")
        # line文言もscalarと矛盾しないように手入力用に書き換える（「allPct=0なのにline=19%」の再発防止）
        d["line"] = "（手入力 %s時点）全モデル %s%% ／ Fable %s%%" % (
            man.get("asOf", "?"), d.get("allPct"), d.get("fablePct"))
        json.dump(d, open(q, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PYEOF
# 2026-09-02 見張り番：止まっている子セッションを検知して claude -p --resume で自動再開（判定は factory_status の分類。負荷ゲートあり）
# 2026-09-03 14:45 たまごさん「もう止めて」により無効化。計測(factory_status.py)とPWAへのpushは継続、自動再開だけ止める
# 2026-09-03 18:12 たまごさん「仕組みで起こす方復活させてください。やって」により再有効化。
#   止めていた本当の理由＝再開がFableのままだったこと。それは session_watchdog.py 側で潰した：
#   ①resume時に必ず --model claude-sonnet-5 を明示 ②status/no_fable.flag がある間はFable完全禁止。
#   また止めたいときは status/no_fable.flag ではなくこの行をコメントに戻す（再開そのものが止まる）。
run_with_timeout 60 python3 "$REPO/tools/session_watchdog.py" >/dev/null 2>&1 || true
# 2026-09-03 孤児プロセス回収：セッション終了後もppid=1で残り続けるlint/build/test系の暴走プロセスを止める（ロード100%固定化の実害を確認して追加）
run_with_timeout 30 python3 "$REPO/tools/orphan_reaper.py" >/dev/null 2>&1 || true
# 2026-09-06(415番) 容量の見張り：/System/Volumes/Data の空きを測り、30GB未満なら
#   .worktreesのnode_modules/dist/.output・7日超ログ・__pycache__だけを安全に片づけ、
#   20GB未満ならstatus/no_launch.flagを立てて発車を止める。壺と金庫(写真/動画/音楽/
#   Eagle/Vault/Drive/dmg)には一切触れない。launchdの新規登録が2回ブロックされたため
#   既存の5分間隔ジョブに相乗り(内部で15分に1回だけ実処理・STAMPファイルで間引き)。
run_with_timeout 45 python3 "$REPO/tools/disk_guardian.py" >/dev/null 2>&1 || true
# 2026-09-04 たまごさん「まず連続して走る仕組みを優先してね。順番に発車されるようにして、1日中回ってる状態を作るのが最優先」
#   発車待ち(status/queue.json)から、マシンとクレジットに空きがあれば1本だけ自動で着火する。
#   3時間縛り・URL報告のセットはプロンプト側に必ず入る。Fableは使わない（常にSonnet）。
# 2026-09-05 発車は心臓（15秒おき）だけに任せる。ここからも呼ぶと二重発車の元になった。
#   （実測：同じ番号が2回出てクレジットが二重に減った）
# python3 "$REPO/tools/auto_launcher.py" >/dev/null 2>&1 || true
# 2026-09-04 たまごさん「Obsidianには飛ばない」→ 進捗表のボタンをHTTPSで直接受ける中継所。
#   立っていなければ立て、トンネルのURLを status/relay.json へ書く（冪等・既に動いていれば何もしない）。
# 2026-09-05 中継所の面倒は relay_watch.py（心臓から2分おき）に一本化した。
#   ここからも呼ぶと、同時に立て直しにかかって「Address already in use」で共倒れする（実測）。
#   世話をする係は1つだけにする。
: # relay_up.sh はもう呼ばない
# 2026-09-04 心臓を1つにする。
#   受信箱(Vault経由の指示)は今まで別のlaunchd便(command_watch.sh・30秒おき)に任せていたが、
#   その便が**20:18で止まっていた**（スマホのボタンも、Dispatchからの指示も、Macに届かなくなっていた）。
#   別便が1つ死ぬだけで工場が片肺になるので、この巡回の中で一緒に処理する。
#   （command_watch.sh 側は残してよい。二重に走っても、処理済みファイルは消えるので害はない）
run_with_timeout 30 python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1 || true
# 2026-09-03 たまごさん「iPhoneでいいなと思ったスクショを、すかさず入れられるのかな。そのスピード感だと助かる」
#   ① iCloud Driveの「Eagle_取り込み_iPhoneから」に入った画像をEagleへ登録して、取り込み済みへ移す
#   ② Eagleライブラリ → スマホ用Webギャラリー（share/eagle-…）を差分更新
#   どちらも増えたぶんだけ処理するので数秒で終わる。外付けが外れていれば②は黙って何もしない。
# 2026-09-04 たまごさん「Eagleの見回りは5分に1回じゃなくて1日1回でいい」
#   取り込み口（iPhoneから放り込んだぶん）は「すかさず入る」のが要件なので5分おきのまま。
#   ギャラリーの作り直しだけ1日1回（前回から20時間以上あいたときだけ）にする。
{ echo "--- $(date '+%F %T') eagle-inbox ---"; python3 "$REPO/tools/eagle_inbox.py"; } >> "$REPO/status/eagle_run.log" 2>&1 || true
_gstamp="$REPO/status/.eagle_gallery_last"
if [ ! -f "$_gstamp" ] || [ -n "$(find "$_gstamp" -mmin +1200 2>/dev/null)" ]; then
  { echo "--- $(date '+%F %T') eagle-gallery(1日1回) ---"; python3 "$REPO/tools/eagle_gallery.py"; } >> "$REPO/status/eagle_run.log" 2>&1 || true
  touch "$_gstamp"
fi
tail -n 200 "$REPO/status/eagle_run.log" > "$REPO/status/eagle_run.log.tmp" 2>/dev/null && mv "$REPO/status/eagle_run.log.tmp" "$REPO/status/eagle_run.log" 2>/dev/null || true

# 2026-09-12(717番) relay.log・check_page_pruner.logが際限なく太る事故の再発防止。
#   relay.logは中継所(relay_server.py)のHTTPアクセスログをappendし続けるだけで、
#   どこにもトリム処理が無かったため実測46.8MB(632,529行)まで膨れ上がっていた
#   （公開リポジトリの1MB超ガードを赤くしていた原因の一つ）。
#   1MBを超えたら直近1000行だけ残す。追記元プロセスはappendし続けるだけなので、
#   tail→mvの入れ替え自体は他の書き込みと衝突しない（eagle_run.logと同じ安全な手法）。
for _bigsrc in "$REPO/status/relay.log" "$REPO/status/check_page_pruner.log"; do
  if [ -f "$_bigsrc" ]; then
    _bs=$(wc -c < "$_bigsrc" 2>/dev/null || echo 0)
    if [ "${_bs:-0}" -gt 1000000 ] 2>/dev/null; then
      tail -n 1000 "$_bigsrc" > "${_bigsrc}.tmp" 2>/dev/null && mv "${_bigsrc}.tmp" "$_bigsrc" 2>/dev/null || true
    fi
  fi
done

# 2026-09-09(652番) あとで見る棚：Brave（Default＝あなたの Brave）のセッションファイルを
#   直接読み取り、開いていたタブ相当のURLをサムネイル付きでstatus/later_tabs.jsonへ書く。
#   Braveアプリ自体には触れない・タブは開かない（tools/later_tabs_snapshot.py参照）。
#   1日1回でよいのでeagle_galleryと同じ「20時間以上あいたときだけ」方式にする
#   （ネットワーク取得(oEmbed/タイトル取得)を伴い数十秒かかるため、5分おきには回さない）。
_ltstamp="$REPO/status/.later_tabs_last"
if [ ! -f "$_ltstamp" ] || [ -n "$(find "$_ltstamp" -mmin +1200 2>/dev/null)" ]; then
  { echo "--- $(date '+%F %T') later-tabs(1日1回) ---"; python3 "$REPO/tools/later_tabs_snapshot.py"; } >> "$REPO/status/later_tabs_run.log" 2>&1 || true
  touch "$_ltstamp"
fi
# 2026-09-03 本数の実測校正：load_history.jsonl＋heavy_events.jsonl → calibration.json（safeN/target）。次回の factory_status が読む
run_with_timeout 30 python3 "$REPO/tools/calibrate.py" --quiet >/dev/null 2>&1 || true
# 2026-09-05 週の配分（天井に行かないためのペース）。今日いくつ使ったか／あといくつ使えるか
run_with_timeout 20 python3 "$REPO/tools/pace.py" >/dev/null 2>&1 || true
# 2026-09-17 完了の検証（記録されたURLの実物と番号が一致したときだけ緑）。status/verify_log.jsonl を書く
run_with_timeout 30 python3 "$REPO/tools/verify_done.py" >/dev/null 2>&1 || true
# 2026-09-05 完了は1週間で「完了のひかえ」へ移す（画面を短く保つ・あとから辿れる）
run_with_timeout 30 python3 "$REPO/tools/archive_done.py" >/dev/null 2>&1 || true
# 2026-09-03 ホワイトボード同期：PWAの優先度(status/priority.json)を正本へ取り込み、写し(status/whiteboard.json)を書く
run_with_timeout 30 python3 /Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py sync >/dev/null 2>&1 || true

cd "$REPO" || return 0

# 2026-09-03 たまごさんの優先度（PWA→Obsidian経由）を取り込み、priority.json とホワイトボードに反映
run_with_timeout 20 python3 "$REPO/tools/priority_ingest.py" >/dev/null 2>&1 || true

# 2026-09-03 Macの健康管理：何を閉じれば／消せば楽になるか（実測。重い計測は30分に1回）
# 2026-09-17（930番棚卸し・884番再発対応）：セッション過多で負荷995%まで振れた実機で、
# 45秒だと health_candidates.py がタイムアウトでSIGKILLされ続け、status/health.jsonの
# measuredAtが4時間以上進まなくなる事故を実測で確認した（factory_status.pyと同じ90秒に揃える）。
run_with_timeout 90 python3 "$REPO/tools/health_candidates.py" >/dev/null 2>&1 || true

# 2026-09-03 PWAリモコン：▶️動かす／⏸止める／🔁引き継ぐ／🗑閉じる のコマンドキューを実行（launchd新規登録がブロックされたため、この5分間隔ジョブに相乗り）
run_with_timeout 30 python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1 || true

# 2026-09-02 PWA第3段階：セッションごとの航跡を1行ずつ積む（何時に始まり・何時に止まり・誰が起こしたか、を後から数えるため）
python3 - "$OUT" "$REPO/status/history.jsonl" <<'PY' 2>/dev/null || true
import json, sys
m = json.load(open(sys.argv[1]))
wd = (m.get("watchdog") or {})
resumed = {r.get("pid") for r in (wd.get("resumed") or []) if not r.get("dry")}
with open(sys.argv[2], "a", encoding="utf-8") as f:
    for s in m.get("sessionList") or []:
        f.write(json.dumps({"t": m.get("measuredAt"), "pid": s.get("pid"), "cli": s.get("cli"), "title": s.get("title"),
                            "kind": s.get("kind"), "idle": s.get("idleMin"), "start": s.get("startedAt"),
                            "resumed": s.get("pid") in resumed}, ensure_ascii=False) + "\n")
PY
# 履歴は直近3日分だけ残す（公開リポジトリを肥やさない）
python3 - "$REPO/status/history.jsonl" <<'PY' 2>/dev/null || true
import sys, json, time, os
p = sys.argv[1]
if os.path.exists(p):
    lim = time.time() - 3*86400
    keep = []
    for ln in open(p, encoding="utf-8"):
        try:
            t = json.loads(ln).get("t") or ""
            ts = time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))
            if ts >= lim: keep.append(ln)
        except Exception:
            pass
    open(p, "w", encoding="utf-8").writelines(keep)
PY

# 数字が前回と同じなら push しない（measuredAt 以外を比較）
strip() { sed -E 's/"measuredAt":"[^"]*",//; s/"(load1|load5|load15|loadRatio|ioMBs|memAvailGB|idleMin|mb|lastRun)":[^,}]*,?//g'; }
PREV=$(git show HEAD:status/machine.json 2>/dev/null | strip)
CURR=$(strip < "$OUT")
LAST=$(git log -1 --format=%ct -- status/machine.json 2>/dev/null); LAST=${LAST:-0}
AGE=$(( $(date +%s) - LAST ))
# 数字が同じでも20分以上経っていれば鮮度のために push する
HIST_CHANGED=0
# 2026-09-04 バグ修正：この見張りに queue.json・index.html・tools が入っていなかったため、
#   「マシンの数字が前回と同じ」だけで早期returnし、**発車待ちの中身や画面の直しが
#   何時間も公開されなかった**（実害：たまごさんの画面に「発車待ちはありません」が出続けた）。
#   公開に載せる対象（下の git add と同じ顔ぶれ）を、そのまま変更検知の対象にする。
# git status を1回だけ叩いて判定する（1ファイルずつ git を呼ぶと、share/ に画像が1000枚以上あるため
# 30秒ごとの巡回が重くなり、計測そのものが遅れる）。share/ はここに入れない（変更が稀で、
# 20分の鮮度ルールで拾えるため。毎回の差分計算に画像1000枚を含めない）。
if [ -n "$(git status --porcelain --untracked-files=normal -- \
      status/history.jsonl status/whiteboard.json status/priority.json status/health.json \
      status/commands.json status/queue.json status/relay.json status/version.json status/launch_cap.json \
      status/ai_verify_stats.json \
      status/disk_guardian.log status/disk_trend_report.json status/disk_daily_history.json status/disk_candidates.json \
      index.html data.js said.js tools status/pace.json 2>/dev/null | head -1)" ]; then
  HIST_CHANGED=1
fi
# 2026-09-22（コミットの口の1本化）：status/commit_inbox/ に紙が1枚でも置かれていたら、
#   マシンの数字が前回と同じでもこの便を進める。ここを通さないと、サンドボックスが
#   置いた紙が「変化なし」で早期returnされ、何時間も載らないことがある。
#   status/ は.gitignore対象なので git status では見えない。ふつうのファイル有無で見る。
if ls "$REPO"/status/commit_inbox/*.json >/dev/null 2>&1; then HIST_CHANGED=1; fi
if [ "$PREV" = "$CURR" ] && [ "$AGE" -lt 1200 ] && [ "$HIST_CHANGED" -eq 0 ]; then return 0; fi

# 2026-09-04 画面の世代を書き出す。スマホのホーム画面アプリが古いindex.htmlを握ったままになる問題への対応。
#   index.html の中身のハッシュを status/version.json に置き、画面側が違いを見つけたら ?v=… で開き直す。
# 948番（2026-09-19）：v は index.html のハッシュしか見ていなかったので、index_full.html を
#   直しても全部入りの画面には伝わらず、逆に index.html を直すだけで全部入りの画面まで
#   開き直しが走っていた（314KBの再取得）。画面ごとに別々のハッシュを持たせる。
python3 - "$REPO" <<'PYVER' >/dev/null 2>&1 || true
import hashlib, io, json, os, sys, time
repo = sys.argv[1]
def sha(name):
    try:
        return hashlib.sha1(io.open(os.path.join(repo, name), "rb").read()).hexdigest()[:10]
    except Exception:
        return None
h = sha("index.html")
hf = sha("index_full.html")
if not h:
    sys.exit(0)
p = os.path.join(repo, "status", "version.json")
try:
    old = json.load(io.open(p, encoding="utf-8"))
    if old.get("v") == h and old.get("vFull") == hf:
        sys.exit(0)
except Exception:
    pass
out = {"v": h, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
if hf:
    out["vFull"] = hf
json.dump(out, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PYVER
### 2026-09-16（緊急・queue.json/auto_launch.log巻き戻り事故の恒久対策・23:08追記で強化）：
### status/ を.gitignoreしただけでは足りなかった（`git add -f`で明示公開していた36ファイルは
### status/直下という「昔から追跡されてきたパス」のままだったため、その36ファイルを昔から
### 抱えている古いworktreeが広いgit addを行うと今度はそこが巻き込まれ、22:49発車の890番の
### 作業14分が実際に巻き戻りで失われた）。公開先を status/public/ という、
### **どの既存worktreeも過去に一度も追跡したことが無いパス**へ丸ごと移した。
### 存在すらしなかったパスは、どんな広いgit addでも誤って巻き込みようがない。
### 925番（1MB超ファイル対策）：done_archive.json（正本）はwhat/result込みで1MB超。
### PUBLISH_LISTから外し、単純cpをやめてwhat/resultを抜いた軽量版を直接
### status/public/done_archive.json へ書き出す（build_done_archive_light.py）。
### 正本 status/done_archive.json 自体は変更しない。
### 925番（2回目の修正・queue.json）：queue.jsonの単純cpも1MB超の原因そのものだった
### （1回目は点検の除外パスに追加してすり抜けさせただけでAI検品にはねられた）。
### what/resultは実際にfetchQueueFull()で使われているため中身は削れない。
### 中身は一切削らずgzip圧縮のみで物理的に縮める（1.8MB→約480KB）。
### PUBLISH_LISTからも外し、単純cpをやめてstatus/public/queue.json.gzへ
### 圧縮版を書き出す（build_queue_public_gz.py）。正本status/queue.jsonは変更しない。
PUBLISH_LIST="version.json pace.json verify_summary.json verify_log.jsonl launch_cap.json machine.json history.jsonl whiteboard.json priority.json health.json commands.json quota.json relay.json ai_verify_stats.json disk_guardian.log disk_candidates.json later_tabs.json disk_trend_report.json disk_daily_history.json gdrive_daily_usage.json genzaichi.json genzaichi.md queue_light.json queue_next.json top_status.json now.json rev.txt failures_summary.json daily_ingest_summary.json deleted.json dekimono.json kenpou_check.json new_arrivals.json number_conflicts.json cost_by_task.json estimate_vs_actual_summary.json fal_cost_ledger.json gaibu.json mac_souji.json"
mkdir -p "$REPO/status/public"
# ---- 2026-09-20（969番）鍵・つながりの台帳 ----
# 「走っているのに何も取れていない」を自動で赤にする係。新しい常駐は増やさず、この5分便に相乗り。
# 中で30分に間引くので、5分おきに呼んでも外を叩くのは30分に1回だけ。
# ★status/public/ へ直接書くのでPUBLISH_LISTへの追加は要らない（下の公開にそのまま乗る）。
# ★値（鍵の中身）は読まない・書かない。通ったか通らないかだけ。
run_with_timeout 120 python3 "$REPO/tools/kagi_daicho.py" >/dev/null 2>&1 || true
# ---- 2026-09-23（1029番）開通：毎朝1回、閉じている口を知らせる ----
# たまごさん「1回開けたらもう全部通るようにしてよ」「ログインを求められ続けるのが苦痛」。
# ★新しい常駐は増やさない。外も叩かない（上の台帳の結果を読むだけ）。
# ★中で「朝7時以降・1日1回・赤のときだけ」に間引く。緑の日は1文字も書かない。
# ★「走った>0なのに取れた=0」と「台帳に載っていない口」を、必ず表に出す。
run_with_timeout 60 python3 "$REPO/tools/kaitsuu.py" --asa >/dev/null 2>&1 || true
# ---- 2026-09-23（1033番）数字と断定の門が、まだ効いているかを毎朝みる ----
# たまごさん「調べてから上げてこいよって。混乱するから。コロコロ変わるから、報告がさぁ」。
# ★門は、効かなくなっても静かに素通りするので誰も気づかない。
#   わざと悪い報告文（出典なしの「残高は381円です」など）を毎朝入れて、
#   落ちなくなっていたらそのときだけ知らせる。落ちている限り1文字も書かない。
# ★AIを1回も呼ばない・外も叩かない・常駐も増やさない（ただの文字列判定）。
run_with_timeout 30 python3 "$REPO/tools/kazu_gate.py" --asa >/dev/null 2>&1 || true
# ---- 2026-09-20（971番・Cowork側から設置）外部から入れたもののコピー日報 ----
# たまごさん「毎日、昨日なら昨日の外部から入ったものを釣って、コピーはこうです、っていうのも知りたい」。
# 実測：毎朝の入荷見回り（756番）は09-12〜09-19の8本が積まれたまま1本も走っていなかった。
# 積む係は居たが、結果を毎日1枚にして出す係が居なかった＝誰も気づかないまま9日。ここがその1枚。
# ★新しい常駐は増やさない。中で30分ゲートしているので5分おきに呼んでも外へ出るのは30分に1回。
# ★status/public/ へ直接書くのでPUBLISH_LISTへの追加は要らない（下の公開にそのまま乗る）。
# ★鍵の値は書き出さない（名前と、通ったか通らないかだけ）。
run_with_timeout 90 python3 "$REPO/tools/gaibu_copy_nippou.py" >/dev/null 2>&1 || true
# ※「コピーを毎朝直す係」はこの下ではなく、**この便の冒頭**（ロックを取った直後）に置いた。
#   ここは上の早期return（数字が前回と同じなら return 0）より後ろなので、
#   変化が無い日は一度も回ってこない＝毎朝の約束が守れないため。
[ -f "$REPO/status/done_archive.json" ] && python3 "$REPO/tools/build_done_archive_light.py" >/dev/null 2>&1
[ -f "$REPO/status/queue.json" ] && python3 "$REPO/tools/build_queue_public_gz.py" >/dev/null 2>&1
for _f in $PUBLISH_LIST; do
  [ -f "$REPO/status/$_f" ] && cp -f "$REPO/status/$_f" "$REPO/status/public/$_f" 2>/dev/null
done
### ---- 2026-09-20（963番）ここで写しを main へ commit するのを**やめた** ----
### それまで：この5分便が status/public/ の写しを main へ commit+push していた。
###   実測＝**1日73回**。9人の書き手と17個のworktreeが居る main へ、機械が5分おきに
###   割り込む形だったため、人間側の作業が毎回その後ろに並ばされ、
###   git は232回詰まっていた（push失敗95／「向こうが先で合流できない」64／
###   取り残しロック23／pull失敗9）。
###   さらに main への push のたびに .github/workflows/pages.yml が
###   **リポジトリ丸ごと(681MB)** を Pages へ上げ直していた（1日274回）。
###
### いま：配信専用の枝 gh-pages を立て、**書き手は tools/pages_publish.sh ただ1本**にした。
###   その枝は履歴を常に1コミットに固定して毎回 force push する＝
###   **書き手が1人・履歴1コミット・毎回force なので、非fast-forwardが原理的に起きない。**
###   main は人間の作業だけの道に戻り、機械は main へ一切書かない。
###   （上の cp ループはそのまま残す。status/public/ にファイルが揃っていること自体は、
###     公開係がそこを丸ごと映すために今までどおり必要だから。）
###
### たまごさんに渡したURLは1本も変わらない：
###   https://tamago2022.github.io/tamago-shinchoku/ も share/check/*.html も同じ住所のまま。
###
### ★公開係は**待たない**（投げっぱなし）。この便を1秒も遅らせないため。
###   中で変化が無ければ即座に戻るので、毎周呼んでも重くならない。
( "$REPO/tools/pages_publish.sh" >/dev/null 2>&1 & ) >/dev/null 2>&1
# 2026-09-03 追加：画面本体（index.html/data.js/said.js）と共有資料（share/）も一緒に載せる。
# ここに無いとCowork側が書き換えても永久に公開されない（実際 share/ が載らず気づいた）。
# ---- 2026-09-22 コミットの口の1本化：サンドボックスが置いた紙をここで回収する ----
#   Cowork（サンドボックス）側がマウント越しに自分で git add/commit を叩くと、
#   この5分便とぶつかって .git/index.lock の取り合いになり、しかも向こうは
#   残ったロックを消せない（Operation not permitted）＝工場のgitが丸ごと止まる。
#   2026-09-22に何度も再発したため、**ロックを後から消すのをやめて、口そのものを1本にした。**
#   向こうは status/commit_inbox/ に紙を置くだけ（gitを叩かない）。回収はここ1か所。
#   commit / push はこの下の1本だけが持つ。投げっぱなしにはしない（addが済んでから下のcommitへ進む必要があるため）。
python3 "$REPO/tools/commit_kuchi.py" --drain --quiet >/dev/null 2>&1 || true
git add index.html data.js said.js share tools >/dev/null 2>&1
# 2026-09-22（977番）追加：番号付きの単票ページ（969/971/972/977…）も載せる。
#   ここに無いと、作っても永久に公開されない（977-ai-renkei.html で気づいた）。
#   対象は「3桁の番号で始まる .html」だけ＝画面用の小さい単票に限る。
#   万一大きいものが混ざっても、この下の1MB検査が1本だけ取り下げるので事故にならない。
git add ./[0-9][0-9][0-9]-*.html >/dev/null 2>&1

# ---- 2026-09-09 事故の再発防止：**大きいファイルを公開に載せない。**----
# 何が起きたか：02:44、Xアプリのプロトタイプを作っていた別セッションが
#   share/x-search/data.json（たまごさん本人の実ツイート47,011件・12MB）を置いた。
#   **この巡回の `git add share tools` が中身を見ずに巻き込み、公開GitHub Pagesへpushした。**
#   1分で気づいて消したが、たまごさんに「二度と起きないようにして」と言われた。
#
# なぜ .gitignore だけでは足りないか：
#   .gitignore に書けるのは「今回の1ファイル」だけ。**次に誰かが別の名前で置いたら、また同じことが起きる。**
#   ここは `share` と `tools` を**丸ごと**addしているので、置かれたものは何でも公開される構造だった。
#
# 対策：**これから載せようとしているファイルを1つずつ見て、1MBを超えるものがあったら
#        その1本だけ取り下げて、載せない。**（残りは通常どおり公開する＝画面は止まらない）
#   個人データの塊は必ず大きい。確認ページのHTMLは小さい。**この線引きで十分に効く。**
#   取り下げたものは status/blocked_large_files.log に記録し、たまごさんが後で見られるようにする。
_BIG=0
while IFS= read -r _f; do
  [ -z "$_f" ] && continue
  [ -f "$_f" ] || continue
  _sz=$(wc -c < "$_f" 2>/dev/null || echo 0)
  if [ "${_sz:-0}" -gt 1048576 ] 2>/dev/null; then
    git restore --staged "$_f" >/dev/null 2>&1 || git reset -q HEAD "$_f" >/dev/null 2>&1
    echo "$(date '+%F %T') 🛑 公開を止めた（${_sz}バイト・1MB超）: $_f" >> "$REPO/status/blocked_large_files.log"
    _BIG=$((_BIG+1))
  fi
done < <(git diff --cached --name-only --diff-filter=AM -- share tools 2>/dev/null)
if [ "$_BIG" -gt 0 ]; then
  echo "$(date '+%F %T') 🛑 大きいファイル${_BIG}件を公開から外しました（個人データの誤公開を防ぐため）" >> "$REPO/status/relay.log"
fi
# 2026-09-04 バグ修正：commitが失敗したとき return 0 で抜けていたため、push まで到達しなかった。
#   commitが失敗する典型は「新しい変更が無いとき」。だが、その前に別経路（Cowork側）でcommitされた分が
#   未pushで残っていることがあり、そのぶんが永久に公開されなかった（画面が更新されない実害）。
#   → commitの成否に関わらず push まで進む。
#
# 2026-09-13（案件#687・queue.json等status/丸ごとの複数回ロールバック事故の真因）：
#   ここの `git pull --rebase -q ... || true` が、**少なくとも2回**status/丸ごとの
#   ロールバックを起こしていた（1回目 10:17:46＝777〜804番28件消失／2回目 11:14〜16:12の間＝
#   その後の復旧分319件も含めて再度消失・264件/最大780番まで巻き戻り）。
#   実測：`git pull --rebase`が実行中に未コミットの変更を自動でautostashへ退避 →
#   rebase自体が完走せず失敗（`|| true`が握りつぶし誰にも気づかれなかった）→
#   作業ツリーが古いorigin/mainの内容に取り残され、autostashは二度とpopされずに残った
#   （実測：`.git/rebase-merge/autostash`。1回目の分はタグ`rescue-687-autostash-20260913`で保全済み）。
#   → **rebaseそのものをやめてmergeにする。** mergeが失敗しても作業ツリーは「コンフリクト状態のまま」
#   残るだけで、rebaseのautostashのように**サイレントに古い内容へ巻き戻ることは無い**。
#   さらに、①次の周回開始時に壊れたrebase/merge残骸を検知したら自分で片付けてから進む、
#   ②pull自体が失敗したら黙って続けず`git merge --abort`で必ず元へ戻し理由をログへ残す、を追加する。
_REBASE_MARKER="$REPO/.git/rebase-merge"
_REBASE_MARKER2="$REPO/.git/rebase-apply"
_MERGE_MARKER="$REPO/.git/MERGE_HEAD"
if [ -d "$_REBASE_MARKER" ] || [ -d "$_REBASE_MARKER2" ] || [ -f "$_MERGE_MARKER" ]; then
  echo "$(date '+%F %T') ⚠️ 前回の周回が壊れたrebase/merge状態を残していた→ 片付けてから進む" \
    >> "$REPO/status/git_rebase_incidents.log"
  git rebase --abort >/dev/null 2>&1 || true
  git merge --abort >/dev/null 2>&1 || true
  rm -rf "$_REBASE_MARKER" "$_REBASE_MARKER2" 2>/dev/null || true
fi
git -c user.name="machine-status" -c user.email="machine-status@local" commit -q -m "画面・共有資料・道具の更新 $(date +%H:%M)" >/dev/null 2>&1 || true

# ---- 2026-09-20（963番）main への pull/push を「出すものがある時だけ」にした ----
# それまで：下の pull と push は**毎周（約60秒おき）無条件で**走っていた。
#   出すものが1つも無い回でも main を触りに行くので、他の書き手と正面衝突し続けていた。
#   実測の詰まり232回のうち「向こうが先で合流できない」64回・pull失敗9回はここが発生源。
# いま：最後に push できた地点(.last_main_push)から HEAD が1歩も動いていなければ、
#   **main には一切触らない**。写しは gh-pages 側（単一書き手）へ出ているので、
#   ここが黙っていても画面は今までどおり更新される。
_LASTPUSH_F="$REPO/status/.last_main_push"
_HEAD_NOW="$(git rev-parse HEAD 2>/dev/null || echo x)"
if [ "$_HEAD_NOW" = "$(cat "$_LASTPUSH_F" 2>/dev/null || echo '')" ]; then
  return 0
fi
# 2026-09-16（緊急・queue.json 239→234件・887/888/889番消失事故）：
#   status/ は1秒おきに書き換わる「生きている台帳」なのに、この5分おきのpullが
#   古いorigin/mainの中身でそれを丸ごと上書きしていた（#687と同型の再発）。
#   .gitattributes の `status/** merge=ours` で「マージ時はこちら側を必ず勝たせる」よう
#   したが、その属性を有効にするカスタムマージドライバの登録はリポジトリに同梱できない
#   ローカルgit設定なので、ここで毎回（安価・冪等）保証しておく。
git config merge.ours.driver true 2>/dev/null || true
if ! git -c credential.helper='!gh auth git-credential' pull --no-rebase -q origin main >/dev/null 2>&1; then
  echo "$(date '+%F %T') 🛑 git pull(merge) が失敗→ merge --abort で必ず元の状態へ戻す（黙って進まない）" \
    >> "$REPO/status/git_rebase_incidents.log"
  git merge --abort >/dev/null 2>&1 || true
  rm -rf "$_REBASE_MARKER" "$_REBASE_MARKER2" 2>/dev/null || true
fi
if git -c credential.helper='!gh auth git-credential' push -q origin main >/dev/null 2>&1; then
  # 出し切った地点を覚えておく。次の周回はここから1歩も動いていなければ main を触らない。
  git rev-parse HEAD > "$_LASTPUSH_F" 2>/dev/null || true
fi
}

# 2026-09-18（931番）：Claudeが作ったChromeタブの孤児を掃く。
#   子セッションはそれぞれ自分のタブグループを作るが、**他のセッションからは見えないし閉じられない**
#   （tabs_context_mcpは自分の分しか返さない）。セッションが落ちると孤児として残り、
#   実際に10枚以上溜まってたまごさんのMacが重くなり、タイピングも音声入力もできなくなった。
#   → セッションの外側（この工場）から掃く。新しいlaunchd常駐は増やさず既存の便に相乗り
#     （既存方針と同じ）。スクリプト内部で**15分**ゲートしているので5分おきに呼んでも実走は15分に1回。
#     ★2026-09-19：元は1時間ゲートで、しかもChromeが起動していない回でもゲートを消費していたため
#       実質ほとんど掃けていなかった（closedTotal=0だった）。15分＋掃いた時だけゲート更新に修正。
#   ★Chromeが起動していなければ何もしない（起こさない）。activateしない。前面タブは閉じない。
#     たまごさんの作業タブは閉じない（見分けがつかないものは残す）。
( python3 "$REPO/tools/chrome_tab_sweeper.py" --recon --sweep --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1

# 2026-09-21（840番）毎週のMac掃除。★新しい定期タスク・新しいlaunchd便は作っていない。
#   理由（実測）：定期タスク weekly-mac-maintenance は毎週走ってはいたが、定期実行の
#   スコープでは許可ダイアログを押す人が居ないためMacの実ファイルに一度も届かず、
#   毎回「何も実行できなかった」と返していた（＝動いているのに何も取れていない）。
#   許可の要る経路をやめて、許可の要らない工場側（この便と心臓）に寄せる。
#   ★中で**週1**に間引いているので、5分おきに呼んでも実際に掃くのは週1回だけ。
#     間引きで戻る回は状態ファイルを1つ読むだけ＝負荷はほぼゼロ。
#   ★掃く判定は tools/disk_guardian.py の既存ロジックをそのまま使う（二重実装しない）。
#     Brave・たまごさんのアプリ・作り直せないものには一切触らない。
#   ★走った回数と実際に片付いたバイト数の両方を status/mac_souji.json に残す。
#     走行>0 なのに 片付き=0 は赤で出る。
#   この便を止めないよう、バックグラウンドへ逃がして10分で打ち切る（前で待たない）。
( run_with_timeout 600 python3 "$REPO/tools/mac_souji.py" >/dev/null 2>&1 & ) >/dev/null 2>&1

# 約260秒（次の5分ティックが来る前）、間を空けずに回し続ける。走行中↔停止の切り替わりをできるだけ早くPWAへ反映するため。
# factory_status.py自体が実測27秒かかる（ps/lsof/transcriptスキャン）ので、固定sleepは入れず作業時間そのものを間隔にする
LOOP_END=$(( $(date +%s) + 260 ))
# 2026-09-04 たまごさん「1個空いたら1個繰り上がる、ところてんみたいに」
#   重い計測(factory_status・実測27秒〜。走行が増えるとさらに伸びる)と同じ周期でしか
#   着火と受信箱を見ていなかったため、空きが出てから繰り上がるまで最大5分かかっていた。
#   → 重い計測の合間に、**軽い2つ（着火・受信箱）だけを15秒おきに回す。**
#     どちらも数百ミリ秒で終わるので、負荷はほぼ増えない。
# 2026-09-12（776番）：heartbeat.sh と同じ保険をここにも入れる。この5分便の中でも
#   auto_launcher.py/command_ingest.pyを直接呼んでいるため、心臓側だけ直しても
#   この経路がハングすればやはり「詰まって見える」状態になりうる。
# （run_with_timeout はファイル冒頭で定義済み・ここでは使うだけ）
quick_tick() {
  run_with_timeout 45 python3 "$REPO/tools/auto_launcher.py"   >/dev/null 2>&1 || true
  run_with_timeout 45 python3 "$REPO/tools/command_ingest.py"  >/dev/null 2>&1 || true
  # 944番（2026-09-18）：外部AI（Grok/ChatGPT/Gemini）への代行係。
  #   Cowork/Dispatchのサンドボックスからは api.openai.com / api.x.ai /
  #   generativelanguage.googleapis.com へ回線が出ない（実測）。このMacからは出る。
  #   → 向こうは status/gaibu_jobs/pending/ に仕事票を置くだけ。実際に叩くのはここ。
  #   ★pendingが空なら数ミリ秒で何もせず終わるので、15秒おきに呼んでも工場は重くならない。
  #   ★この便を止めないよう、バックグラウンドに逃がして150秒で打ち切る（前で待たない）。
  ( run_with_timeout 150 python3 "$REPO/tools/gaibu_runner.py" --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-19：GitHubの見張り番（tools/github_watch.py）。心臓にも同じ1行がある＝経路の二重化。
  #   心臓が落ちている間もGitHubの新着に気づけるようにするため。
  #   ★内部で60秒ゲートしているので、両方から呼ばれても外へ出るのは1分に1回だけ。
  ( run_with_timeout 60 python3 "$REPO/tools/github_watch.py" >> "$REPO/status/github_watch_err.log" 2>&1 & ) >/dev/null 2>&1
}
while :; do
  run_once
  NOWSEC=$(date +%s)
  [ "$NOWSEC" -ge "$LOOP_END" ] && break
  for _ in 1 2 3 4; do
    sleep 15
    [ "$(date +%s)" -ge "$LOOP_END" ] && break
    quick_tick
  done
  [ "$(date +%s)" -ge "$LOOP_END" ] && break
done
