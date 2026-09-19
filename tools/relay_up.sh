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

# brew未導入でも動くよう、~/.tamago/bin/cloudflared（単体バイナリ・git管理外）をフォールバックに使う。
# 2026-09-04: リポジトリ内(tools/bin)に置くと公開リポジトリへ41MBのバイナリをcommitすることになるため、
#   Mac側のローカルインフラ置き場（~/.tamago/配下・公開便Chromeと同じ流儀）へ移した。
CLOUDFLARED="$(command -v cloudflared 2>/dev/null || true)"
if [ -z "$CLOUDFLARED" ] && [ -x "$HOME/.tamago/bin/cloudflared" ]; then
  CLOUDFLARED="$HOME/.tamago/bin/cloudflared"
fi
have_cloudflared() { [ -n "${CLOUDFLARED:-}" ]; }

# ---- 1. 受け口（python）を起動 ----
# 2026-09-05：relay_server.py を直したときに、古いプロセスが動き続けて新機能が効かなかった。
#   ファイルが前回起動より新しければ、いったん落として入れ直す。
STAMP="$REPO/status/.relay_server_started"
# relay_server.py は command_ingest.py を読み込んでいるので、そちらの更新でも入れ直す
if pgrep -f "relay_server.py" >/dev/null 2>&1 && [ -f "$STAMP" ] \
   && { [ "$REPO/tools/relay_server.py" -nt "$STAMP" ] || [ "$REPO/tools/command_ingest.py" -nt "$STAMP" ]; }; then
  pkill -f "relay_server.py" >/dev/null 2>&1 || true
  sleep 1
  echo "$(date '+%F %T') 受け口を入れ直します（コードが新しくなったため）" >>"$LOG"
fi
if ! pgrep -f "relay_server.py" >/dev/null 2>&1; then
  touch "$STAMP"
  nohup python3 "$REPO/tools/relay_server.py" >>"$LOG" 2>&1 &
  sleep 1
  echo "$(date '+%F %T') 受け口を起動しました" >>"$LOG"
fi

# ---- 2. トンネルを起動 ----
if ! have_cloudflared; then
  echo "$(date '+%F %T') cloudflared が入っていません。brew install cloudflared が必要です" >>"$LOG"
  exit 0
fi

# 2026-09-05：**プロセスが居るかどうかで生死を判断してはいけない。**
#   trycloudflare のクイックトンネルは、cloudflared のプロセスを残したまま無言で死ぬ。
#   pgrep が引っかかるので新しく立て直さず、進捗表からのボタンが**丸ごと届かなくなる。**
#   たまごさんの「今すぐ押しても入らない」「今何も動いてませんてなる」の正体がこれ（実測 HTTP 000）。
#   だから**外から実際に叩いて200が返るか**で見る。返らなければ、プロセスが居ても殺して立て直す。
TUNNEL_OK=0
OLD_URL="$(python3 -c "import json,io,sys;print(json.load(io.open(sys.argv[1],encoding='utf-8')).get('url',''))" "$REPO/status/relay.json" 2>/dev/null || true)"
if [ -n "${OLD_URL:-}" ]; then
  CODE="$(curl -s -m 8 -o /dev/null -w '%{http_code}' "$OLD_URL/health" 2>/dev/null || echo 000)"
  [ "$CODE" = "200" ] && TUNNEL_OK=1
  if [ "$TUNNEL_OK" != "1" ]; then
    echo "$(date '+%F %T') トンネルが死んでいます（$OLD_URL → HTTP $CODE）。立て直します" >>"$LOG"
    pkill -f "cloudflared.*localhost:$PORT" >/dev/null 2>&1 || true
    sleep 1
  fi
fi

if [ "$TUNNEL_OK" != "1" ] || ! pgrep -f "cloudflared.*localhost:$PORT" >/dev/null 2>&1; then
  : > "$TUNLOG"
  # 2026-09-05：たまごさんの回線は **QUIC(UDP 7844) が塞がれている**（cloudflaredの事前チェックで
  #   region2 が UDP・TCP ともに FAIL、hard_fail=true）。既定のQUICのままだとトンネルが張れず、
  #   URLが払い出されないまま黙って居座る＝進捗表のボタンが全部死ぬ。
  #   cloudflared 自身が「use HTTP2」と言っているので、最初からHTTP2で張る。
  nohup "$CLOUDFLARED" tunnel --url "http://localhost:$PORT" --protocol http2 --no-autoupdate >>"$TUNLOG" 2>&1 &
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
