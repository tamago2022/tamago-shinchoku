#!/bin/bash
# status/cloud_credit/code.txt が置かれてログインが OK になったら、すぐ3本を起動する見張り（start と一緒に切り離して動く・60時間）。
S=/Users/mac/tamago/tamago-shinchoku/status/cloud_credit
END=$(( $(date +%s) + 216000 ))
while [ $(date +%s) -lt $END ]; do
  if [ -f $S/login_result.txt ]; then
    if grep -q OK $S/login_result.txt; then
      for i in 1 2 3 4; do CLOUD_IGNORE_HOURS=1 python3 /Users/mac/tamago/tamago-shinchoku/tools/cloud_mainichi.py; done >> $S/mainichi.log 2>&1
    fi
    exit 0
  fi
  sleep 3
done
