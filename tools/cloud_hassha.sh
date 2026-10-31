#!/bin/bash
# クラウドセッション（Claude Code on the web）を1本起動する。クレジットが減るのはこの道（本物のクラウドセッション）だけ。
#   Anthropic サポート回答（2026-10-22）：クレジットはクラウドセッション（Web・デスクトップ・CLI・スマホ）だけに使われる。
#   チャット・Cowork・Dispatch・ルーティン（RemoteTrigger）・リモートコントロールでは減らない。
#   新規作成は `claude --cloud "説明"`（対話専用。`-p` との併用は「--cloud cannot be combined with --print」で不可＝10-22実測）。疑似端末 script で起動して切り離す。
#   既存セッションへの追加の指示だけ `claude -p "…" --cloud <session-id>`。期限 11/5 16:59 JST は延長不可。残高APIなし。
# 使い方（Mac で。子セッションからは status/mac_jobs/pending/*.sh に1行書く）：
#   bash tools/cloud_hassha.sh <便の名前> tools/cloud_prompts/<依頼文>.md
#   → ~/tamago/jrs_fix（joy-relief-station main の写し）で、共通の作法(_kyoutsu.md)＋依頼文を `claude -p … --cloud` に渡し、
#     切り離して起動（nohup）。出力は status/cloud_credit/log/<名前>.log。URL の回収・台帳・Dispatch への1行は
#     python3 tools/cloud_kaishuu.py（心臓 or 子が呼ぶ）。
# 承認待ちで止まらないのは joy-relief-station の .claude/hooks/cloud-no-wait.mjs（PR #1038）。
export PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH
NAME="$1"; PF="$2"
F=/Users/mac/tamago/tamago-shinchoku
J=/Users/mac/tamago/jrs_fix
[ -f "$PF" ] || PF="$F/$PF"
[ -f "$PF" ] || { echo "依頼文が無い: $2"; exit 1; }
git -C "$J" pull -q --rebase origin main >/dev/null 2>&1
mkdir -p "$F/status/cloud_credit/log"
LOG="$F/status/cloud_credit/log/$NAME.log"
PROMPT="$(cat "$F/tools/cloud_prompts/_kyoutsu.md")

$(cat "$PF")"
# クラウドの作成には claude.ai の本物のログインが要る（工場の setup-token は 403）。tools/cloud_login.sh で作った置き場を使う。
# CFG=main なら工場の ~/.claude のログインを使う（たまごさんが本物のログインをしたとき）
if [ "${CFG:-cloud}" = "main" ]; then CJ=$HOME/.claude.json; else export CLAUDE_CONFIG_DIR=$HOME/.tamago/claude_cloud; CJ=$CLAUDE_CONFIG_DIR/.claude.json; fi
export CJ
python3 - <<'PY'
import json, os
p = os.environ["CJ"]
d = json.load(open(p)) if os.path.exists(p) else {}
d.setdefault("projects", {}).setdefault("/Users/mac/tamago/jrs_fix", {})["hasTrustDialogAccepted"] = True
d["hasCompletedOnboarding"] = True if "tamago/claude_cloud" in p else d.get("hasCompletedOnboarding", True)
json.dump(d, open(p, "w"), indent=2)
PY
fi_dummy=1
cd "$J"
{ echo "== $(date '+%F %T') 起動 $NAME ($PF) MODE=${MODE:-s}"; } > "$LOG"
if [ "${MODE:-s}" = "p" ]; then
  nohup claude -p "$PROMPT" --cloud >>"$LOG" 2>&1 </dev/null &
else
  nohup script -q /dev/null claude --cloud "$PROMPT" >>"$LOG" 2>&1 </dev/null &
fi
echo "pid $!" >> "$LOG"; disown
sleep 40
LC_ALL=C sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' "$LOG" | tail -c 3000
