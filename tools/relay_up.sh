#!/bin/bash
# 中継所を立ち上げっぱなしにする（進捗表のボタン → Mac）。
#
# 2026-09-04 たまごさん「Obsidianには飛ばない」。
#   PWA(https://tamago2022.github.io) から直接HTTPSで受けるために、
#   ローカルの relay_server.py を cloudflared のクイックトンネル（アカウント不要）で外へ出し、
#   払い出されたURLを status/relay.json に書く。PWAは60秒おきにそれを読み直す。
#
# 使い方：
#   bash tools/relay_up.sh          … 起動（既に動いていれば何もしない）
#   launchd から5分おきに呼んでよい（冪等）
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${RELAY_PORT:-8788}"
LOG="$REPO/status/relay.log"
TUNLOG="$REPO/status/relay_tunnel.log"

# brew未導入でも動くよう、リポジトリ同梱版(tools/bin/cloudflared)をフォールバックに使う。
CLOUDFLARED="$(command -v cloudflared 2>/dev/null || true)"
if [ -z "$CLOUDFLARED" ] && [ -x "$REPO/tools/bin/cloudflared" ]; then
  CLOUDFLARED="$REPO/tools/bin/cloudflared"
fi
have_cloudflared() { [ -n "${CLOUDFLARED:-}" ]; }

# ---- 1. 受け口（python）を起動 ----
if ! pgrep -f "relay_server.py" >/dev/null 2>&1; then
  nohup python3 "$REPO/tools/relay_server.py" >>"$LOG" 2>&1 &
  sleep 1
  echo "$(date '+%F %T') 受け口を起動しました" >>"$LOG"
fi

# ---- 2. トンネルを起動 ----
if ! have_cloudflared; then
  echo "$(date '+%F %T') cloudflared が入っていません。brew install cloudflared が必要です" >>"$LOG"
  exit 0
fi

if ! pgrep -f "cloudflared.*localhost:$PORT" >/dev/null 2>&1; then
  : > "$TUNLOG"
  nohup "$CLOUDFLARED" tunnel --url "http://localhost:$PORT" --no-autoupdate >>"$TUNLOG" 2>&1 &
  # URLが出るまで最大30秒待つ
  for _ in $(seq 1 30); do
    URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNLOG" 2>/dev/null | head -1)"
    [ -n "${URL:-}" ] && break
    sleep 1
  done
else
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNLOG" 2>/dev/null | head -1)"
fi

# ---- 3. URLを進捗表へ渡す ----
if [ -n "${URL:-}" ]; then
  python3 - "$REPO" "$URL" <<'PY'
import json, sys, time, io, os
repo, url = sys.argv[1], sys.argv[2]
p = os.path.join(repo, "status", "relay.json")
old = None
try:
    old = json.load(io.open(p, encoding="utf-8")).get("url")
except Exception:
    pass
if old != url:
    json.dump({"url": url, "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
              io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("relay.json を更新:", url)
PY
  echo "$(date '+%F %T') 中継所URL: $URL" >>"$LOG"
else
  echo "$(date '+%F %T') トンネルのURLがまだ取れません" >>"$LOG"
fi
tail -n 300 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG" 2>/dev/null || true
