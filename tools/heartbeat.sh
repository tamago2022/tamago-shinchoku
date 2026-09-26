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
# ---- 2026-09-20（975番）「既に心臓が動いています」が5秒おきに無限に書かれていた ----
# 実測：2026-09-20 03:58〜04:12 のログが、この1行だけで埋まっていた（1日あたり約17,000行）。
#   仕組み：launchd の心臓便は KeepAlive=true / ThrottleInterval=5。
#   ところが本物の心臓(pid 84548)は launchd の外から起動されていたため、
#   launchd便が起動 → ここで「既に居る」と分かって exit 0 → launchdが5秒後にまた起動、
#   を永久に繰り返していた（launchctl list でも心臓便のPIDが常に空だった）。
#   ログが5秒ごとに1行ずつ太り、下の「たまに刈る」で200行に刈られるので、
#   **本当に知りたい記録（いつ詰まったか・いつ交代したか）が全部流されて消えていた。**
# 直し方：exit しない。**控えとして待つ。**launchdから見れば起動しっぱなし＝再起動churnが止まる。
#   先代が消えたらそのまま自分が心臓になる（下の $$ 書き込みへ落ちる）＝自己修復は今までどおり。
if [ -f "$PIDF" ]; then
  OLD="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${OLD:-}" ] && [ "$OLD" != "$$" ] && kill -0 "$OLD" 2>/dev/null; then
    echo "$(date '+%F %T') 既に心臓が動いています（pid $OLD）。控えとして待機します（pid $$）" >> "$LOG"
    while :; do
      CUR="$(cat "$PIDF" 2>/dev/null || true)"
      [ -z "${CUR:-}" ] && break                      # PIDファイルが消えた＝先代が退いた
      [ "$CUR" = "$$" ] && break                      # 自分が正規になった
      kill -0 "$CUR" 2>/dev/null || break             # 先代が死んだ＝自分が引き継ぐ
      sleep 30
    done
    echo "$(date '+%F %T') 先代が居なくなったので、控え（pid $$）が心臓を引き継ぎます" >> "$LOG"
  fi
fi
echo $$ > "$PIDF"

# ---- 2026-09-22（1018番）「生きてる」と「仕事が進んでる」を1つの信号で兼務するのをやめた ----
# 実測（heartbeat_watchdog.log 全349件）：
#   心臓の「死亡宣告」の中央値は73秒、最小60秒。600秒を超えたのは**349件中わずか3件**。
#   ＝ 346件（99.1%）は死んでいない。**忙しかっただけの心臓を、見張りが殺していた。**
# なぜそうなったか：
#   .heartbeat_alive は下のループの**先頭で1回だけ** touch していた。
#   ところが同じループの中で auto_launcher(最大45秒) と command_ingest(最大45秒) を
#   順番に待つので、1周が90秒を超えうる。見張りの閾値は60秒。**構造的に必ず超える。**
#   見張り側のコメントは「心臓は15秒ごとにtouchする」と書いてあるが、それは事実ではなかった。
#   そして kickstart -k は kill を伴うので、殺された拍子に auto_launcher.py が孤児化して
#   ロックを握ったまま残り、**投げた仕事が一度も走りきらない**（順番待ちのリセット）。
# 直し方（穴を塞がない。信号の素材を替える）：
#   Kubernetes が liveness probe と readiness probe を分けている理由と同じ。
#   liveness に「仕事が終わったか」を混ぜると、仕事が重いだけで全部再起動になる。
#   → 鼓動は**仕事に絶対に邪魔されない専用の子プロセス**が5秒ごとに打つ。
#     これは「シェルが存在するか」だけを表す。仕事が何秒かかっていても打ち続ける。
#   → 「仕事が進んでいるか」は別ファイル .heartbeat_progress に、1周終わるたびに書く。
#     本当に固まった時はこちらが古くなるので、見張りはそれを見る（下の閾値は10分）。
#   これで「忙しい」と「死んだ」が初めて区別できる。信号は1か所（この2ファイル）だけ。
ALIVE_F="$REPO/status/.heartbeat_alive"
PROGRESS_F="$REPO/status/.heartbeat_progress"
touch "$ALIVE_F" "$PROGRESS_F" 2>/dev/null || true
MAIN_PID=$$
( while kill -0 "$MAIN_PID" 2>/dev/null; do
    touch "$ALIVE_F" 2>/dev/null || true
    sleep 5
  done ) &
BEATER_PID=$!

# 退くときは「自分のPIDが書いてあるときだけ」消す。
# 2026-09-05 17:25 これを付けずに無条件で消していたため、交代した古い心臓が
#   **新しい心臓のPIDファイルまで道連れに消して**、誰も居ないのに居るように見えたり、
#   逆に立て直しの判断が狂ったりした（17:17を最後に心臓が止まった）。
cleanup_pid() {
  kill "$BEATER_PID" 2>/dev/null || true
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

# ---- 2026-09-18（Cowork側から設置）相乗りスクリプトの起動そのものを間引く ----
# 実測で見えた「重いほど重くなる」仕組み：
#   このループには「投げっぱなし(&)」の python3 が14本並んでいて、15秒ごとに全部を起動する。
#   ＝**1分あたり約56回、pythonインタプリタを起動していた。**
#   どれも中で「1時間に1回」「1日に1回」に間引いているので"仕事"はしていないが、
#   **インタプリタ起動のコストだけは毎回満額かかる。**
#   さらに、Macが重いほど1本あたりの起動が延びるのに、心臓は待たずに次の15秒へ進むので、
#   同じスクリプトが何本も重なって走り、重いほどもっと重くなる（正のフィードバック）。
#   実測：2026-09-18 07:11〜07:16 auto_launcher.py/command_ingest.pyが45秒の強制終了を連発し、
#        07:15にこの心臓自体が停止。以後 machine.json は07:26から1時間半更新されなかった。
# → 中で1時間・1日に間引いているものを、15秒おきに叩き起こす理由はどこにも無い。
#   **起動の頻度そのもの**をここで落とす。中の間引き設定は一切変えない＝挙動は変わらない。
#   毎分の起動回数：約56回 → 約12回（約8割減）。
TICK=0
tick_every() { [ "$(( TICK % $1 ))" -eq 0 ]; }

# ---- 2026-09-26（1153番）Macが寝ないように、心臓が自分で押さえる ----
# たまごさん「Claudeがオフラインになる。リモートも切れる。切れない方法はないのか。」
# 実測（status/1153/kireru_gen-in.md）：
#   ・`pmset -g custom` の AC Power が **sleep 1**＝電源につないでいても**1分放っておくと寝る**。
#   ・いま寝ないでいられるのは `caffeinate -dims` が居るときだけ。しかもそれは
#     `claude remote-control` が自分のために連れてきたもの。
#     → **claude が落ちると caffeinate も消え、1分後にMacが寝る**＝リモートも切れる。
#   ・`sudo pmset -c sleep 0` が本筋だが、sudoのパスワードはAIが打たない（憲法）。
# → そこで **claudeが居ても居なくても寝かせない番人**を、心臓の寿命に紐づけて1本だけ立てる。
#   ・`-w $$` なので **心臓が死ねば番人も一緒に消える**（居残りゴミにならない）
#   ・exec で自分を入れ替えてもPIDは変わらないので、番人は生き続ける（二重に立てない）
#   ・0円。新しいlaunchd便も増やしていない。
#   ★戻し方：この4行を消す、または `pkill -f "caffeinate -dims -w $$"`（次の起動で戻る）
if ! pgrep -f "caffeinate -dims -w $$" >/dev/null 2>&1; then
  caffeinate -dims -w $$ >/dev/null 2>&1 &
  echo "$(date '+%F %T') 🛡 寝かせない番人を立てました（caffeinate -dims -w $$）" >> "$LOG"
fi

echo "$(date '+%F %T') 心臓を起動しました（pid $$）" >> "$LOG"
while :; do
  TICK=$(( (TICK + 1) % 40 ))   # 15秒 × 40 = 10分で一周
  # 2026-09-16：詰まり判定を auto_launch.log の更新（=実際に発車/回収があった時だけ書かれる）
  # に頼っていたため、「走行0本で書くことが無いだけ」でも詰まっていると誤判定し、
  # machine_status_push.sh が正常な心臓を何度も殺して立て直す事故が起きた
  # （殺した拍子に子の auto_launcher.py が孤児化してロックを握ったまま残り、発車が止まった）。
  # 2026-09-22（1018番）ここで touch するのはやめた。上の専用の子プロセスが5秒ごとに打つ。
  #   ここで打つと「1周が終わるまで次の鼓動が無い」＝1周90秒なら60秒の見張りに必ず殺される。
  #   鼓動＝生存、下の .heartbeat_progress＝仕事の進行。役割を混ぜない。
  CYCLE_STARTED_AT=$(date +%s)
  # ---- 2026-09-24（命綱）：★常駐は直しただけでは反映されない。
  #   走っているループは、書き換わった後も古いファイルを読み続ける。
  #   これまではここで人が「起こし直す」コマンドを打つ必要があった＝たまごさんの手が要った。
  #   → 自分のファイルが書き換わったことに自分で気づいて、自分を入れ替える。
  #     exec なのでPIDは変わらない＝launchdから見ても交代したことにならず、churnも起きない。
  ME_MTIME="$(stat -f %m "$0" 2>/dev/null || stat -c %Y "$0" 2>/dev/null || echo 0)"
  if [ -z "${ME_MTIME_AT_START:-}" ]; then
    ME_MTIME_AT_START="$ME_MTIME"
  elif [ "$ME_MTIME" != "$ME_MTIME_AT_START" ]; then
    echo "$(date '+%F %T') 🔁 心臓のファイルが書き換わったので、自分で新しい方に入れ替わります" >> "$LOG"
    kill "$BEATER_PID" 2>/dev/null || true
    trap - EXIT INT TERM
    exec bash "$0" "$@"
  fi
  # 自分が正規の心臓でなくなっていたら（誰かが入れ直した）静かに退く
  CUR="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${CUR:-}" ] && [ "$CUR" != "$$" ]; then
    echo "$(date '+%F %T') 新しい心臓（pid $CUR）に交代します" >> "$LOG"
    exit 0
  fi
  # ---- 2026-09-12（776番①）：心臓を立て直す側（machine_status_push.sh・launchd 5分便）が
  #   死んでいないかを、心臓自身が確かめる。「見張りの見張り」を積み上げるのではなく、
  #   相互監視（心臓⇄5分便）にして、どちらか生きている方が相手を起こせる形にする。
  #   実測はmachine.json（この5分便が毎回必ず書く）の最終更新時刻で行う。15分止まっていたら
  #   launchdへ直接蹴り直しを頼む（新規ジョブ登録ではなく既存ジョブのkickstartのみ）。
  # ---- 2026-09-24（命綱）：ここは「起こすのをやめる条件」を持っていなかった。
  #   実測：09-24 04:56〜05:20 のあいだ、17秒おきに kickstart を打ち続けていた（数百回）。
  #   相手は起きないのに永遠に叩く＝無限に起こし続ける状態。ログもこれで埋まっていた。
  #   → 起こす判断は tools/inochi.py に一本化した。あちらは3回続けて死んだら諦める。
  #   ★ここでは直接 kickstart を打たない。
  tick_every 2 && ( python3 "$REPO/tools/inochi.py" --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 心臓自身が「生きている」印を命綱の台帳に押す（死亡判定はあちらが持つ）
  ( python3 "$REPO/tools/inochi.py" --ikiteru heartbeat >/dev/null 2>&1 & ) >/dev/null 2>&1
  # ★1163番（2026-09-26）進捗表の「工場の体温」（心臓・最後の発車・今の負荷）。
  #   既存の genzaichi.json / health.json は2〜5時間古く、体温には使えなかった。
  #   ここは毎周なので常に数十秒以内の数字だけが載る。書くだけ・0.05秒。
  ( python3 "$REPO/tools/1163_taion.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  run_with_timeout 45 python3 "$REPO/tools/auto_launcher.py"  >/dev/null 2>&1
  [ $? -eq 124 ] && echo "$(date '+%F %T') ⏱ auto_launcher.pyが45秒以内に終わらず強制終了しました" >> "$LOG"
  run_with_timeout 45 python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1
  [ $? -eq 124 ] && echo "$(date '+%F %T') ⏱ command_ingest.pyが45秒以内に終わらず強制終了しました" >> "$LOG"
  # ---- ここから下は「投げっぱなしの相乗り」。tick_every で起動の頻度を落としてある ----
  # 数字の根拠は各行のコメントに書いてある「中の間引き」そのもの。
  # それより細かく叩く意味は無いので、中の間引きに合わせた周期で呼ぶ。
  # ログインが戻ったら自分で気づいて再開する（10分に1回だけ試す）
  #   ← 元から「10分に1回」と書いてあったのに毎サイクル起動していた。10分に揃える。
  tick_every 40 && python3 "$REPO/tools/auth_watch.py"     >/dev/null 2>&1 || true
  # 2026-09-20（975番）ログインの生死・鍵の寿命・切れる前の予告を1か所にまとめた係。
  #   auth_watch.py は「切れた後に戻ったら旗を外す」だけだった（＝切れてからしか動かない）。
  #   auth_keeper.py は「切れる前に言う」「1年もつ鍵(setup-token)へ正本を移す」「死んだ鍵を
  #   立てっぱなしにしない」までを持つ。中で30分（切れているときは10分）に間引くので、
  #   10分おきに呼んでもAPIを叩く回数は増えない。投げっぱなしにして心臓は待たない。
  tick_every 40 && ( python3 "$REPO/tools/auth_keeper.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-05：中継所（進捗表→Mac）が死ぬと、たまごさんがボタンを押しても何も届かない。
  #   5分便まかせだと最大5分間ボタンが効かないままなので、心臓でも2分に1回見る。
  #   **投げっぱなしにして心臓は待たない**（対話待ちで工場を止めた07:03の事故の教訓）。
  #   生死は「プロセスが居るか」ではなく「外から叩いて200が返るか」で見る。道は2本（relay_watch.py）。
  # 起動の間引き（2026-09-18）：元コメント「2分に1回見る」に合わせる（15秒×8=2分）
  tick_every 8 && ( python3 "$REPO/tools/relay_watch.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-05 使い終わった作業場(git worktree)を片づける。放っておくと51個溜まり、
  #   ChatGPT(Codex)がそれを1つずつ「プロジェクト」として拾ってたまごさんの画面を汚す。
  #   本流に入っていて・未保存の変更が無くて・2時間以上経ったものだけ消す（30分に1回）。
  # 起動の間引き（2026-09-18）：中で30分に間引いている。10分おきの起動で十分
  tick_every 40 && ( python3 "$REPO/tools/worktree_reaper.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-07（620番）：確認ページ(share/check)が上限も掃除も無いまま増え続けていた。
  #   60日以上さわられていないものだけ、店主が拾えるようゴミ箱へ退避する（6時間に1回でよい）。
  # 起動の間引き（2026-09-18）：中で6時間に間引いている
  tick_every 40 && ( python3 "$REPO/tools/check_page_pruner.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-07（626番）：support@anthropic.comへの問い合わせ返信を1日1回チェックする見張り。
  #   新しいlaunchd便は増やさず、既存の心臓に相乗り。実際にIMAPへ繋ぐのはスクリプト内部で
  #   1日1回に間引いている（それ以外の15秒ごとの呼び出しは即座に戻るだけで負荷ゼロに近い）。
  # 起動の間引き（2026-09-18）：中で1日1回に間引いている
  tick_every 40 && ( python3 "$REPO/tools/check_anthropic_reply.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-13（801番）：LINE Creators Market／スタンプメーカーへの問い合わせ返信を1日1回チェックする見張り。
  #   check_anthropic_reply.pyと全く同じ間引きパターンで既存の心臓に相乗り（新しいlaunchd便は増やさない）。
  # 起動の間引き（2026-09-18）：中で1日1回に間引いている
  tick_every 40 && ( python3 "$REPO/tools/check_line_reply.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-20（974番）：珍獣ラシコルの【審査結果】メールの見張り。801番と同じ相乗り方式。
  #   801番は「問い合わせの返信」用でDONEフラグを別に持つため、審査結果はこちらで別に見る。
  #   たまごさんが「すぐ」と言っているので、中の間引きだけ30分（IMAP接続は30分に1回）。
  tick_every 40 && ( python3 "$REPO/tools/check_line_shinsa.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-17（891番）：外部連絡窓口台帳(renraku_madoguchi.json)に登録した全窓口(LINE Creators
  #   Market・LINEスタンプメーカー・Lovable・Anthropic)への返信を毎日（朝・夜の2回想定）見張る。
  #   check_anthropic_reply.py/check_line_reply.pyと同じ間引きパターンで既存の心臓に相乗り
  #   （renraku.py内部でCHECK_INTERVAL_HOURSに間引くので、15秒ごとに呼んでも負荷は増えない）。
  #   新着・2週間未着・認証情報なしは status/dispatch_outbox.jsonl へ全文そのまま1回だけ通知する。
  # 起動の間引き（2026-09-18）：中でCHECK_INTERVAL_HOURSに間引いている
  tick_every 40 && ( python3 "$REPO/tools/renraku.py" check >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-11（756番）：毎朝の入荷見回り（707番）を手作業から自動へ。前日にjoy-relief-stationへ
  #   新規登録された動画を見回るタスクを、1日1回だけ発車待ちへ積む（check_anthropic_reply.pyと
  #   同じ間引きパターン。新しいlaunchd便は増やさない）。
  # 起動の間引き（2026-09-18）：中で1日1回に間引いている
  tick_every 40 && ( python3 "$REPO/tools/daily_ingest_scheduler.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-23（1036番）：税金ラインの係。Obsidianの#税金タグ・棚を1日1回拾って、
  #   e-Gov法令API／国会会議録API（どちらもキー不要・0円）で裏を取り、
  #   「裏取り待ち／裏が取れた／取れなかった」の3つの数字だけを status/uratori/counts.json へ。
  #   新しいlaunchd便は増やさない。中で1日1回に間引いている（daily_ingest_schedulerと同じ型）。
  #   ★Vaultにも外のAPIにも、サンドボックスからは届かない（実測 curl→000）。心臓はMacなので届く。
  tick_every 40 && ( python3 "$REPO/tools/zeikin_kakari.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-25（1140番）：ごきげん補給所の全26,400曲を、毎日1回まるごと機械で流し直す。
  #   実測（oEmbedで全動画IDを1件ずつ）→全曲検査→「再生できる動画が1本も無い」曲を
  #   表から外す表を作り直す→変わったぶんだけ main に1コミット。
  #   ★新しいlaunchd便は増やさない。中で1日1回に間引いている（daily_ingest_schedulerと同じ型）。
  #   ★サンドボックスからは youtube.com に回線が出ない（実測 curl→000）。心臓はMacなので届く。
  tick_every 40 && ( python3 "$REPO/tools/1140_mainichi.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  tick_every 41 && ( python3 "$REPO/tools/1141_mainichi.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1057番）：ごきげん補給所の「重さ」の見張り。たまごさんより先に気づく係。
  #   これまで重さは**人が思い出したときにだけ**測られていた＝「いつの間にか3MBに戻る」が
  #   何度でも起きる。1日1回、機械が測る。★赤（前回比+5%超／1MB超／CLS0.1超）のときだけ
  #   status/dispatch_outbox.jsonl へ1行書く。青の日は1行も出さない（黙っているのが正常の合図）。
  #   中で20時間に間引いているので10分おきに呼んでも測るのは1日1回。投げっぱなしで心臓は待たない。
  #   ★この係は測って判定して知らせるだけ。**直さない**（測った本人が直すと嘘を誰も見つけられない）。
  tick_every 40 && ( python3 "$REPO/tools/omosa_mihari.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-12（787番）：「いまの現在地」1枚(status/genzaichi.md/.json)を実質30分おきで更新する。
  #   憲法0番に「30分おき自動更新」と書いてあったのに実体（スケジューリング）が無かった穴を塞ぐ。
  #   新しいlaunchd常駐は増やさず、既存の心臓に相乗り。内部で1500秒ゲートしているので
  #   15秒ごとに呼んでも実際に本体が走るのは30分に1回だけ（daily_ingest_scheduler.pyと同じ間引き）。
  # 起動の間引き（2026-09-18）：中で1500秒(25分)に間引いている
  tick_every 8 && ( python3 "$REPO/tools/genzaichi.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-16（882番）：「今すぐ走っているもの」がgenzaichi.json（実質30分おき）だと
  #   古すぎて0本と誤表示することがあった。queue_light.jsonだけを読む軽い専用スクリプトを
  #   毎サイクル（15秒おき）回して status/top_status.json を常に生きた状態に保つ。
  ( python3 "$REPO/tools/top_status.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # ───────────────────────────────────────────────────────────────
  # 1142番（2026-09-25）ループを閉じる3本。**出す → 測る → 直す → また出す** の後ろ3つ。
  #   たまごさん「測るところが無いと全部ただの作業」「基本的に止まらないで回し続けて」
  #   ★新しい常駐(launchd)は1本も増やさない。既にある心臓に相乗りさせる（憲法：見張りを増やさない）
  #   順番が大事：測る(loop) → 直す(fukkyuu) → 次の周でまた測る。
  #   直す係が先に走ると「何を直すのか」が分からないので、必ずこの順で書く。
  tick_every 8  && ( python3 "$REPO/tools/1142_loop.py" --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  tick_every 40 && ( python3 "$REPO/tools/1142_fukkyuu.py" --honban >> "$REPO/status/1142_fukkyuu.log" 2>&1 & ) >/dev/null 2>&1
  # 1143番【成果の鮮度計（Freshness SLO）】2026-09-25
  #   「動いているのに成果が出ていない」を、走行本数ではなく**成果の年齢**で捕まえる。
  #   OneUptime の Freshness SLO ＋ Prefactor の presence チェックの移植。0円。
  #   ★ tick_every 8（約2分）＝ 1142_loop と同じ間隔。measure→alert なので loop の前に置く。
  tick_every 8  && ( python3 "$REPO/tools/1143_freshness.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 門の押しボタン（わざと不正な1件を流して、門が生きているか実測する）。中で6時間に間引く。
  tick_every 40 && ( python3 "$REPO/tools/1142_kanmon.py" >> "$REPO/status/1142_kanmon.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-16（894番）：発車0本の検知＋自己修復（tools/genzaichi.pyのcheck_launch_silence・
  #   797/798番実装）は、genzaichi.py本体が「実質30分おき」に間引かれているせいで、
  #   発車が10分止まっても最大約30分検知が遅れる穴があった。判定自体は軽量（ファイルの
  #   更新時刻とmachine.jsonを読むだけ）なので、ここで毎サイクル（15秒おき）直接呼ぶ。
  #   実装は tools/launch_watchdog.py（genzaichi.check_launch_silence()をそのまま再利用・
  #   二重実装はしない）。
  # 起動の間引き（2026-09-18）：発車0本の検知。30秒おきで十分（元は15秒）
  tick_every 2 && ( python3 "$REPO/tools/launch_watchdog.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-26（復元便）復活係。1分おき（tick_every 4 ＝ 15秒×4）。
  #   ★足しているのは2つだけ：①本物が0本だった時間を分で積算して日別に残す
  #   （status/fukkatsu.jsonl・status/zero_bon.json。空回しは走行に数えない）
  #   ②Claudeが使えない間、空回しの代わりに0円の本物工程を回す。
  #   目標本数(inochi.py)・0本検知(launch_watchdog.py)・固まった便の戻し(1142_fukkyuu.py)・
  #   順番(aitara_mawasu.py)は既にあるものを呼ぶだけ。二重実装しない。
  #   ★この係が落ちても心臓は次のtickでまた呼ぶ＝どのセッションにも依存しない。
  tick_every 4 && ( python3 "$REPO/tools/fukkatsu.py" >> "$REPO/status/fukkatsu.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-17（926番）：外部検品ゲート。status/kenpin/pending/ に積まれた依頼票を
  #   ChatGPT(OpenAI API)へ投げて判定を号番号(queue.json)へ戻す。5分便(machine_status_push.sh)にも
  #   同じ行があるが、その便はMacが重いと何十分も回ってこないことが実測されており（このログの
  #   「立て直しの便が◯分更新していません」）、検品の往復が止まると「未検品のものを
  #   たまごさんへ返さない」という仕組みそのものが死ぬ。検品待ちが空のときは
  #   ディレクトリを1回見るだけで即座に戻るので、15秒おきに呼んでも負荷はほぼゼロ。
  #   投げっぱなしにして心臓は待たない（他の相乗りと同じ形）。
  # 起動の間引き（2026-09-18）：検品の往復。30秒おきで十分（元は15秒）
  tick_every 2 && ( python3 "$REPO/tools/kenpin_gate.py" --run-pending --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-18（931番）：Claudeが作ったChromeタブの孤児を掃く（5分便にも同じ行がある。
  #   スクリプト内部で1時間ゲートしているので二重には走らない＝kenpin_gateと同じ相乗りの形）。
  #   Chromeが起動していなければ即座に戻るだけ。activateしない・前面タブは閉じない・
  #   たまごさんの作業タブは閉じない。
  # 起動の間引き（2026-09-19 更新）：中で**15分**に間引いている（元は1時間だった）。
  #   1時間だと、Chromeが起動していない回でもゲートを消費してしまい、Chromeが起きた直後の
  #   一番タブが溜まっている時間帯を素通りしていた（実測で証拠あり）。15分＋「掃いたときだけ
  #   ゲートを進める」に直した。
  tick_every 40 && ( python3 "$REPO/tools/chrome_tab_sweeper.py" --recon --sweep --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # ---- 1160番【タブ掃除係】2026-09-26：**外した。ここに足してはいけない。** ----
  #   一度ここに `python3 tools/1160_tab_souji.py` を足したが、中身が osascript（AppleScript）で
  #   Chrome/Brave/System Events を触る作りだったため、**たまごさんの画面にmacOSの許可ダイアログ
  #   （"python3" が "System Events" を制御…）を出してしまった。**同じ事故を1日に2回やった。
  #   → たまごさん指示：**AppleScript / System Events / TCC許可が要る手段は全面禁止。**
  #   タブを閉じるのは Chrome MCP（tabs_close_mcp）＝自分のタブグループの中だけ。
  #   グループ外には届かない。届かないものは「届かない」と書く（無理やりOSを触らない）。
  #   代わりの仕組み：status/1154_stop_kanmon.jsonl の完了条件に「自分が開いたタブが0枚」を足し、
  #   閉じずに終わろうとしたセッションの終了を拒否する（tools/1161_tab_kanmon.py）。
  # 2026-09-18（931番）：取り残された .git のロックが工場のgitを丸ごと止める事故への自己修復。
  #   Cowork（サンドボックス）側のセッションがgitの途中で打ち切られると index.lock が残り、
  #   以後 add/commit が全てrc=128で失敗する。しかもマウント越しにはunlinkできず本人が片付けられない。
  #   5分以上放置＋gitプロセスが1本も無い時だけ消す（worktree_reaper.pyと同じ立ち位置）。
  # 起動の間引き（2026-09-18）：5分以上放置のロックが対象。2分おきで十分
  tick_every 8 && ( python3 "$REPO/tools/git_lock_reaper.py" --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-19（Cowork側から設置）GitHubの見張り番。
  #   たまごさん「チャッピーがGitHubに上げたら、俺が言わなくても即座に気づくようにして。水汲みゼロ」
  #   実害：joy-relief-stationにIssueが置かれても、たまごさんが口で伝えるまで誰も気づかなかった。
  #   ★「5分ごとに全部見に行く」形ではない。ETag(If-None-Match)を付けた条件付きGETなので、
  #     変化が無い回は 304 が返るだけ＝**本文0バイト・レート制限の消費0**（公式ドキュメント記載）。
  #   ★中に60秒ゲートがあるので、呼ばれすぎても外へは出ない（状態ファイルを1つ読んで即戻る）。
  #     心臓の一周は混むと実測40〜50秒まで伸びるので、呼ぶ側は短い方(2周=約30〜100秒)に倒す。
  #   拾ったら status/queue.json の発車待ちへ自分で積む。着火は auto_launcher がやる＝人は押さない。
  #   ★吐き出したものは status/github_watch_err.log に残す（黙って死ぬのを防ぐ）。
  tick_every 2 && ( python3 "$REPO/tools/github_watch.py" >> "$REPO/status/github_watch_err.log" 2>&1 & ) >/dev/null 2>&1

  # 977番（2026-09-22）：外部AI台帳の回収係。
  #   見張り番（github_watch.py）はETagと基準線で「いま新しいもの」しか拾わない。
  #   タイミングが1秒ずれた回・上限に当たった回・トークンで寝ていた回の返事を取りこぼす。
  #   こちらは別の原理で動く＝「投げたのに返り0のスレッド」だけを名指しで読みに行く。
  #   ★赤が0件なら通信を1本も出さずに終わる（--gated）。工場は重くならない。
  tick_every 2 && ( python3 "$REPO/tools/ai_daicho.py" --collect --gated >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-18（944番）：外部AI（Grok/ChatGPT/Gemini）への代行係。
  #   Cowork/Dispatchのサンドボックスからは api.openai.com / api.x.ai /
  #   generativelanguage.googleapis.com へ回線が出ない（実測）。このMacからは出る。
  #   向こうは status/gaibu_jobs/pending/ に仕事票を置くだけで、実際に叩くのはここ。
  #   ★5分便(machine_status_push.sh)にも同じ行があるが、その便は実測で25分以上止まることが
  #     あるため（今日07:24〜）、kenpin_gateと同じく心臓側にも置いて二重化する。
  #     待ちが空ならディレクトリを1回見るだけで即座に戻るので、15秒おきでも負荷はほぼゼロ。
  # 起動の間引き（2026-09-18）：外部AI代行。30秒おきで十分（元は15秒）
  tick_every 2 && ( python3 "$REPO/tools/gaibu_runner.py" --quiet >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-18（Cowork側から設置）機械の健康診断＋工場が撒いた残骸の回収。
  #   5分便にも sales-watch便にも同じ1行がある（＝経路の三重化）。本体が2分で
  #   間引くので、15秒おきに呼んでも実際に測るのは2分に1回だけ＝負荷は増えない。
  #   kenpin_gate等と同じ「投げっぱなしにして心臓は待たない」形。
  # 起動の間引き（2026-09-18）：本体が2分で間引いている
  tick_every 8 && ( python3 "$REPO/tools/machine_health.py" --reap >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-21（840番）毎週のMac掃除。5分便(machine_status_push.sh)にも同じ1行がある＝経路の二重化。
  #   なぜここへ移したか（実測）：定期タスク weekly-mac-maintenance は毎週走ってはいたが、
  #   定期実行のスコープでは許可ダイアログを押す人が居ないので、Macの実ファイルに一度も
  #   届いていなかった（毎回「何も実行できなかった」＋毎回たまごさんに質問）。
  #   ★動いているのに何も取れていない、が一番たちの悪い壊れ方。
  #   → 許可の要る経路をやめて、許可の要らない工場側（心臓とこの5分便）に寄せる。
  #     新しい定期タスク・新しいlaunchd便は作らない。
  #   ★中で**週1**に間引いている（status/.mac_souji_at）。10分おきに呼んでも実走は週1回。
  #     掃く判定は tools/disk_guardian.py の既存ロジックをそのまま使う（二重実装しない）。
  #     Brave・たまごさんのアプリ・作り直せないものには一切触らない。
  #   ★走った回数と実際に片付いたバイト数の両方を status/mac_souji.json に残し、
  #     「走行>0 なのに 片付き=0」は赤で出す。投げっぱなしにして心臓は待たない。
  tick_every 40 && ( python3 "$REPO/tools/mac_souji.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-22 鬼監督の口。やり残しを自分で見つけて、1日1本だけ言い出す。
  #   たまごさん「俺が言わなくても仕事が進むようにしてほしい。
  #              『これできてないからここ進めよう』だとか、そこも半自動化したい」
  #   中で1日1回に間引く（status/.oni_kuchi_last）ので、ここは緩く呼べばよい。
  #   AIを1回も呼ばないので、何度呼んでもクレジットは0円。定期タスクも新しい常駐も作らない。
  tick_every 240 && ( python3 "$REPO/tools/oni_kuchi.py" >> "$REPO/status/oni_kuchi.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-23（1042番）投げ込み箱の一覧。たまごさん「何が入ってきたかわかるようにしといて」
  #   status/nagekomi.jsonl（非公開）から**出してよい列だけ**を写して
  #   status/nagekomi_list.json（中継所が配る生）と status/public/nagekomi_list.json（公開）へ。
  #   台帳を1本読んでJSONを1枚書くだけ＝1秒かからない。新しい常駐は増やさない。
  tick_every 2 && ( python3 "$REPO/tools/nagekomi_list.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-26（1163番）棚に書ける鍵（~/.tamago/supabase_service_role）が置かれた**その周回で**、
  #   たまごさんがコマンドを1つも打たずに、溜まっている分を全部棚へ入れる。
  #   鍵が無い周回は os.path.exists を1回見て即座に戻るだけ＝心臓は重くならない。
  #   鍵の値はログにもJSONにも1バイトも書かない。AIを呼ばないのでクレジットは0円。
  tick_every 2 && ( python3 "$REPO/tools/1163_kagi_machi.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1050番）外の働き手の紙。たまごさん「役に立ってるなら使うし、役に立ってないならいらない」
  #   ★この問いは何度も出ているのに、毎回その場の報告で消えていた。だから紙を1枚だけ持たせて、
  #     そこが毎日勝手に書き換わる形にする。新しい常駐も定期タスクも作らない（心臓に相乗り）。
  #   中で1日1回に間引く（status/.soto_hatarakite_at）ので、ここは緩く呼べばよい。
  #   AIを1回も呼ばない・外へ1回も出ない＝クレジット0円。投げっぱなしにして心臓は待たない。
  tick_every 240 && ( python3 "$REPO/tools/soto_hatarakite.py" >> "$REPO/status/soto_hatarakite.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1059番）サブスクのお知らせ係。たまごさん「全てのサブスク、3日ぐらい前から
  #   アナウンスして。もう更新が迫ってるって。3日連続お知らせしてくださいね」
  #   ★更新日の3日前・2日前・前日に、status/dispatch_outbox.jsonl へ**1行だけ**積む。
  #     更新日を過ぎたら止まる。同じ日に2回は言わない（status/subsc_shirase_sent.json）。
  #   ★お金の紙(1051番)より先に呼ぶ＝紙は書き直された数字を写すだけ。新しい常駐も定期タスクも作らない。
  #   中で1日1回に間引く（status/.subsc_shirase_at）。外へ出るのは為替レート1本だけ＝0円。
  tick_every 240 && ( python3 "$REPO/tools/subsc_shirase.py" >> "$REPO/status/subsc_shirase.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1051番）お金の紙。たまごさん「シンプルに月々いくらかかってるかを目視で確認できるようにしたい」
  #   ★お金の紙は1枚だけ。中で1日1回に間引く（status/.okane_ichimai_at）。AIを呼ばない・外へ出ない＝0円。
  tick_every 240 && ( python3 "$REPO/tools/okane_ichimai.py" >> "$REPO/status/okane_ichimai.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1052番）たまごさんの確認待ちの紙。たまごさん「俺の確認待ちもいっぱいあるのかもしれない。
  #   なんか今出してよ。優先順位つけるから」「多くても10行」
  #   ★たまごさんにしか押せないもの（鍵・本人確認・金銭・取り消せない公開）だけを載せる。
  #   こちらで進められるものを載せた時点でこの紙の負け。中で1日1回に間引く（status/.kakunin_machi_at）。
  tick_every 240 && ( python3 "$REPO/tools/kakunin_machi.py" >> "$REPO/status/kakunin_machi.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1065番）適材適所の紙。たまごさん「仕事できないやつを切り捨てるって簡単なんだよ。
  #   それをうまく役立たせるって方が難しいと思うよ」＝★切る前に、得意な形の仕事を当てる側の紙。
  #   お金は1050番の結果をそのまま写すだけで、ここでは計算し直さない（数字を2本持たない）。
  #   中で1日1回に間引く（status/.tekizai_at）。AIを呼ばない・外へ出ない＝0円。新しい常駐は作らない。
  tick_every 240 && ( python3 "$REPO/tools/tekizai.py" >> "$REPO/status/tekizai.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1066番）配管図。たまごさん「テキストでわーって言われてもわかんねぇわ。配管図みたいな」
  #   ★kaitsuu.json（実測）と tekizai.json（実測）だけを読んで図を描き換える。
  #   ★叩いて通ったものだけ緑。実測の無い線は描かない。AIを呼ばない・外へ出ない＝0円。
  #   中で1日1回に間引く（status/.haikanzu_at）。新しい常駐は作らない。
  tick_every 240 && ( python3 "$REPO/tools/haikanzu.py" >> "$REPO/status/haikanzu.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1058番）Gensparkへ自動で流す配管。たまごさん「俺が水汲みをやらないと動かせない」
  #   ★サンドボックスからは gsk に手が届かない（実測）。Macで常に動いているのはこの心臓だけ。
  #   ★番号が選ばれていないあいだは、ファイルを1枚読んで即戻る＝**通信0・クレジット0**。
  #     選ばれて初めて流れ始める。中で60秒に間引く＋1日の上限（10/4までの日割り）で止まる。
  #   投げっぱなしにして心臓は待たない。新しい常駐も定期タスクも作らない。
  tick_every 4 && ( python3 "$REPO/tools/genspark_nagashi.py" --quiet >> "$REPO/status/gsk/nagashi.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-25（1142番）外の口へ仕入れを1本ずつ絶やさず流す係。たまごさん「デビンは仕入れ含め止まらず回して」
  #   ★サンドボックスからは api.devin.ai / api.github.com に回線が出ない（実測403）。Macのここだけが叩ける。
  #   ★1本ずつ（3本同時は2026-09-20にACUが尽きて3本とも凍った）。走っている1本があれば見るだけで戻る。
  #   ★お金：財布の栓（yosan devin）が0円なら Devinには1本も投げない。列は0円の口（Jules）で回す。
  #   投げっぱなしにして心臓は待たない。新しい常駐も定期タスクも作らない。
  tick_every 4 && ( python3 "$REPO/tools/1142_nagashi.py" >> "$REPO/status/1142/nagashi.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1074番）秋の投稿・今日の1本。たまごさん「たまごさんがやるのはOKかこれじゃないかだけ」
  #   ★朝07:00と夜20:30に、ドラフトを1本だけ出す（投稿の30分前）。文面はこちらが書いてある。
  #   ★中で1便1回に間引く（status/aki_toko.json の lastKey）ので、ここは緩く呼べばよい。
  #   ★在庫28本を使い切っても止まらない。次の周に入って出し続ける。
  #   AIを1回も呼ばない・外へ1回も出ない＝0円。新しい常駐も定期タスクも作らない。
  tick_every 8 && ( python3 "$REPO/tools/aki_toko.py" >> "$REPO/status/aki_toko.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1080番）空いたら勝手に回す。たまごさん
  #   「こういうのがあるのに工場が止まってるなんてありえないんだよ。
  #     仕入れるなり間違いを探すなり、何かしらやっててくださいよ。」
  #   ★キューが空でも止まらない。順番の正本は tools/aitara_mawasu.py の JUNBAN。
  #   ★0円の工程（間違い探し・メイン不在の門）だけをここから回す。課金する工程はキュー経由。
  #   ★Gensparkの栓（status/genspark.stop）が在るあいだ、覆面テストは順番から外れる。
  #   AIを呼ばない・外へ出ない＝0円。新しい常駐も定期タスクも作らない。
  tick_every 20 && ( python3 "$REPO/tools/aitara_mawasu.py" >> "$REPO/status/aitara_mawasu.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1080番）メイン不在の門。たまごさん
  #   「タイトルがあるのにメインのものがないだとか、そういうのはもうゼロにして。あり得ないから。」
  #   ★本番のcoverGuide.tsを数え直して status/main_kanmon.json に書くだけ。書き換えない＝0円。
  tick_every 60 && ( python3 "$REPO/tools/main_kanmon.py" --jissoku >> "$REPO/status/main_kanmon.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-24（1082番）戻せる台帳。たまごさん
  #   「間違えて変えてしまうものもあるかもしれないけれど、すぐ戻れるようにしといてね。」
  #   ★戻れる点（anzen-* の印）を作り直して、全部が戻せる状態かを実測する。
  #   ★git の印を作るだけ。作業ツリーにも index にも触らない＝0円・0リスク。
  tick_every 40 && ( python3 "$REPO/tools/modoseru.py" --shiraberu >> "$REPO/status/modoseru.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-25（1138番）宿題台帳。たまごさん
  #   「俺が言ったのに返ってきてないことがたくさんある。それが自動で走ってゼロになるようにやってほしい。」
  #   ★発車待ち・引き継ぎ58本・工場の申し送りを1本の台帳に集め直し、まだ列に居ないものを
  #     発車待ちへ積む。残り件数を毎日数えて、減っていなければ赤。
  #   ★中で1日1回に間引く（status/.shukudai_at）。AIを呼ばない・外へ出ない＝0円。
  tick_every 240 && ( python3 "$REPO/tools/shukudai.py" --hima >> "$REPO/status/shukudai.log" 2>&1 & ) >/dev/null 2>&1
  # 2026-09-25（1138番）配分。「いま何本走らせてよいか」と「余らせていないか」を1か所で答える。
  #   ★本数の計算は pace.py のまま。ここは天井までの余裕・朝の余りの赤・空き枠放置の実測だけ。
  #   ★安いので10分おき。AIを呼ばない・外へ出ない＝0円。
  tick_every 40 && ( python3 "$REPO/tools/haibun.py" >> "$REPO/status/haibun.log" 2>&1 & ) >/dev/null 2>&1
  # ══ 2026-09-26（1152番）「言われなくても動く」を機械にする5点セット ══
  #   たまごさん「俺に言われて動き出すのはもうダメだよ、30点。仕組みは作ってるの？」
  #             「何回も同じこと言うのってエネルギー使う。早く仕組みにしてくれ。」
  #             「忘れられない、もう逃げられない仕組みにしてよ。」
  #   ★5つとも0円（AIを呼ばない・外へ出ない）。新しい常駐は tomaranai の launchd 1本だけ。
  #
  # ① 拾う：たまごさんの発言を会話ログから自動で抜いて、言われた回数を数える。
  #    ★手で写さない。写し忘れた瞬間に消えていたのが「言ったのにやってない」の正体。
  #    読んだ位置を status/kioku/.seen.json に残すので、落ちても続きから。
  tick_every 8  && ( python3 "$REPO/tools/kioku.py" >> "$REPO/status/kioku/kioku.log" 2>&1 & ) >/dev/null 2>&1
  # ② 判定日：1週間後・1ヶ月後が来たら機械が状態を見に行く。
  #    ★変わっていなければ自動で赤＋P1に繰り上げて、その場で再発車する。
  #      うやむやを構造的に不可能にするのがここ。人の許可を要らなくしてある。
  tick_every 40 && ( python3 "$REPO/tools/hantei.py" >> "$REPO/status/kioku/hantei.log" 2>&1 & ) >/dev/null 2>&1
  # ③ 鬼監督（差し戻し係）：自己申告の完了を受け付けない。
  #    URLを叩いて200・中身が空でない・過去の指摘に引っかからない、を機械が確かめる。
  #    ★落ちたら自動で同じ案件を再発車（回数制限なし・上限は14日だけ）。
  tick_every 20 && ( python3 "$REPO/tools/oni_modoshi.py" >> "$REPO/status/oni_modoshi/run.log" 2>&1 & ) >/dev/null 2>&1
  # ④ 外の審査：台帳と実測を Genspark／Codex／公開リポ ai-kaigi に出して監査させ、
  #    返ってきた指摘を台帳へ戻す。★完了の鍵（status/gaibu/soto_hantei.json）は外しか開けない。
  #    中で1日1回に間引く。出すのは tools/nageru.py の口1本だけ＝新しい通信を作らない。
  tick_every 240 && ( python3 "$REPO/tools/gaibu_shinsa.py" >> "$REPO/status/gaibu/shinsa.log" 2>&1 & ) >/dev/null 2>&1
  # ⑤ 紙を1枚だけ書き直す（リポ直下 1152-nankai.html／スマホで開ける）。
  #    ★一番上に出すのは 今週言われた件数／実際に変わった件数／達成率。走らせた本数は出さない。
  tick_every 8  && ( python3 "$REPO/tools/kioku_page.py" >> "$REPO/status/kioku/page.log" 2>&1 & ) >/dev/null 2>&1
  # ⑥ 止まらない係：走行0本を検知したら聞かずに台帳の上から自分で発車する。
  #    launchd（1分おき）が正本。心臓からも呼んでおくのは、launchd が落ちても死なせないため。
  #    中で5分に1回に間引くので、二重に呼んでも二重に積まない。
  tick_every 4  && ( python3 "$REPO/tools/tomaranai.py" >> "$REPO/status/tomaranai.log" 2>&1 & ) >/dev/null 2>&1
  #    launchd への登録は冪等。既に入っていれば何もしないので、毎周呼んで構わない。
  #    ★たまごさんに手で流させない。登録そのものを機械にやらせる。
  tick_every 40 && ( bash "$REPO/tools/tomaranai_install.sh" >> "$REPO/status/tomaranai.log" 2>&1 & ) >/dev/null 2>&1

  # ログが太らないように、たまに刈る
  if [ "$(( $(date +%s) % 3600 ))" -lt 20 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
    echo "$(date '+%F %T') 心臓は動いています" >> "$LOG"
  fi
  # ---- 2026-09-22（1018番）1周を最後まで回りきった事実だけをここに書く ----
  # 鼓動(.heartbeat_alive)＝シェルが生きている。これ(.heartbeat_progress)＝1周が終わった。
  # 本当に固まった時だけ、こちらが古くなる。見張りはこの2つを別々に見る。
  # 中身に1周の所要秒数を残す＝「見張りの閾値が実測と合っているか」を後から数字で言える。
  echo "$(date '+%F %T') cycle_secs=$(( $(date +%s) - CYCLE_STARTED_AT ))" > "$PROGRESS_F" 2>/dev/null || true
  sleep 15
done
