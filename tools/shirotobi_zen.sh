#!/bin/bash
# 白コマの全場面測定（2026-10-27）。使い方: bash tools/shirotobi_zen.sh <名前> [基点URL]
# コマは $TMPDIR に一時保存し、白いコマの写しだけ share/check/shirotobi/<名前>/ に残して、一時フォルダは必ず消す。
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${1:-$(date +%m%d-%H%M)}"; BASE="${2:-https://joy-relief-station.lovable.app}"
W="$(mktemp -d "${TMPDIR:-/tmp}/shirokoma-XXXXXX")"
trap 'rm -rf "$W"' EXIT
OUTJ="$REPO/status/shirotobi/$NAME.json"; KOMA="$REPO/share/check/shirotobi/$NAME"
mkdir -p "$REPO/status/shirotobi"; rm -rf "$KOMA"
SHIRO_STEPS="$REPO/tools/shirotobi_zenbamen.json" SHIRO_CPU="${SHIRO_CPU:-4}" node "$REPO/tools/shirotobi_sokutei.mjs" "$W" "$BASE" > "$W/sokutei.log" 2>&1
python3 "$REPO/tools/shirotobi_shirokoma.py" "$W" --koma "$KOMA" --json "$OUTJ" > /dev/null
RC=$?
tail -c 3000 "$W/sokutei.log" > "$REPO/status/shirotobi/$NAME.sokutei.log" 2>/dev/null
echo "SHIROKOMA_RESULT: $([ $RC = 0 ] && echo PASS || echo FAIL) $OUTJ"
exit $RC
