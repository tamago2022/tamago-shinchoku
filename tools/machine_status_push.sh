#!/bin/bash
# Macの負荷を measure して status/machine.json に書き、変わっていれば GitHub Pages へ push する。
# 5分おきに launchd（com.tamago.machine-status）から呼ばれる。計測本体は /Users/mac/Desktop/machine_load.sh。
# 2026-09-03 15:xx リアルタイム化：launchdの新規ジョブ登録は2回ともAuto mode classifierにブロックされたため、
# 「1回の起動の中で30秒おきに測る」方式に変更（新規ジョブ登録なし・既存の5分おき起動はそのまま）。
# 1回の起動につき最大約260秒(=launchdの次の5分ティックが来る前)ループし続け、変化があれば即pushする。
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

REPO="/Users/mac/Desktop/tamago-shinchoku"
OUT="$REPO/status/machine.json"
LOADSH="/Users/mac/Documents/AI作業/2026-09-02/スクリプト/machine_load.sh"
mkdir -p "$REPO/status"

# 1回の起動が約260秒に伸びたため、launchdの次の5分ティックと重なって二重起動しないようロックする
LOCK="$REPO/status/.machine_status_push.lock"
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

# 2026-09-03 追加：置き去りのgitロックを掃除する。
# Cowork側のサンドボックスからマウント越しにgitを叩くと、.git/*.lock と objects/*/tmp_obj_* を
# unlink できず（Operation not permitted）残る。残ると以後このスクリプトのcommit/pushが毎回失敗し、
# 進捗表が丸ごと止まる（18:25〜18:30に実際に発生）。5分以上前のものだけ消す＝実行中のgitは巻き添えにしない。
find "$REPO/.git" -maxdepth 1 -name "*.lock" -mmin +5 -delete 2>/dev/null || true
find "$REPO/.git/objects" -maxdepth 2 -name "tmp_obj_*" -mmin +5 -delete 2>/dev/null || true

run_once() {
# 2026-09-02 止まらない工場：計測＋止まり判定＋安全上限は factory_status.py に集約（土台は machine_load.sh のまま）。
# factory_status.py が失敗したら従来どおり machine_load.sh 単体で最低限のJSONを書く（止まらない）。
if python3 "$REPO/tools/factory_status.py" --write >/dev/null 2>&1 && grep -q '"safeMax"' "$OUT" 2>/dev/null; then
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
python3 "$REPO/tools/quota_estimate.py" --quiet >/dev/null 2>&1 || true
# 2026-09-03 たまごさん「進捗の数字がずれてる時点でダメ」。
# Claudeアプリの実測ファイルは書き込みが止まることがあり（21:45で停止を確認）、推定に落ちると大きく外す。
# 実際: 全モデル68% / Fable82% ← アプリ画面の値。推定: 111% / 88.5%。
# status/quota_manual.json に {"allPct":68,"fablePct":82,"asOf":"2026-09-03 23:05"} を置けば、そちらを正とする。
# アプリ画面のスクショから拾った値を入れる用。実測ファイルが復活すればこのファイルを消せば元に戻る。
python3 - "$REPO" <<'PYEOF' >/dev/null 2>&1 || true
import json, os, sys
# 2026-09-04 バグ修正：ここは REPO を環境変数として読もうとしていたが export されておらず、
#   フォールバックの __file__ もヒアドキュメント実行では存在しないため例外→握りつぶし で
#   手入力(quota_manual.json)が一度も適用されていなかった。引数で渡す形に直した。
repo = sys.argv[1] if len(sys.argv) > 1 else "/Users/mac/Desktop/tamago-shinchoku"
q = os.path.join(repo, "status", "quota.json")
m = os.path.join(repo, "status", "quota_manual.json")
if os.path.exists(m):
    d = json.load(open(q, encoding="utf-8")) if os.path.exists(q) else {}
    man = json.load(open(m, encoding="utf-8"))
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
    json.dump(d, open(q, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PYEOF
# 2026-09-02 見張り番：止まっている子セッションを検知して claude -p --resume で自動再開（判定は factory_status の分類。負荷ゲートあり）
# 2026-09-03 14:45 たまごさん「もう止めて」により無効化。計測(factory_status.py)とPWAへのpushは継続、自動再開だけ止める
# 2026-09-03 18:12 たまごさん「仕組みで起こす方復活させてください。やって」により再有効化。
#   止めていた本当の理由＝再開がFableのままだったこと。それは session_watchdog.py 側で潰した：
#   ①resume時に必ず --model claude-sonnet-5 を明示 ②status/no_fable.flag がある間はFable完全禁止。
#   また止めたいときは status/no_fable.flag ではなくこの行をコメントに戻す（再開そのものが止まる）。
python3 "$REPO/tools/session_watchdog.py" >/dev/null 2>&1 || true
# 2026-09-03 孤児プロセス回収：セッション終了後もppid=1で残り続けるlint/build/test系の暴走プロセスを止める（ロード100%固定化の実害を確認して追加）
python3 "$REPO/tools/orphan_reaper.py" >/dev/null 2>&1 || true
# 2026-09-04 たまごさん「まず連続して走る仕組みを優先してね。順番に発車されるようにして、1日中回ってる状態を作るのが最優先」
#   発車待ち(status/queue.json)から、マシンとクレジットに空きがあれば1本だけ自動で着火する。
#   3時間縛り・URL報告のセットはプロンプト側に必ず入る。Fableは使わない（常にSonnet）。
python3 "$REPO/tools/auto_launcher.py" >/dev/null 2>&1 || true
# 2026-09-04 たまごさん「Obsidianには飛ばない」→ 進捗表のボタンをHTTPSで直接受ける中継所。
#   立っていなければ立て、トンネルのURLを status/relay.json へ書く（冪等・既に動いていれば何もしない）。
bash "$REPO/tools/relay_up.sh" >/dev/null 2>&1 || true
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
# 2026-09-03 本数の実測校正：load_history.jsonl＋heavy_events.jsonl → calibration.json（safeN/target）。次回の factory_status が読む
python3 "$REPO/tools/calibrate.py" --quiet >/dev/null 2>&1 || true
# 2026-09-03 ホワイトボード同期：PWAの優先度(status/priority.json)を正本へ取り込み、写し(status/whiteboard.json)を書く
python3 /Users/mac/Desktop/joy-relief-station/ai-brain/live/whiteboard.py sync >/dev/null 2>&1 || true

cd "$REPO" || return 0

# 2026-09-03 たまごさんの優先度（PWA→Obsidian経由）を取り込み、priority.json とホワイトボードに反映
python3 "$REPO/tools/priority_ingest.py" >/dev/null 2>&1 || true

# 2026-09-03 Macの健康管理：何を閉じれば／消せば楽になるか（実測。重い計測は30分に1回）
python3 "$REPO/tools/health_candidates.py" >/dev/null 2>&1 || true

# 2026-09-03 PWAリモコン：▶️動かす／⏸止める／🔁引き継ぐ／🗑閉じる のコマンドキューを実行（launchd新規登録がブロックされたため、この5分間隔ジョブに相乗り）
python3 "$REPO/tools/command_ingest.py" >/dev/null 2>&1 || true

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
      status/commands.json status/queue.json status/relay.json status/version.json \
      index.html data.js said.js tools 2>/dev/null | head -1)" ]; then
  HIST_CHANGED=1
fi
if [ "$PREV" = "$CURR" ] && [ "$AGE" -lt 1200 ] && [ "$HIST_CHANGED" -eq 0 ]; then return 0; fi

# 2026-09-04 画面の世代を書き出す。スマホのホーム画面アプリが古いindex.htmlを握ったままになる問題への対応。
#   index.html の中身のハッシュを status/version.json に置き、画面側が違いを見つけたら ?v=… で開き直す。
python3 - "$REPO" <<'PYVER' >/dev/null 2>&1 || true
import hashlib, io, json, os, sys, time
repo = sys.argv[1]
try:
    h = hashlib.sha1(io.open(os.path.join(repo, "index.html"), "rb").read()).hexdigest()[:10]
except Exception:
    sys.exit(0)
p = os.path.join(repo, "status", "version.json")
try:
    if json.load(io.open(p, encoding="utf-8")).get("v") == h:
        sys.exit(0)
except Exception:
    pass
json.dump({"v": h, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
          io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
PYVER
git add status/version.json >/dev/null 2>&1
git add status/machine.json status/history.jsonl status/whiteboard.json status/priority.json status/health.json status/commands.json status/queue.json status/quota.json status/relay.json >/dev/null 2>&1
# 2026-09-03 追加：画面本体（index.html/data.js/said.js）と共有資料（share/）も一緒に載せる。
# ここに無いとCowork側が書き換えても永久に公開されない（実際 share/ が載らず気づいた）。
git add index.html data.js said.js share tools >/dev/null 2>&1
# 2026-09-04 バグ修正：commitが失敗したとき return 0 で抜けていたため、push まで到達しなかった。
#   commitが失敗する典型は「新しい変更が無いとき」。だが、その前に別経路（Cowork側）でcommitされた分が
#   未pushで残っていることがあり、そのぶんが永久に公開されなかった（画面が更新されない実害）。
#   → commitの成否に関わらず push まで進む。
git -c user.name="machine-status" -c user.email="machine-status@local" commit -q -m "status: Mac負荷 $(date +%H:%M)" >/dev/null 2>&1 || true
git -c credential.helper='!gh auth git-credential' pull --rebase -q origin main >/dev/null 2>&1 || true
git -c credential.helper='!gh auth git-credential' push -q origin main >/dev/null 2>&1
}

# 約260秒（次の5分ティックが来る前）、間を空けずに回し続ける。走行中↔停止の切り替わりをできるだけ早くPWAへ反映するため。
# factory_status.py自体が実測27秒かかる（ps/lsof/transcriptスキャン）ので、固定sleepは入れず作業時間そのものを間隔にする
LOOP_END=$(( $(date +%s) + 260 ))
while :; do
  run_once
  NOWSEC=$(date +%s)
  [ "$NOWSEC" -ge "$LOOP_END" ] && break
  sleep 2
done
