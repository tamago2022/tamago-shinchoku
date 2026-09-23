#!/bin/bash
# 1065番：適材適所の紙が、本番で本当に開くかを工場（Mac）から叩いて確かめる。
# サンドボックスからは tamago2022.github.io へ出られない（403 Forbidden）ので、ここで叩く。
# 押すのは確認だけ。課金・公開・解約・削除には一切触らない。
set -u
REPO="$HOME/Desktop/tamago-shinchoku"
URL="https://tamago2022.github.io/tamago-shinchoku/share/check/1065-tekizai.html"
OUT="$REPO/status/1065_kakunin.txt"
PNG="$REPO/status/1065_tekizai_375.png"

cd "$REPO" || exit 1

# まだ載っていなければ、5分便の回収を待たずにここで1回だけ載せる
python3 tools/commit_kuchi.py --drain >/dev/null 2>&1 || true

{
  echo "== $(date '+%F %T') 1065 適材適所の紙 =="
  for i in 1 2 3 4 5 6; do
    CODE=$(curl -s -o /tmp/1065.html -w '%{http_code}' "$URL")
    SIZE=$(wc -c < /tmp/1065.html | tr -d ' ')
    echo "$(date '+%H:%M:%S') httpCode=$CODE bytes=$SIZE $URL"
    if [ "$CODE" = "200" ]; then
      echo "必須語の点検:"
      for W in "適材適所" "得意" "苦手" "通した" "本番に出た" "まだ判定できない"; do
        if grep -q "$W" /tmp/1065.html; then echo "  ◯ $W"; else echo "  ✕ $W"; fi
      done
      break
    fi
    sleep 45
  done

  echo "== 紙を書いた係の自己試験 =="
  python3 tools/tekizai.py --self-test

  echo "== 数字の門 =="
  python3 tools/kazu_gate.py --file share/check/1065-tekizai.html

  echo "== 割り振りが実際に効くか（4本叩く） =="
  python3 tools/tekizai.py --shigoto "yomi-answersのJSONを149件そろえて"   | sed -n '1,2p'
  python3 tools/tekizai.py --shigoto "トップページを軽くする実装をしてPRを出して" | sed -n '1,2p'
  python3 tools/tekizai.py --shigoto "この曲の出典を調べて"                 | sed -n '1,2p'
  python3 tools/tekizai.py --shigoto "この動画は本人かどうか判定して"         | sed -n '1,2p'

  echo "== スマホ1画面（375px）の証拠 =="
  node tools/_825_screenshot_375.mjs "$URL" "$PNG" && echo "  撮れた $PNG"
} > "$OUT" 2>&1

echo "書いた $OUT"
