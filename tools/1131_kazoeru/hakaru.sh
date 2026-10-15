#!/usr/bin/env bash
# 1131番【壊れている数を数える】本物のソースを、本物の関数で、全件叩いて数える。
#
# たまごさん（2026-09-24）:
#   「推測で言わない。機械で照合する。」「『相当ある』で終わらせない。合計何件かを1つの数字で。」
#
# ★やっていること
#   本番の src/lib をそのまま esbuild で1本に束ね、本番と同じ
#   getShelfPicks() / getEraHitsFallback() を全曲に対して実際に呼ぶ。
#   画面に何が出るかを再現して数えるので、推測が1件も入らない。
#
# ★使い方（工場＝Mac で）
#   bash tools/1131_kazoeru/hakaru.sh [/Users/mac/Desktop/joy-relief-station]
#   → status/1131_kowareteru.json  に種類ごとの件数と合計が出る
#   → tools/1131_kazoeru/page.py で1枚のページになる
#
# ★毎日やるなら：心臓（tools/top_status.py）から、この1本を呼ぶだけ。
#   新しい常駐は増やさない。
set -euo pipefail

SRC="${1:-/Users/mac/Desktop/joy-relief-station}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
WORK="$REPO/status/1131_work"

[ -d "$SRC/src/lib" ] || { echo "本番ソースが無い: $SRC/src/lib"; exit 1; }

rm -rf "$WORK"; mkdir -p "$WORK/src"
cp -R "$SRC/src/lib" "$WORK/src/lib"
[ -d "$SRC/src/assets" ] && cp -R "$SRC/src/assets" "$WORK/src/assets" || mkdir -p "$WORK/src/assets"
cp "$HERE"/common.mjs "$HERE"/a_flow.mjs "$HERE"/a_era.mjs "$HERE"/a_rest.mjs "$WORK/"

cd "$WORK"
cat > entry.ts <<'EOF'
export * as CG from "@/lib/coverGuide";
export * as SP from "@/lib/shelfPicks";
export * as W from "@/lib/worlds";
export * as SIG from "@/lib/artistSignature";
EOF
npx --yes esbuild entry.ts --bundle --format=esm --platform=node --outfile=bundle.mjs \
  --log-level=error --alias:@="$WORK/src" \
  --loader:.png=text --loader:.jpg=text --loader:.svg=text --loader:.webp=text

node --max-old-space-size=6144 a_flow.mjs
node --max-old-space-size=6144 a_era.mjs
node --max-old-space-size=6144 a_rest.mjs
node --max-old-space-size=6144 "$HERE/matome.mjs"

echo "→ $REPO/status/1131_kowareteru.json"
