#!/bin/bash
# 670番: 売上の見張り番（Gumroad+YouTube）を1本のジョブで回すラッパー
# 30分おき起動。Gumroadは毎回、YouTubeは8時台の実行時だけ（1日1回相当）。
# python標準ライブラリのみ・claude CLIは叩かない＝API消費ゼロ。
# 定期実行台帳: AI出力/_ルール/定期実行台帳.md に登録済み（com.tamago.tamago-shinchoku.sales-watch）。
cd "/Users/mac/Desktop/tamago-shinchoku" || exit 1

# 他セッションの未push分と衝突しないよう、まず取り込む（ff-onlyのみ・失敗しても続行）
git fetch origin --quiet 2>/dev/null
git merge --ff-only origin/main --quiet 2>/dev/null

python3 tools/gumroad_sales_sync.py 2>>/tmp/com.tamago.tamago-shinchoku.sales-watch.err

HOUR=$(date +%H)
if [ "$HOUR" = "08" ]; then
  python3 tools/youtube_stats_sync.py 2>>/tmp/com.tamago.tamago-shinchoku.sales-watch.err
fi

TARGETS=""
for f in status/gumroad_last_seen.json status/sales.json status/youtube_stats.json status/youtube_stats_history.json; do
  if [ -f "$f" ]; then
    TARGETS="$TARGETS $f"
  fi
done

if [ -n "$TARGETS" ] && ! git diff --quiet -- $TARGETS 2>/dev/null; then
  git add $TARGETS
  git commit -m "売上見張り番: 自動更新 $(date '+%Y-%m-%d %H:%M')" --quiet
  git push origin main --quiet 2>>/tmp/com.tamago.tamago-shinchoku.sales-watch.err
fi
