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
python3 "$REPO/tools/quota_estimate.py" --quiet >/dev/null 2>&1 || true
# 2026-09-02 見張り番：止まっている子セッションを検知して claude -p --resume で自動再開（判定は factory_status の分類。負荷ゲートあり）
# 2026-09-03 14:45 たまごさん「もう止めて」により無効化。計測(factory_status.py)とPWAへのpushは継続、自動再開だけ止める
# python3 "$REPO/tools/session_watchdog.py" >/dev/null 2>&1 || true
# 2026-09-03 孤児プロセス回収：セッション終了後もppid=1で残り続けるlint/build/test系の暴走プロセスを止める（ロード100%固定化の実害を確認して追加）
python3 "$REPO/tools/orphan_reaper.py" >/dev/null 2>&1 || true
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
for f in status/history.jsonl status/whiteboard.json status/priority.json status/health.json status/commands.json; do
  [ -f "$f" ] || continue
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || HIST_CHANGED=1
  git diff --quiet -- "$f" 2>/dev/null || HIST_CHANGED=1
done
if [ "$PREV" = "$CURR" ] && [ "$AGE" -lt 1200 ] && [ "$HIST_CHANGED" -eq 0 ]; then return 0; fi

git add status/machine.json status/history.jsonl status/whiteboard.json status/priority.json status/health.json status/commands.json >/dev/null 2>&1
git -c user.name="machine-status" -c user.email="machine-status@local" commit -q -m "status: Mac負荷 $(date +%H:%M)" >/dev/null 2>&1 || return 0
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
