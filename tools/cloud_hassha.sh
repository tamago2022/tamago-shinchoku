#!/bin/bash
# クラウドセッション（Claude Code on the web）を1本起動する。クレジットが減るのはこの道（本物のクラウドセッション）だけ。
#   Anthropic サポート回答（2026-10-22）：クレジットはクラウドセッション（Web・デスクトップ・CLI・スマホ）だけに使われる。
#   チャット・Cowork・Dispatch・ルーティン（RemoteTrigger）・リモートコントロールでは減らない。
#   無人の起動は `claude -p "指示" --cloud`（今のリポジトリのクラウドセッションが作られる）。期限 11/5 16:59 JST は延長不可。残高APIなし。
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
cd "$J"
{ echo "== $(date '+%F %T') 起動 $NAME ($PF) MODE=${MODE:-p}"; } > "$LOG"
if [ "${MODE:-p}" = "p" ]; then
  nohup claude -p "$PROMPT" --cloud >>"$LOG" 2>&1 </dev/null &
else
  nohup script -q /dev/null claude --cloud "$PROMPT" >>"$LOG" 2>&1 </dev/null &
fi
echo "pid $!" >> "$LOG"; disown
sleep 40
LC_ALL=C sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' "$LOG" | tail -c 3000
