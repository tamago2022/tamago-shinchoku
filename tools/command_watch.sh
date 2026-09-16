#!/bin/bash
# PWAリモコンのコマンドキューを実行し、結果があればpushする（30秒おきにlaunchdから呼ばれる）。
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="/Users/mac/Desktop/tamago-shinchoku"
cd "$REPO" || exit 0

python3 "$REPO/tools/command_ingest.py" >/tmp/command_ingest.log 2>&1

# 2026-09-13（案件#687）：ここの `pull --rebase` が、このリポジトリ全体の未コミットの変更
#   （このスクリプトが触っていないstatus/queue.json等も含む）を巻き込んでautostashへ退避し、
#   rebase失敗時にサイレントに古い内容へ巻き戻す事故を30秒おきに起こしうる状態だった
#   （実測：2026-09-02〜09-12の間だけで12回の"autostash"残骸を確認・machine_status_push.shと同じ穴）。
#   rebaseをやめてmergeにする。失敗してもコンフリクト状態で残るだけでサイレントな巻き戻りは起きない。
_REBASE_MARKER="$REPO/.git/rebase-merge"
_REBASE_MARKER2="$REPO/.git/rebase-apply"
_MERGE_MARKER="$REPO/.git/MERGE_HEAD"
if [ -d "$_REBASE_MARKER" ] || [ -d "$_REBASE_MARKER2" ] || [ -f "$_MERGE_MARKER" ]; then
  echo "$(date '+%F %T') ⚠️ command_watch: 壊れたrebase/merge残骸を検知→片付ける" \
    >> "$REPO/status/git_rebase_incidents.log"
  git rebase --abort >/dev/null 2>&1 || true
  git merge --abort >/dev/null 2>&1 || true
  rm -rf "$_REBASE_MARKER" "$_REBASE_MARKER2" 2>/dev/null || true
fi
# 2026-09-16：公開先を status/public/commands.json へ移した（status/直下は
#   .gitignoreで追跡対象外。status/public/だけが例外的に追跡される新設パス）。
mkdir -p "$REPO/status/public"
cp -f "$REPO/status/commands.json" "$REPO/status/public/commands.json" 2>/dev/null
git add status/public/commands.json >/dev/null 2>&1
if ! git diff --cached --quiet -- status/public/commands.json 2>/dev/null; then
  git -c user.name="command-ingest" -c user.email="command-ingest@local" commit -q -m "cmd: 実行結果 $(date +%H:%M)" >/dev/null 2>&1 || exit 0
  if ! git -c credential.helper='!gh auth git-credential' pull --no-rebase -q origin main >/dev/null 2>&1; then
    echo "$(date '+%F %T') 🛑 command_watch: git pull(merge) 失敗→ merge --abort で元へ戻す" \
      >> "$REPO/status/git_rebase_incidents.log"
    git merge --abort >/dev/null 2>&1 || true
    rm -rf "$_REBASE_MARKER" "$_REBASE_MARKER2" 2>/dev/null || true
  fi
  git -c credential.helper='!gh auth git-credential' push -q origin main >/dev/null 2>&1
fi
