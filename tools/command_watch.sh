#!/bin/bash
# PWAリモコンのコマンドキューを実行し、結果があればpushする（30秒おきにlaunchdから呼ばれる）。
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="/Users/mac/Desktop/tamago-shinchoku"
cd "$REPO" || exit 0

# 2026-09-19（配達係の工事中に実機で踏んだ）：.git/index.lock が置き去りになると、
#   このリポジトリで動く全部の常駐（この便・machine_status_push.sh・Cowork側）の
#   git add / commit が黙って失敗し続ける。実測：06:08に残ったlockのせいで
#   machine_status_push.sh が18分間なにもpushできず、watchdogが16秒おきに
#   蹴り直しても永久に直らない状態になった（lockを消す人が誰もいない）。
#   gitのlockは正常時1秒未満しか存在しない。120秒を超えて残っていたら死体なので片づける。
_LOCK="$REPO/.git/index.lock"
if [ -f "$_LOCK" ]; then
  _AGE=$(( $(date +%s) - $(stat -f %m "$_LOCK" 2>/dev/null || echo 0) ))
  if [ "$_AGE" -gt 120 ]; then
    echo "$(date '+%F %T') 🧹 command_watch: .git/index.lock が${_AGE}秒残っている→片づける" \
      >> "$REPO/status/git_rebase_incidents.log"
    rm -f "$_LOCK" 2>/dev/null || true
  fi
fi

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

# 2026-09-19（配達係）：ここまでの push は「commands.json が変わったときだけ」走る。
#   だがこのリポジトリには push できる出口が事実上ここと machine_status_push.sh の
#   2つしか無く、Cowork/Dispatch のサンドボックスには GitHub の資格情報が無いため
#   （実測：`could not read Username for 'https://github.com'`）、
#   セッション側が commit したものは「誰かが push してくれるまで永久に公開されない」。
#   実際 machine_status_push.sh が詰まると、その未pushのcommitは何十分も宙に浮く。
#   30秒おきに回るこの便で「未pushのcommitが溜まっていたら押し出すだけ」を最後に足す。
#   commit はしない（＝この便が勝手に何かを公開することはない）。押し出すだけ。
if git rev-parse --abbrev-ref --symbolic-full-name '@{u}' >/dev/null 2>&1; then
  _AHEAD=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
  if [ "${_AHEAD:-0}" -gt 0 ]; then
    echo "$(date '+%F %T') 📮 command_watch: 未pushのcommitが${_AHEAD}件→押し出す" \
      >> "$REPO/status/git_rebase_incidents.log"
    git -c credential.helper='!gh auth git-credential' push -q origin main >/dev/null 2>&1
  fi
fi
