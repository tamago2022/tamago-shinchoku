#!/bin/bash
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_commit.txt"
exec >"$OUT" 2>&1
cd "$REPO" || exit 1
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
echo "== 972 commit $(date '+%F %T') =="
git add -- 972-okane-report.html index.html 2>&1
git -c user.name=tamago-972 -c user.email=tamago-972@users.noreply.github.com \
    commit -q -m "972番：今週かかったお金の報告書を追加／進捗表に1行" -- 972-okane-report.html index.html 2>&1
echo "rc=$?"
git log --oneline -1 2>&1
git ls-files --error-unmatch 972-okane-report.html >/dev/null 2>&1 && echo "追跡されている: はい" || echo "追跡されている: いいえ"
echo "--- 公開を1回回す ---"
/bin/bash "$REPO/tools/pages_publish.sh" 2>&1 | tail -5
echo "--- 200確認 ---"
for i in 1 2 3 4 5 6 7 8; do
  C=$(curl -sS -o /dev/null -m 10 -w '%{http_code}' -L "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" 2>/dev/null)
  echo "$(date '+%H:%M:%S')  $C"
  [ "$C" = "200" ] && break
  sleep 30
done
echo "== おわり $(date '+%F %T') =="
