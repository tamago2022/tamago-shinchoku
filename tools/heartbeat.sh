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

echo "$(date '+%F %T') 心臓を起動しました（pid $$）" >> "$LOG"
while :; do
  TICK=$(( (TICK + 1) % 40 ))   # 15秒 × 40 = 10分で一周
  # 2026-09-16：詰まり判定を auto_launch.log の更新（=実際に発車/回収があった時だけ書かれる）
  # に頼っていたため、「走行0本で書くことが無いだけ」でも詰まっていると誤判定し、
  # machine_status_push.sh が正常な心臓を何度も殺して立て直す事故が起きた
  # （殺した拍子に子の auto_launcher.py が孤児化してロックを握ったまま残り、発車が止まった）。
  # ループが回っている事実そのものを、何もしなくても毎周期touchするこのファイルで示す。
  touch "$REPO/status/.heartbeat_alive" 2>/dev/null || true
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
  MJ="$REPO/status/machine.json"
  if [ -f "$MJ" ]; then
    MJ_AGE=$(( $(date +%s) - $(stat -f %m "$MJ" 2>/dev/null || echo 0) ))
    if [ "$MJ_AGE" -gt 900 ]; then
      echo "$(date '+%F %T') 🚨 立て直しの便（machine_status_push.sh）が${MJ_AGE}秒（約$(( MJ_AGE / 60 ))分）更新していません。launchdへ蹴り直しを試みます" >> "$LOG"
      launchctl kickstart -k "gui/$(id -u)/com.tamago.machine-status" >> "$LOG" 2>&1 || true
    fi
  fi
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
  # 2026-09-16（894番）：発車0本の検知＋自己修復（tools/genzaichi.pyのcheck_launch_silence・
  #   797/798番実装）は、genzaichi.py本体が「実質30分おき」に間引かれているせいで、
  #   発車が10分止まっても最大約30分検知が遅れる穴があった。判定自体は軽量（ファイルの
  #   更新時刻とmachine.jsonを読むだけ）なので、ここで毎サイクル（15秒おき）直接呼ぶ。
  #   実装は tools/launch_watchdog.py（genzaichi.check_launch_silence()をそのまま再利用・
  #   二重実装はしない）。
  # 起動の間引き（2026-09-18）：発車0本の検知。30秒おきで十分（元は15秒）
  tick_every 2 && ( python3 "$REPO/tools/launch_watchdog.py" >/dev/null 2>&1 & ) >/dev/null 2>&1
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
  # ログが太らないように、たまに刈る
  if [ "$(( $(date +%s) % 3600 ))" -lt 20 ]; then
    tail -n 200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
    echo "$(date '+%F %T') 心臓は動いています" >> "$LOG"
  fi
  sleep 15
done
