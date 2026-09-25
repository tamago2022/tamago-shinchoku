#!/bin/bash
# 1144番【出るまで押す】main に入れたものが本番に出るまで、見る係→押す係を回す。
# 心臓とは縁を切って走る（tools/1144_hanareru.py 経由で起こす）。
cd /Users/mac/Desktop/tamago-shinchoku || exit 1
mkdir -p status/1144
URL="https://joy-relief-station.lovable.app/"
key() { curl -s -o /dev/null -D- "$URL" | awk 'tolower($1)=="x-deployment-id:"{print $2}'; }
BEFORE="$(key)"
echo "$(date '+%H:%M:%S') before=$BEFORE"
for i in $(seq 1 30); do
  python3 tools/kohyou_kanshi.py >/dev/null 2>&1
  python3 tools/kohyou_osu.py    >/dev/null 2>&1
  NOW="$(key)"
  echo "$(date '+%H:%M:%S') [$i] now=${NOW:0:40}"
  if [ -n "$NOW" ] && [ "$NOW" != "$BEFORE" ]; then
    echo "$(date '+%H:%M:%S') ★出ました $BEFORE -> $NOW"
    break
  fi
  sleep 40
done
echo "--- kohyou_osu state ---"; python3 tools/kohyou_osu.py 2>&1 | tail -20
