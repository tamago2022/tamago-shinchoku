#!/bin/bash
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$REPO/status/972_url200.txt"
exec >"$OUT" 2>&1
echo "== 200確認 $(date '+%F %T') =="
for i in 1 2 3 4 5 6; do
  C=$(curl -sS -o /dev/null -m 10 -w '%{http_code}' -L "https://tamago2022.github.io/tamago-shinchoku/972-okane-report.html" 2>/dev/null)
  echo "$(date '+%H:%M:%S')  $C  972-okane-report.html"
  [ "$C" = "200" ] && break
  sleep 40
done
echo "== おわり $(date '+%F %T') =="
