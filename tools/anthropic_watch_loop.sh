#!/bin/bash
# 626番専用の独立ループ。
#
# 既存の心臓(heartbeat.sh)にもcheck_anthropic_reply.pyの呼び出しを足したが、
# heartbeat.shは常駐プロセスがすでに動いており、ファイルを書き換えても
# 次に自然に入れ替わるまで反映されない（bashのwhileループは起動時に読み込んだ
# 本体を使い続けるため）。既存の心臓を触ってリスタートさせると、心臓の
# 二重起動事故（failures.md 2番）を再発させかねないので触らない。
#
# 代わりに、この専用ループだけを独立に起動して、今日から確実に1日1回
# 見に行けるようにする。check_anthropic_reply.py自体が内部で「1日1回」に
# 間引くので、ここは30分おきに軽く呼ぶだけでよい（負荷はほぼゼロ）。
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PIDF="$REPO/status/.anthropic_watch_loop.pid"
if [ -f "$PIDF" ]; then
  OLD="$(cat "$PIDF" 2>/dev/null || true)"
  if [ -n "${OLD:-}" ] && [ "$OLD" != "$$" ] && kill -0 "$OLD" 2>/dev/null; then
    exit 0
  fi
fi
echo $$ > "$PIDF"
cleanup(){ if [ "$(cat "$PIDF" 2>/dev/null || true)" = "$$" ]; then rm -f "$PIDF" 2>/dev/null || true; fi; }
trap cleanup EXIT INT TERM

while :; do
  python3 "$REPO/tools/check_anthropic_reply.py" >/dev/null 2>&1 || true
  # 見張り終了フラグが立ったら（返信を検知して知らせ終わったら）このループも静かに終わる
  if [ -f "$REPO/status/.anthropic_watch_done" ]; then
    exit 0
  fi
  sleep 1800
done
